"""
Doc-event handlers for CRM Deal.

When a deal's status changes, create a CRM Task containing the checklist
items defined on the new CRM Deal Status record (if any).  Mirrors the
behaviour of rtCamp/next_crm for Opportunity.
"""

from __future__ import annotations

import frappe
from frappe import _


def before_save(doc, method=None):
	current_status = frappe.db.get_value("CRM Deal", doc.name, "status")
	if current_status is None:
		# new record — handled by after_insert
		return
	if doc.status != current_status:
		_create_checklist_task(doc)


def after_insert(doc, method=None):
	_create_checklist_task(doc)


# ─── internal ─────────────────────────────────────────────────────────────────


def _create_checklist_task(doc):
	"""
	Look up CRM Deal Status Checklist items for ``doc.status`` and, if any
	exist, create a CRM Task assigned to the deal owner.  Idempotent: skips
	creation when an open task with the same title already exists.
	"""
	checklist_items = frappe.get_all(
		"CRM Deal Status Checklist",
		filters={"parent": doc.status, "parenttype": "CRM Deal Status"},
		fields=["checklist_item"],
		pluck="checklist_item",
		ignore_permissions=True,
	)
	if not checklist_items:
		return

	title = _("Checklist for {0}").format(doc.status)

	# Idempotency: skip if an active task with this title already exists
	existing = frappe.get_all(
		"CRM Task",
		filters={
			"reference_doctype": "CRM Deal",
			"reference_docname": doc.name,
			"title": title,
			"status": ["not in", ["Done", "Cancelled"]],
		},
		limit=1,
		ignore_permissions=True,
	)
	if existing:
		return

	# Build a Quill-compatible unchecked list
	items_html = "".join(
		f'<li data-list="unchecked">{frappe.utils.escape_html(item)}</li>' for item in checklist_items
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
