"""Reset FCRM Note.modified ← creation for legacy rows."""

import click
import frappe


def execute():
	if not frappe.db.exists("DocType", "FCRM Note"):
		return

	# Scope to migrator-created notes only — they carry custom_source_crm_note.
	if not frappe.db.has_column("FCRM Note", "custom_source_crm_note"):
		return

	note = frappe.qb.DocType("FCRM Note")
	frappe.qb.update(note).set(note.modified, note.creation).where(
		note.custom_source_crm_note.notnull()
	).run()

	click.secho(
		"  FCRM Note.modified ← creation",
		fg="green",
	)
	frappe.db.commit()
