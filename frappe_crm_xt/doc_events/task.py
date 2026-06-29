from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime

from frappe_crm_xt.doc_events.calendar_sync import _combine_date_time

_CRM_TASK = "CRM Task"
_CRM_NOTIFICATION = "CRM Notification"


def validate(doc, method=None):
	"""Validate a CRM Task before save."""
	validate_due_after_start(doc)


def validate_due_after_start(doc):
	"""Reject saves where `due_date` is at or before `start_date + custom_start_time`.

	Skips silently when either field is missing — partial date input is allowed
	(used by quick-create flows that only fill one end of the window).
	"""
	start_date = doc.get("start_date")
	due_date = doc.get("due_date")
	if not (start_date and due_date):
		return

	start_moment = _combine_date_time(start_date, doc.get("custom_start_time"))
	due_moment = get_datetime(due_date)

	if due_moment <= start_moment:
		suffix = " + Start Time" if doc.get("custom_start_time") else ""
		frappe.throw(
			_("Due Date ({0}) must be after Start Date{1} ({2}).").format(due_moment, suffix, start_moment)
		)


def on_trash(doc, method=None):
	notifications = frappe.get_all(
		_CRM_NOTIFICATION,
		filters={"notification_type_doctype": _CRM_TASK, "notification_type_doc": doc.name},
		pluck="name",
	)
	for name in notifications:
		frappe.delete_doc(_CRM_NOTIFICATION, name)
