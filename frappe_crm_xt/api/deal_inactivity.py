"""Daily Slack digest nudging CRM Deals with no activity for exactly INACTIVE_DAYS."""

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


def notify_inactive_deals():
	"""Scheduler entry point (daily). Gated by the Notification's `enabled` flag."""
	if not frappe.db.get_value("Notification", NOTIFICATION, "enabled"):
		return

	# Only deals touched on target_day can have their gap cross exactly INACTIVE_DAYS today.
	target_day = add_days(nowdate(), -INACTIVE_DAYS)
	day = [target_day + " 00:00:00", target_day + " 23:59:59"]

	candidates = set(
		frappe.get_all(
			"CRM Deal",
			filters={"status": ["not in", CLOSED_STATUSES]},
			or_filters={
				"modified": ["between", day],
				"custom_last_incoming_email_time": ["between", day],
				"last_responded_on": ["between", day],
				"custom_last_responded_on": ["between", day],
			},
			pluck="name",
		)
	)
	candidates |= _deals_touched_on("FCRM Note", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("CRM Task", "reference_docname", "modified", day)
	candidates |= _deals_touched_on("Comment", "reference_name", "creation", day, comment_type="Comment")

	if not candidates:
		return {"candidates": 0, "deals_notified": 0, "messages": 0}

	names = list(candidates)
	deals = frappe.get_all(
		"CRM Deal",
		filters={"name": ["in", names], "status": ["not in", CLOSED_STATUSES]},
		fields=[
			"name",
			"modified",
			"custom_last_incoming_email_time",
			"last_responded_on",
			"custom_last_responded_on",
		],
	)
	notes = _latest_map("FCRM Note", "reference_docname", "modified", names)
	tasks = _latest_map("CRM Task", "reference_docname", "modified", names)
	comments = _latest_map("Comment", "reference_name", "creation", names, comment_type="Comment")

	notification = frappe.get_doc("Notification", NOTIFICATION)
	blocks = []
	for d in deals:
		stamps = [
			d.modified,
			d.custom_last_incoming_email_time,
			d.last_responded_on,
			d.custom_last_responded_on,
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
			blocks.append(_render_message(notification, deal))
		except Exception:
			frappe.log_error(
				title="Deal inactivity alert failed",
				message=f"Deal: {d.name}\n\n{frappe.get_traceback()}",
			)

	if not blocks:
		return {"candidates": len(deals), "deals_notified": 0, "messages": 0}

	messages = _send_slack_digest(notification, blocks)
	return {"candidates": len(deals), "deals_notified": len(blocks), "messages": messages}


def _render_message(notification, deal):
	"""Render the Notification's message template for one deal (same context as .send())."""
	from frappe.email.doctype.notification.notification import get_context

	context = get_context(deal)
	context.update({"alert": notification, "comments": None})
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
	header = f"🔔 *{n} deal{'' if n == 1 else 's'} inactive for {INACTIVE_DAYS}+ days*"

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
	params = {"rdt": "CRM Deal", "names": tuple(deal_names)}
	ct_clause = ""
	if comment_type:
		ct_clause = "and comment_type = %(ct)s"
		params["ct"] = comment_type
	rows = frappe.db.sql(
		f"""
		select `{ref_field}` as ref, max(`{date_field}`) as ts
		from `tab{doctype}`
		where reference_doctype = %(rdt)s and `{ref_field}` in %(names)s {ct_clause}
		group by `{ref_field}`
		""",
		params,
		as_dict=True,
	)
	return {r.ref: r.ts for r in rows if r.ref}
