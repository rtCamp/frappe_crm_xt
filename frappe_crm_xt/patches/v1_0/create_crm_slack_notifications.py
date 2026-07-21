"""
Three Notifications drive CRM → Slack alerts:

  * "CRM Slack — CRM Deal Inactivity (7 days)"  (event: Custom, CRM Deal)
        Drives frappe_crm_xt.tasks.deal_inactivity.notify_inactive_deals (daily
        cron), which creates a follow-up CRM Task on each inactive deal and posts
        a Slack digest. Its `enabled` flag is that feature's on/off switch, and the
        cron honors its Condition/Filters and renders its Message when sending.
  * "CRM Slack — CRM Deal Note Added"           (event: New,  FCRM Note)
  * "CRM Slack — CRM Deal Updates"              (event: Save, CRM Deal)
        Fired automatically by Frappe's document-event machinery on save/insert.


"""

import json
from pathlib import Path

import frappe

WEBHOOK = "CRM webhook"

DEFINITIONS = Path(__file__).with_name("crm_slack_notifications.json")


def execute():
	webhook = WEBHOOK if frappe.db.exists("Slack Webhook URL", WEBHOOK) else None
	definitions = json.loads(DEFINITIONS.read_text(encoding="utf-8"))

	created = []
	for defn in definitions:
		name = defn["name"]
		if frappe.db.exists("Notification", name):
			continue

		doc = frappe.new_doc("Notification")
		doc.name = name
		doc.update(defn)
		doc.slack_webhook_url = webhook
		doc.enabled = 0  # opt-in: admin links the webhook and enables from the desk
		doc.insert(ignore_permissions=True)
		created.append(name)

	if created:
		hint = f"pre-linked to {WEBHOOK!r}" if webhook else "no webhook linked"
		print(f"Seeded {len(created)} CRM-Slack Notification(s), disabled ({hint}): " + ", ".join(created))
