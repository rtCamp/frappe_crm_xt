"""Register CRM doctypes in Global Search Settings and backfill __global_search."""

import click
import frappe
from frappe.utils.global_search import rebuild_for_doctype

from frappe_crm_xt.setup import install

# CRM Task is excluded: its autoincrement (int) names crash
# rebuild_for_doctype (frappe.db.escape only accepts str/bytes).
DOCTYPES = ("CRM Lead", "CRM Deal", "FCRM Note")


def execute():
	# Patch may run before `after_migrate` applies the in_global_search
	# custom fields / property setters on a fresh deploy — install them first.
	install()

	settings = frappe.get_doc("Global Search Settings")
	registered = {d.document_type for d in settings.allowed_in_global_search}
	if missing := [dt for dt in DOCTYPES if dt not in registered]:
		for doctype in missing:
			settings.append("allowed_in_global_search", {"document_type": doctype})
		settings.save(ignore_permissions=True)

	for doctype in DOCTYPES:
		rebuild_for_doctype(doctype)

	click.secho(f"  Global search index rebuilt for {', '.join(DOCTYPES)}", fg="green")
