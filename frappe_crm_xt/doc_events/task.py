from __future__ import annotations

import frappe

_CRM_TASK = "CRM Task"
_CRM_NOTIFICATION = "CRM Notification"


def on_trash(doc, method=None):
	notifications = frappe.get_all(
		_CRM_NOTIFICATION,
		filters={"notification_type_doctype": _CRM_TASK, "notification_type_doc": doc.name},
		pluck="name",
		ignore_permissions=True,
	)
	for name in notifications:
		frappe.delete_doc(_CRM_NOTIFICATION, name, ignore_permissions=True, delete_permanently=True)
