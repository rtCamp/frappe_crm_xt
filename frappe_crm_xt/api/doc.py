"""Override of `crm.api.doc.get_linked_docs_of_document`.

Hides Contact / Address / Gmail Thread from the linked-docs modal when
the parent is a CRM Lead or CRM Deal. Upstream's unlink flow doesn't
work for these doctypes (writes the wrong field name), so showing them
in the modal just gives users a broken "Unlink" button.

We don't lose any cleanup — the matching `ignore_links_on_delete` hook
plus the `on_trash` handler in `doc_events.lead_deal_delete` strip the
back-references automatically when the parent is deleted. Users never
have to manually unlink these.
"""

from __future__ import annotations

import frappe

_HIDDEN_FROM_MODAL = frozenset({"Contact", "Address", "Gmail Thread"})
_SUPPORTED_TARGET_DOCTYPES = frozenset({"CRM Lead", "CRM Deal"})


@frappe.whitelist()
def get_linked_docs_of_document(doctype: str, docname: str):
	from crm.api.doc import get_linked_docs_of_document as upstream

	rows = upstream(doctype=doctype, docname=docname) or []
	if doctype not in _SUPPORTED_TARGET_DOCTYPES:
		return rows

	return [
		row
		for row in rows
		if row.get("reference_doctype") not in _HIDDEN_FROM_MODAL and row.get("doc") not in _HIDDEN_FROM_MODAL
	]
