"""Daily scheduler: flag CRM Deals idle for N working days — post a Slack digest and,
optionally, create a follow-up CRM Task. Config lives on the CRM XT Settings doctype;
holidays come from the resolved Holiday List (per-deal when the Company option is on).
"""

import json
import re

import frappe
from frappe.utils import add_days, get_datetime, getdate, nowdate

SETTINGS = "CRM XT Settings"

# Defaults for blank CRM XT Settings fields.
DEFAULT_INACTIVE_DAYS = 7  # working days
DEFAULT_CLOSED_STATUSES = ("Won", "Lost")
DEFAULT_TASK_TITLE = "Follow up on inactive deal"
DEFAULT_TASK_PRIORITY = "High"

# Candidate window = last activity in [threshold, threshold + buffer] calendar days.
# Bounds the query; deals idle beyond the band aren't chased. Overridable in settings.
DEFAULT_WINDOW_BUFFER_DAYS = 4

# Slack message size cap + the message template's comment-divider syntax.
SLACK_TEXT_LIMIT = 38000
BLOCK_SEPARATOR = "\n\n"
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)


def notify_inactive_deals(as_of=None):
	"""Scheduler entry (daily); runs only when a Notification is selected and enabled.

	`as_of` ("YYYY-MM-DD") overrides today for backfill/tests; the scheduler passes none.
	"""
	if not frappe.db.exists("DocType", SETTINGS):
		return
	settings = frappe.get_cached_doc(SETTINGS)

	notification_name = settings.get("deal_inactivity_notification")
	if not notification_name or not frappe.db.exists("Notification", notification_name):
		return  # off until a Notification is chosen
	notification = frappe.get_doc("Notification", notification_name)
	if not notification.enabled:
		return

	threshold = _cfg_inactive_days(settings)  # working days
	closed_statuses = DEFAULT_CLOSED_STATUSES
	followup_enabled = bool(settings.get("deal_inactivity_followup_enabled"))
	use_company_hl = bool(settings.get("deal_inactivity_use_company_holiday_list"))
	fixed_hl = settings.get("deal_inactivity_holiday_list")
	title_tmpl = settings.get("deal_inactivity_task_title")
	body_tmpl = settings.get("deal_inactivity_task_body")
	priority = settings.get("deal_inactivity_task_priority") or DEFAULT_TASK_PRIORITY
	buffer_days = _cfg_window_buffer(settings)

	today = as_of or nowdate()

	# Bounded window: last activity in [threshold, threshold + buffer_days] calendar days.
	# The exact working-day check runs per deal below.
	high_day = add_days(today, -threshold)
	low_day = add_days(today, -(threshold + buffer_days))
	day = [low_day + " 00:00:00", high_day + " 23:59:59"]

	deal_meta = frappe.get_meta("CRM Deal")
	# Deal-level activity date fields that exist in this deployment (all guarded).
	date_fields = [
		f for f in ("last_responded_on", "custom_last_incoming_email_time") if deal_meta.has_field(f)
	]
	has_company = deal_meta.has_field("company")
	or_filters = {"modified": ["between", day]}
	for f in date_fields:
		or_filters[f] = ["between", day]

	# Notes/tasks/comments don't bump deal.modified, so gather from every source.
	candidates = set(
		frappe.get_all(
			"CRM Deal",
			filters={"status": ["not in", closed_statuses]},
			or_filters=or_filters,
			pluck="name",
		)
	)
	candidates |= _deals_touched_on("FCRM Note", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("CRM Task", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("Comment", "reference_name", "creation", day, comment_type="Comment")
	if not candidates:
		return {"candidates": 0, "deals_notified": 0, "messages": 0}

	names = list(candidates)
	fields = ["name", "modified", *date_fields]
	if has_company:
		fields.append("company")
	deals = frappe.get_all(
		"CRM Deal",
		filters={"name": ["in", names], "status": ["not in", closed_statuses]},
		fields=fields,
	)
	notes = _latest_map("FCRM Note", "reference_docname", "modified", names)
	tasks = _latest_map("CRM Task", "reference_docname", "modified", names)
	comments = _latest_map("Comment", "reference_name", "creation", names, comment_type="Comment")

	# Per-run caches (avoid N+1): company → holiday_list, holiday_list → date set.
	company_hl, holiday_sets = {}, {}

	blocks = []
	for d in deals:
		stamps = [d.modified, notes.get(d.name), tasks.get(d.name), comments.get(d.name)]
		stamps += [d.get(f) for f in date_fields]
		last = max(get_datetime(s) for s in stamps if s)

		holiday_list = _resolve_holiday_list(d, use_company_hl, fixed_hl, company_hl)
		holidays = _holiday_dates(holiday_list, low_day, today, holiday_sets)
		if _is_non_working_day(today, holidays):
			continue  # skip on the deal's own holiday; caught next working day
		if not _reached_working_days(last, today, holidays, threshold):
			continue
		try:
			deal = frappe.get_doc("CRM Deal", d.name)
			deal.last_activity_on = last  # transient, surfaced in the message
			if not _passes_notification_condition(notification, deal):
				continue
			title = _render_task_field(title_tmpl, deal) or DEFAULT_TASK_TITLE
			if _followup_exists(deal.name, title, last):
				continue  # streak already handled
			block = _render_message(
				notification, deal
			)  # render before side effects (no orphan task on a bad template)
			if followup_enabled:
				_create_followup_task(deal, title, _render_task_field(body_tmpl, deal), priority)
			blocks.append(block)
		except Exception:
			frappe.log_error(
				title="Deal inactivity alert failed",
				message=f"Deal: {d.name}\n\n{frappe.get_traceback()}",
			)

	if not blocks:
		return {"candidates": len(deals), "deals_notified": 0, "messages": 0}

	# Digest needs a webhook; follow-up tasks are created regardless.
	messages = _send_slack_digest(notification, blocks, threshold) if notification.slack_webhook_url else 0
	return {"candidates": len(deals), "deals_notified": len(blocks), "messages": messages}


def _render_message(notification, deal):
	"""Render the Notification's message template for one deal (same context as .send())."""
	from frappe.email.doctype.notification.notification import get_context

	context = get_context(deal)
	context.update({"alert": notification, "comments": None})
	# admin-authored template (System Manager); trusted surface, like Notification.send().
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	return frappe.render_template(notification.message, context)


def _send_slack_digest(notification, blocks, threshold):
	"""Post the blocks under one header, splitting into more messages only past the size cap."""
	from frappe.integrations.doctype.slack_webhook_url.slack_webhook_url import send_slack_message

	# First message-comment supplies the block divider (\n unescaped); comments are stripped.
	separator = BLOCK_SEPARATOR
	for b in blocks:
		m = COMMENT_RE.search(b)
		if m:
			separator = m.group(1).replace("\\n", "\n")
			break
	blocks = [COMMENT_RE.sub("", b).strip() for b in blocks]

	n = len(blocks)
	# admin-authored subject; same trusted surface.
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	header = frappe.render_template(notification.subject or "", {"count": n, "days": threshold})

	posts, current = [], None
	for block in blocks:
		if current is None:
			current = f"{header}\n\n{block}"
			continue
		candidate = current + separator + block
		if len(candidate) > SLACK_TEXT_LIMIT:
			posts.append(current)
			current = f"{header}\n\n{block}"
		else:
			current = candidate
	if current is not None:
		posts.append(current)

	for post in posts:
		send_slack_message(
			webhook_url=notification.slack_webhook_url,
			message=post,
			reference_doctype="CRM Deal",
			reference_name=None,
		)
	return len(posts)


def _passes_notification_condition(notification, deal):
	"""Honor the Notification's own Condition/Filters (which .send() itself does not)."""
	from frappe.email.doctype.notification.notification import get_context
	from frappe.utils.data import evaluate_filters

	if notification.condition_type == "Python" and notification.condition:
		return bool(frappe.safe_eval(notification.condition, None, get_context(deal)))
	if notification.condition_type == "Filters" and notification.filters:
		return evaluate_filters(deal, json.loads(notification.filters))
	return True


# ─── settings-backed config ─────────────────────────────────────────────────────


def _cfg_inactive_days(settings):
	"""Working-day threshold; DEFAULT_INACTIVE_DAYS when blank."""
	try:
		days = int(settings.get("deal_inactivity_days") or 0)
	except (TypeError, ValueError):
		days = 0
	return days if days > 0 else DEFAULT_INACTIVE_DAYS


def _cfg_window_buffer(settings):
	"""Catch-up buffer; honors an explicit 0, falls back to the default only when blank."""
	v = settings.get("deal_inactivity_window_buffer_days")
	if v in (None, ""):
		return DEFAULT_WINDOW_BUFFER_DAYS
	try:
		v = int(v)
	except (TypeError, ValueError):
		return DEFAULT_WINDOW_BUFFER_DAYS
	return v if v >= 0 else DEFAULT_WINDOW_BUFFER_DAYS


# ─── follow-up task (plain to-do, deduped by title) ─────────────────────────────


def _followup_exists(deal_name, title, last):
	"""Whether a same-title follow-up task exists for this streak (created since `last`)."""
	return bool(
		frappe.get_all(
			"CRM Task",
			filters={
				"reference_doctype": "CRM Deal",
				"reference_docname": deal_name,
				"title": title,
				"creation": [">=", get_datetime(last)],
			},
			limit=1,
			ignore_permissions=True,
		)
	)


def _create_followup_task(deal, title, body, priority):
	"""Plain follow-up CRM Task — no dates/calendar fields, so never a calendar task."""
	frappe.get_doc(
		{
			"doctype": "CRM Task",
			"title": title,
			"description": body or None,
			"reference_doctype": "CRM Deal",
			"reference_docname": deal.name,
			"assigned_to": deal.get("deal_owner") or None,
			"status": "Todo",
			"priority": priority,
		}
	).insert(ignore_permissions=True)


def _render_task_field(template, deal):
	"""Render an admin-authored Jinja title/body template against the deal."""
	if not template:
		return ""
	from frappe.email.doctype.notification.notification import get_context

	# admin-authored via CRM XT Settings (System Manager); trusted surface.
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	return frappe.render_template(template, get_context(deal))


# ─── working-day helpers (non-working = in the resolved Holiday List) ───────────


def _reached_working_days(last_dt, today, holidays, threshold):
	"""Whether ≥ `threshold` working days fall in (last_dt, today]. Empty `holidays` set →
	every day counts."""
	if threshold <= 0:
		return True
	end = getdate(today)
	day = add_days(getdate(last_dt), 1)
	count = 0
	while getdate(day) <= end:
		if getdate(day) not in holidays:
			count += 1
			if count >= threshold:
				return True
		day = add_days(day, 1)
	return False


def _resolve_holiday_list(deal, use_company_hl, fixed_hl, company_hl):
	"""Deal's Company default (if enabled) → fixed field → None. `company_hl` memoizes lookups."""
	if use_company_hl:
		company = deal.get("company")
		if company:
			if company not in company_hl:
				company_hl[company] = frappe.db.get_value("Company", company, "default_holiday_list")
			if company_hl[company]:
				return company_hl[company]
	return fixed_hl or None


def _holiday_dates(holiday_list, start, end, cache):
	"""Holiday dates in [start, end] as a frozenset — one query per list per run (cached)."""
	if not holiday_list:
		return frozenset()
	if holiday_list not in cache:
		rows = frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "is_half_day": 0, "holiday_date": ["between", [start, end]]},
			pluck="holiday_date",
		)
		cache[holiday_list] = frozenset(getdate(d) for d in rows)
	return cache[holiday_list]


