"""Backfill FCRM Note.posting_datetime ← creation for legacy rows."""

import click
import frappe

from frappe_crm_xt.setup import install_custom_fields


def execute():
	if not frappe.db.exists("DocType", "FCRM Note"):
		return

	# Patch may run before `after_migrate` installs the custom field on a
	# fresh deploy — install it first so the column exists.
	install_custom_fields()

	count = frappe.db.count("FCRM Note", {"posting_datetime": ["is", "not set"]})
	if not count:
		return

	note = frappe.qb.DocType("FCRM Note")
	frappe.qb.update(note).set(note.posting_datetime, note.creation).where(
		note.posting_datetime.isnull()
	).run()

	click.secho(
		f"  FCRM Note.posting_datetime ← creation on {count} row(s)",
		fg="green",
	)
	frappe.db.commit()
