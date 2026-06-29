from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime

_CRM_TASK = "CRM Task"
_CRM_NOTIFICATION = "CRM Notification"


def validate(doc, method=None):
	"""Validate a CRM Task before save."""
	doc.start_date = doc.get("custom_start_datetime")  # for upstream's benefit
	validate_due_after_start(doc)


def validate_due_after_start(doc):
	"""Reject saves where `due_date` is at or before `custom_start_datetime`.

	Both are Datetime fields stored in the system timezone, so they compare
	directly. Skips silently when either is missing — partial date input is
	allowed (used by quick-create flows that only fill one end of the window).
	"""
	start = doc.get("custom_start_datetime")
	due_date = doc.get("due_date")
	if not (start and due_date):
		return

	start_moment = get_datetime(start)
	due_moment = get_datetime(due_date)

	if due_moment <= start_moment:
		frappe.throw(
			_("Due Date ({0}) must be after Start Date & Time ({1}).").format(due_moment, start_moment)
		)


def on_trash(doc, method=None):
	notifications = frappe.get_all(
		_CRM_NOTIFICATION,
		filters={"notification_type_doctype": _CRM_TASK, "notification_type_doc": doc.name},
		pluck="name",
	)
	for name in notifications:
		frappe.delete_doc(_CRM_NOTIFICATION, name)
