"""
Override of crm.api.activities.get_activities.

Calls the upstream FCRM handler first, then merges frappe_gmail_thread entries
when that app is installed.  Degrades cleanly: if frappe_gmail_thread is absent
this is a pure passthrough.

Response shape expected by FCRM's Activities.vue:
	(activities, calls, notes, tasks, attachments)   ← 5-tuple
"""

from __future__ import annotations

import frappe


@frappe.whitelist()
def get_activities(name: str):
	from crm.api.activities import get_activities as _upstream

	activities, calls, notes, tasks, attachments = _upstream(name)
	activities = list(activities)

	if "frappe_gmail_thread" in frappe.get_installed_apps():
		from frappe_gmail_thread.api.activity import get_linked_gmail_threads

		if frappe.db.exists("CRM Lead", name):
			doctype = "CRM Lead"
			is_lead = True
		else:
			doctype = "CRM Deal"
			is_lead = False

		threads = get_linked_gmail_threads(doctype, name)

		for thread in threads:
			doc = thread["template_data"]["doc"]
			activities.append(
				{
					"activity_type": "communication",
					"communication_type": "Email",
					"communication_date": doc["communication_date"],
					"creation": doc["creation"],
					"data": {
						"subject": doc["subject"],
						"content": doc["content"],
						"sender_full_name": doc["sender_full_name"],
						"sender": doc["sender"],
						"recipients": doc["recipients"],
						"cc": doc["cc"],
						"bcc": doc["bcc"],
						"attachments": doc["attachments"],
						"read_by_recipient": doc["read_by_recipient"],
						"delivery_status": doc["delivery_status"],
					},
					"is_lead": is_lead,
				}
			)

		activities.sort(key=lambda x: x.get("creation", ""), reverse=True)

	return activities, calls, notes, tasks, attachments
