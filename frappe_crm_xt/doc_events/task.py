"""on_trash for CRM Task.

When a CRM Task is deleted, the `notification_type_doctype` /
`notification_type_doc` pair on any CRM Notification that pointed at
this task becomes a dangling reference and trips Frappe's dynamic-link
check, blocking the delete with LinkExistsError. Clear only those two
fields; `reference_doctype` / `reference_name` (the parent Lead/Deal
the notification belongs to) is left intact.

`on_trash` fires before `check_if_doc_is_dynamically_linked`
(frappe/model/delete_doc.py: on_trash at L165, link check at L173),
so doing the cleanup here lets the delete proceed normally.
"""

from __future__ import annotations

import frappe

_CRM_TASK = "CRM Task"
_CRM_NOTIFICATION = "CRM Notification"


def on_trash(doc, method=None):
	if not doc.name:
		return

	notifications = frappe.get_all(
		_CRM_NOTIFICATION,
		filters={"notification_type_doctype": _CRM_TASK, "notification_type_doc": doc.name},
		pluck="name",
	)
	for name in notifications:
		# db.set_value bypasses CRM Notification's validate so the cleared
		# fields aren't re-resolved.
		frappe.db.set_value(
			_CRM_NOTIFICATION,
			name,
			{"notification_type_doctype": "", "notification_type_doc": ""},
			update_modified=False,
		)
