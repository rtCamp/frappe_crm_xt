"""on_trash for CRM Lead / CRM Deal.

Unlinks back-references that upstream `crm.api.doc.delete_bulk_docs` misses:
  - Dynamic Link rows on Contact / Address pointing at the deleted Lead / Deal.
  - Gmail Thread's `reference_name` (upstream writes `reference_docname` —
    the FCRM Note field — so Gmail Thread silently keeps the dangling link).

Always unlink, never delete. Hard-delete of related Contact / Address is
opt-in through `frappe_crm_xt.api.doc.delete_bulk_docs` (delete_linked=True).
"""

from __future__ import annotations

import frappe

_LINK_PARENT_DOCTYPES = ("Contact", "Address")
_GMAIL_THREAD_DOCTYPE = "Gmail Thread"


def on_trash(doc, method=None):
	target_doctype = doc.doctype
	target_name = doc.name
	if not target_name:
		return

	for parent_dt in _LINK_PARENT_DOCTYPES:
		_unlink_dynamic_links(parent_dt, target_doctype, target_name)

	_clear_gmail_thread_references(target_doctype, target_name)


def _unlink_dynamic_links(link_parent_doctype: str, target_doctype: str, target_name: str) -> None:
	parents = frappe.get_all(
		"Dynamic Link",
		filters={
			"parenttype": link_parent_doctype,
			"link_doctype": target_doctype,
			"link_name": target_name,
		},
		pluck="parent",
	)
	for parent_name in {p for p in parents if p}:
		if not frappe.db.exists(link_parent_doctype, parent_name):
			continue
		try:
			parent_doc = frappe.get_doc(link_parent_doctype, parent_name)
			parent_doc.links = [
				link
				for link in (parent_doc.links or [])
				if not (link.link_doctype == target_doctype and link.link_name == target_name)
			]
			# Caller already passed delete-perm on the Lead / Deal — we're just
			# stripping a back-reference, so skip the perm check on Contact / Address.
			parent_doc.save(ignore_permissions=True)
		except (frappe.DoesNotExistError, frappe.ValidationError) as exc:
			frappe.log_error(
				f"CRM XT on_trash unlink: {link_parent_doctype} {parent_name} "
				f"<- {target_doctype} {target_name}: {exc}",
				"CRM XT Delete Hook",
			)


def _clear_gmail_thread_references(target_doctype: str, target_name: str) -> None:
	if not frappe.db.exists("DocType", _GMAIL_THREAD_DOCTYPE):
		return

	thread_names = frappe.get_all(
		_GMAIL_THREAD_DOCTYPE,
		filters={"reference_doctype": target_doctype, "reference_name": target_name},
		pluck="name",
	)
	for thread_name in thread_names:
		# db.set_value rather than get_doc().save() — Gmail Thread's validate
		# hook re-resolves references on save, which would undo this clear.
		frappe.db.set_value(
			_GMAIL_THREAD_DOCTYPE,
			thread_name,
			{"reference_doctype": "", "reference_name": ""},
			update_modified=False,
		)