def _is_non_working_day(date, holidays):
	"""Whether `date` is in the prefetched holiday set."""
	return getdate(date) in holidays


def _deals_touched_on(doctype, ref_field, date_field, day, comment_type=None):
	"""CRM Deal names with a note/task/comment dated within the `day` window."""
	filters = {
		"reference_doctype": "CRM Deal",
		ref_field: ["is", "set"],
		date_field: ["between", day],
	}
	if comment_type:
		filters["comment_type"] = comment_type
	return set(frappe.get_all(doctype, filters=filters, pluck=ref_field))


def _latest_map(doctype, ref_field, date_field, deal_names, comment_type=None):
	"""{deal: latest activity timestamp} across the given deals — one grouped query."""
	if not deal_names:
		return {}
	from frappe.query_builder.functions import Max

	t = frappe.qb.DocType(doctype)
	q = (
		frappe.qb.from_(t)
		.select(t[ref_field].as_("ref"), Max(t[date_field]).as_("ts"))
		.where(t.reference_doctype == "CRM Deal")
		.where(t[ref_field].isin(deal_names))
	)
	if comment_type:
		q = q.where(t.comment_type == comment_type)
	q = q.groupby(t[ref_field])
	return {r.ref: r.ts for r in q.run(as_dict=True) if r.ref}
