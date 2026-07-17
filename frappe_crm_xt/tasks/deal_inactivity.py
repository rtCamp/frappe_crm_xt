"""Daily Slack digest nudging CRM Deals with no activity for exactly INACTIVE_DAYS.

For every deal that is flagged, a follow-up CRM Task is created for the deal
owner. If such a task already exists (matched by title + deal) the deal is
skipped entirely — no duplicate task and no repeat Slack message — so the
create-task-counts-as-activity cycle cannot loop.
"""

import json
import re

import frappe
from frappe.utils import add_days, date_diff, get_datetime, nowdate

NOTIFICATION = "CRM Slack — CRM Deal Inactivity (7 days)"
INACTIVE_DAYS = 7
CLOSED_STATUSES = ("Won", "Lost")
SLACK_TEXT_LIMIT = 38000
BLOCK_SEPARATOR = "\n\n"
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)  # Markdown-style comments, stripped from output

# Follow-up task raised for the deal owner. The title is stable so the same deal
# is never nudged twice — see `follow_up_task_exists`.
FOLLOW_UP_TASK_TITLE = "Follow up on inactive deal"
FOLLOW_UP_DUE_DAYS = 2


def notify_inactive_deals():
	"""Scheduler entry point (daily). Gated by the Notification's `enabled` flag."""
	if not frappe.db.exists("Notification", NOTIFICATION):
		frappe.log_error(
			title="Deal inactivity alert not configured",
			message=f"Notification {NOTIFICATION!r} not found; deal-inactivity digest skipped.",
		)
		return

	notification = frappe.get_doc("Notification", NOTIFICATION)
	if not notification.enabled or not notification.slack_webhook_url:
		return

	# Only deals touched on target_day can have their gap cross exactly INACTIVE_DAYS today.
	target_day = add_days(nowdate(), -INACTIVE_DAYS)
	day = [target_day + " 00:00:00", target_day + " 23:59:59"]

	deal_meta = frappe.get_meta("CRM Deal")
	custom_date_fields = [
		f for f in ("custom_last_incoming_email_time", "custom_last_responded_on") if deal_meta.has_field(f)
	]
	or_filters = {"modified": ["between", day], "last_responded_on": ["between", day]}
	for f in custom_date_fields:
		or_filters[f] = ["between", day]

	candidates = set(
		frappe.get_all(
			"CRM Deal",
			filters={"status": ["not in", CLOSED_STATUSES]},
			or_filters=or_filters,
			pluck="name",
		)
	)
	candidates |= _deals_touched_on("FCRM Note", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("CRM Task", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("Comment", "reference_name", "creation", day, comment_type="Comment")

	if not candidates:
		return {"candidates": 0, "deals_notified": 0, "messages": 0, "tasks_created": 0}

	names = list(candidates)
	deals = frappe.get_all(
		"CRM Deal",
		filters={"name": ["in", names], "status": ["not in", CLOSED_STATUSES]},
		fields=["name", "modified", "last_responded_on", *custom_date_fields],
	)
	notes = _latest_map("FCRM Note", "reference_docname", "modified", names)
	tasks = _latest_map("CRM Task", "reference_docname", "modified", names)
	comments = _latest_map("Comment", "reference_name", "creation", names, comment_type="Comment")

	blocks = []
	tasks_created = 0
	for d in deals:
		stamps = [
			d.modified,
			d.last_responded_on,
			d.get("custom_last_incoming_email_time"),
			d.get("custom_last_responded_on"),
			notes.get(d.name),
			tasks.get(d.name),
			comments.get(d.name),
		]
		last = max(get_datetime(s) for s in stamps if s)
		if date_diff(nowdate(), last) != INACTIVE_DAYS:
			continue
		try:
			deal = frappe.get_doc("CRM Deal", d.name)
			deal.last_activity_on = last  # transient, surfaced in the message
			if not _passes_notification_condition(notification, deal):
				continue
			# Already nudged: a follow-up task exists for this deal. Skip so we
			# don't re-notify or create a duplicate task (avoids the loop where
			# creating a task counts as fresh activity).
			if follow_up_task_exists(deal.name):
				continue
			_create_follow_up_task(deal, last)
			tasks_created += 1
			blocks.append(_render_message(notification, deal))
		except Exception:
			frappe.log_error(
				title="Deal inactivity alert failed",
				message=f"Deal: {d.name}\n\n{frappe.get_traceback()}",
			)

	if not blocks:
		return {"candidates": len(deals), "deals_notified": 0, "messages": 0, "tasks_created": 0}

	messages = _send_slack_digest(notification, blocks)
	return {
		"candidates": len(deals),
		"deals_notified": len(blocks),
		"messages": messages,
		"tasks_created": tasks_created,
	}


def follow_up_task_exists(deal_name):
	"""Return True if a follow-up CRM Task already exists for this deal.

	Matched by the standard follow-up title + the deal reference, so a deal that
	has already been nudged is not notified (or given another task) again.
	"""
	return bool(
		frappe.db.exists(
			"CRM Task",
			{
				"reference_doctype": "CRM Deal",
				"reference_docname": deal_name,
				"title": FOLLOW_UP_TASK_TITLE,
			},
		)
	)


def _create_follow_up_task(deal, last_activity):
	"""Raise a follow-up CRM Task for the deal owner on an inactive deal."""
	task = frappe.new_doc("CRM Task")
	task.title = FOLLOW_UP_TASK_TITLE
	task.status = "Todo"
	task.priority = "High"
	task.assigned_to = deal.deal_owner
	task.due_date = add_days(nowdate(), FOLLOW_UP_DUE_DAYS)
	task.reference_doctype = "CRM Deal"
	task.reference_docname = deal.name
	task.description = (
		f"This deal has had no activity for {INACTIVE_DAYS} days "
		f"(last activity on {get_datetime(last_activity).date()}). Please follow up."
	)
	task.insert(ignore_permissions=True)
	return task.name


def _render_message(notification, deal):
	"""Render the Notification's message template for one deal (same context as .send())."""
	from frappe.email.doctype.notification.notification import get_context

	context = get_context(deal)
	context.update({"alert": notification, "comments": None})
	# message is admin-authored (System Manager only); trusted template surface, like frappe's Notification.send().
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	return frappe.render_template(notification.message, context)


def _send_slack_digest(notification, blocks):
	"""Post the blocks as one Slack message under a header; split only if over the size cap."""
	from frappe.integrations.doctype.slack_webhook_url.slack_webhook_url import send_slack_message

	# A Markdown comment supplies the divider between blocks (its inner text, with \n
	# unescaped); all comments are stripped from the output.
	separator = BLOCK_SEPARATOR
	for b in blocks:
		m = COMMENT_RE.search(b)
		if m:
			separator = m.group(1).replace("\\n", "\n")
			break
	blocks = [COMMENT_RE.sub("", b).strip() for b in blocks]

	n = len(blocks)
	# subject is admin-authored (System Manager only); same trusted template surface.
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-ssti
	header = frappe.render_template(notification.subject or "", {"count": n, "days": INACTIVE_DAYS})

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


def _deals_touched_on(doctype, ref_field, date_field, day, comment_type=None):
	"""Set of CRM Deal names with a note/task/comment dated within the `day` [start, end] range."""
	filters = {
		"reference_doctype": "CRM Deal",
		ref_field: ["is", "set"],
		date_field: ["between", day],
	}
	if comment_type:
		filters["comment_type"] = comment_type
	return set(frappe.get_all(doctype, filters=filters, pluck=ref_field))


def _latest_map(doctype, ref_field, date_field, deal_names, comment_type=None):
	"""{deal_name: latest activity timestamp} for the given deals — one grouped query."""
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
