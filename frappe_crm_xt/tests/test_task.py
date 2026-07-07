# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.doc_events.task import on_trash


class TestTaskEvents(IntegrationTestCase):
	def _make_task(self, title_suffix: str) -> str:
		task = frappe.get_doc(
			{"doctype": "CRM Task", "title": f"XT-Task-{title_suffix}-{frappe.generate_hash(length=6)}"}
		).insert(ignore_permissions=True)
		return task.name

	def _make_notification(self, task_name: str) -> str:
		notif = frappe.get_doc(
			{
				"doctype": "CRM Notification",
				"to_user": "Administrator",
				"type": "Task",
				"notification_type_doctype": "CRM Task",
				"notification_type_doc": task_name,
			}
		).insert(ignore_permissions=True)
		return notif.name

	def test_on_trash_deletes_matching_notification(self):
		"""on_trash removes CRM Notification rows pointing at the trashed CRM Task"""
		task_name = self._make_task("Delete")
		notif_name = self._make_notification(task_name)

		self.assertTrue(frappe.db.exists("CRM Notification", notif_name))

		on_trash(frappe._dict(name=task_name))

		self.assertFalse(frappe.db.exists("CRM Notification", notif_name))

	def test_on_trash_with_no_matching_notifications(self):
		"""on_trash runs cleanly when no notification references the task"""
		task_name = self._make_task("NoNotif")

		on_trash(frappe._dict(name=task_name))

	def test_on_trash_does_not_touch_unrelated_notifications(self):
		"""on_trash leaves notifications for other tasks untouched"""
		task_a = self._make_task("A")
		task_b = self._make_task("B")
		notif_b = self._make_notification(task_b)

		on_trash(frappe._dict(name=task_a))

		self.assertTrue(frappe.db.exists("CRM Notification", notif_b))
