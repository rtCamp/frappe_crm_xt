"""Move child rows from `Opportunity Status Checklist` → `CRM Deal Status Checklist`.

Both child doctypes share the same single-column schema (`checklist_item`,
Data). Source rows live in `tabOpportunity Status Checklist` and are
anchored to either:
  - `parenttype='CRM Deal Status', parentfield='checklist'` (the canonical
    target — visible on the CRM Deal Status form via frappe_crm_xt's
    fixture-registered `checklist` Table field), or
  - `parenttype='Sales Stage', parentfield='custom_checklist'` (still on
    the source-side Sales Stage doctype which frappe_crm_xt keeps using).

Either way, the rows belong in the new `CRM Deal Status Checklist` table
so the target child doctype is the canonical home. parenttype + parentfield
on each row are preserved verbatim, so the form linkage continues to
resolve.

Idempotent — source `name` is preserved on the target row, so re-runs
hit `ignore_duplicates` and skip.
"""

import click
import frappe


def execute():
	src_dt = "Opportunity Status Checklist"
	tgt_dt = "CRM Deal Status Checklist"

	if not frappe.db.exists("DocType", src_dt):
		return
	if not frappe.db.exists("DocType", tgt_dt):
		return

	src = frappe.qb.DocType(src_dt)
	rows = (
		frappe.qb.from_(src)
		.select(
			src.name,
			src.owner,
			src.creation,
			src.modified,
			src.modified_by,
			src.docstatus,
			src.idx,
			src.parent,
			src.parenttype,
			src.parentfield,
			src.checklist_item,
		)
		.run(as_dict=True)
	)
	if not rows:
		return

	target_cols = [
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"parent",
		"parenttype",
		"parentfield",
		"checklist_item",
	]
	values = [tuple(r[c] for c in target_cols) for r in rows]

	before = frappe.db.count(tgt_dt)

	frappe.db.bulk_insert(tgt_dt, fields=target_cols, values=values, ignore_duplicates=True)
	frappe.db.commit()

	after = frappe.db.count(tgt_dt)
	added = after - before

	if added:
		click.secho(
			f"  migrated {added} row(s) from {src_dt} → {tgt_dt} "
			f"(parenttype/parentfield preserved)",
			fg="green",
		)
	else:
		click.secho(
			f"  {src_dt} → {tgt_dt}: nothing to do ({after} rows already present)",
			fg="cyan",
		)
