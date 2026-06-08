"""Delete stale Data-type CRM Organization.custom_source so it re-syncs as a Link."""

import click
import frappe


def execute():
	name = "CRM Organization-custom_source"
	if not frappe.db.exists("Custom Field", name):
		return

	if frappe.db.get_value("Custom Field", name, "fieldtype") != "Data":
		return

	frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	click.secho(
		"  Deleted stale Data-type CRM Organization.custom_source (will re-sync as Link)",
		fg="green",
	)
	frappe.db.commit()
