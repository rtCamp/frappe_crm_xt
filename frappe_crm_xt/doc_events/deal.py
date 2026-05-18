"""Doc-event handlers for CRM Deal — auto-create checklist tasks.

When a deal's `status` or `sales_stage` changes (or on insert), create a
CRM Task containing the checklist items defined on the corresponding
`CRM Deal Status` or `Sales Stage` row. Mirrors rtCamp/next_crm's
behaviour for Opportunity, retargeted at CRM Deal — both the status
and the stage checklists live in `tabCRM Deal Status Checklist` (see
the `migrate_opportunity_status_checklist` patch + the Sales Stage
custom_checklist options override in setup/custom_fields.json).
"""

from __future__ import annotations

import frappe
from frappe import _


def before_save(doc, method=None):
	current_status = frappe.db.get_value("CRM Deal", doc.name, "status")
	current_stage = frappe.db.get_value("CRM Deal", doc.name, "sales_stage")
	if not current_status and not current_stage:
		# Brand-new record — after_insert handles it
		return

	if doc.status != current_status:
		create_checklist(doc, field="status", value=doc.status)
	if doc.sales_stage != current_stage:
		create_checklist(doc, field="sales_stage", value=doc.sales_stage)


def after_insert(doc, method=None):
	create_checklist(doc, field="status", value=doc.status)
	create_checklist(doc, field="sales_stage", value=doc.sales_stage)


# ─── internal ────────────────────────────────────────────────────────────────

# field → checklist parenttype on tabCRM Deal Status Checklist
_PARENTTYPE_FOR = {
	"status": "CRM Deal Status",
	"sales_stage": "Sales Stage",
}


def create_checklist(doc, field=None, value=None):
	if not field or not value:
		return

	parenttype = _PARENTTYPE_FOR.get(field)
	if not parenttype:
		return

	checklist_items = frappe.get_all(
		"CRM Deal Status Checklist",
		filters={"parent": value, "parenttype": parenttype},
		fields=["checklist_item"],
		pluck="checklist_item",
		ignore_permissions=True,
	)
	if not checklist_items:
		return

	title = _("Checklist for {0}").format(value)

	# Idempotency: don't recreate when an active task with the same title
	# already exists on this deal.
	existing = frappe.get_all(
		"CRM Task",
		filters={
			"reference_doctype": "CRM Deal",
			"reference_docname": doc.name,
			"title": title,
			"status": ["not in", ["Done", "Canceled"]],
		},
		limit=1,
		ignore_permissions=True,
	)
	if existing:
		return

	items_html = "".join(
		f'<li data-list="unchecked">{frappe.utils.escape_html(item)}</li>'
		for item in checklist_items
	)
	description = f'<div class="ql-editor read-mode"><ol>{items_html}</ol></div>'

	frappe.get_doc(
		{
			"doctype": "CRM Task",
			"title": title,
			"description": description,
			"reference_doctype": "CRM Deal",
			"reference_docname": doc.name,
			"assigned_to": doc.deal_owner or frappe.session.user,
			"status": "Todo",
		}
	).insert(ignore_permissions=True)
