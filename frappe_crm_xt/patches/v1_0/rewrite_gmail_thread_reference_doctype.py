"""Rewrite Gmail Thread.reference_doctype Lead/Opportunity → CRM Lead/CRM Deal.

Gmail Threads link to the doc the email belongs to via
`reference_doctype` + `reference_name`. Before the ERPNext-CRM →
Frappe-CRM migration, threads on this site point at the ERPNext source
doctypes; after migration, they should point at the Frappe CRM
equivalents so the timeline widget on the migrated record finds them.

`reference_name` is preserved by the migrator's source-meta-preservation
policy (source name == target name), so only the doctype column needs
to flip. Idempotent — once rewritten, the WHERE filter no longer
matches.

No-op when `frappe_gmail_thread` isn't installed.
"""

import click
import frappe


_DOCTYPE_MAP = {
	"Lead": "CRM Lead",
	"Opportunity": "CRM Deal",
}


def execute():
	if "frappe_gmail_thread" not in frappe.get_installed_apps():
		return
	if not frappe.db.exists("DocType", "Gmail Thread"):
		return

	thread = frappe.qb.DocType("Gmail Thread")

	for src, tgt in _DOCTYPE_MAP.items():
		count = frappe.db.count("Gmail Thread", {"reference_doctype": src})
		if not count:
			continue

		frappe.qb.update(thread).set(thread.reference_doctype, tgt).where(
			thread.reference_doctype == src
		).run()

		click.secho(
			f"  Gmail Thread.reference_doctype: {src} → {tgt} on {count} row(s)",
			fg="green",
		)

	frappe.db.commit()
