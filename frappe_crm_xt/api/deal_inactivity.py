"""Daily Slack nudge for CRM Deals that have gone quiet.

A stock "Days After" notification can only watch ONE date field. Real deal
activity is spread across records that do NOT touch `deal.modified` (verified:
adding a note/task/comment does not bump it):

    - Status / any deal field edit  -> deal.modified
    - Incoming email                -> deal.custom_last_incoming_email_time
    - Outgoing email / reply        -> deal.last_responded_on
    - Notes                         -> FCRM Note   (reference_doctype/docname)
    - Tasks                         -> CRM Task     (reference_doctype/docname)
    - Comments                      -> Comment      (reference_doctype/name)

So this job computes `last_activity` = MAX across all of the above and fires the
Slack alert on the day the gap crosses INACTIVE_DAYS (one nudge per streak).

Efficiency: `last_activity >= modified` always, so only deals last *edited*
>= INACTIVE_DAYS ago can qualify — we pre-filter on that, then resolve the note/
task/comment maxima in ONE grouped query each. Total cost ≈ 4 queries per run.
The message, Condition/Filters and `enabled` switch all live on the Notification
below (editable from the desk): this job decides *which* deals crossed the gap,
then defers to that Notification for the on/off switch, any extra Condition/
Filters, and the rendered message.
"""

import json

import frappe
from frappe.utils import add_days, date_diff, get_datetime, nowdate

NOTIFICATION = "CRM Slack — CRM Deal Inactivity (7 days)"
INACTIVE_DAYS = 7
CLOSED_STATUSES = ("Won", "Lost")


def notify_inactive_deals():
	"""Scheduler entry point (daily)."""
	# The Notification's `enabled` flag is the on/off switch for this feature.
	if not frappe.db.get_value("Notification", NOTIFICATION, "enabled"):
		return

	cutoff = add_days(nowdate(), -INACTIVE_DAYS)
	deals = frappe.get_all(
		"CRM Deal",
		filters={"status": ["not in", CLOSED_STATUSES], "modified": ["<=", cutoff + " 23:59:59"]},
		fields=["name", "modified", "custom_last_incoming_email_time", "last_responded_on"],
	)
	if not deals:
		return {"candidates": 0, "sent": 0}

	names = [d.name for d in deals]
	notes = _latest_map("FCRM Note", "reference_docname", "modified", names)
	tasks = _latest_map("CRM Task", "reference_docname", "modified", names)
	comments = _latest_map("Comment", "reference_name", "creation", names, comment_type="Comment")

	notification = frappe.get_doc("Notification", NOTIFICATION)
	sent = 0
	for d in deals:
		stamps = [
			d.modified,
			d.custom_last_incoming_email_time,
			d.last_responded_on,
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
			notification.send(deal)
			sent += 1
		except Exception:
			frappe.log_error(
				title="Deal inactivity alert failed",
				message=f"Deal: {d.name}\n\n{frappe.get_traceback()}",
			)

	return {"candidates": len(deals), "sent": sent}


def _passes_notification_condition(notification, deal):
	"""Honor the Notification's own Condition / Filters before sending.

	`Notification.send()` does not evaluate these — only frappe's `evaluate_alert`
	does, and that reloads the doc, which would wipe the transient `last_activity_on`
	we set above. So we replicate the same check here (mirroring evaluate_alert's
	precedence: Python condition, else JSON filters) so an admin can further scope
	this alert from the desk without the scheduler ignoring it.
	"""
	from frappe.email.doctype.notification.notification import get_context
	from frappe.utils.data import evaluate_filters

	if notification.condition_type == "Python" and notification.condition:
		return bool(frappe.safe_eval(notification.condition, None, get_context(deal)))
	if notification.condition_type == "Filters" and notification.filters:
		return evaluate_filters(deal, json.loads(notification.filters))
	return True


def _latest_map(doctype, ref_field, date_field, deal_names, comment_type=None):
	"""{deal_name: latest activity timestamp} for the given deals — one grouped query.

	Identifiers (doctype/field names) are module constants, never user input;
	values (deal names, comment_type) are bound parameters.
	"""
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
