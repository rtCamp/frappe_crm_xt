"""Delete stale Data-type CRM Organization.custom_source so it re-syncs as a Link."""

import click
import frappe


def execute():
	name = frappe.db.get_value(
		"Custom Field",
		{"dt": "CRM Organization", "fieldname": "custom_source", "fieldtype": "Data"},
		"name",
	)
	if not name:
		return

	frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)
	click.secho(
		"  Deleted stale Data-type CRM Organization.custom_source (will re-sync as Link)",
		fg="green",
	)
