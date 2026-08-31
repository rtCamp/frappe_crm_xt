"""
Document Follow API
"""

from __future__ import annotations

import frappe


@frappe.whitelist()
def is_document_followed(doctype: str, doc_name: str):
	"""Check if current user is following a document"""
	return frappe.db.exists(
		"Document Follow",
		{"ref_doctype": doctype, "ref_docname": doc_name, "user": frappe.session.user},
	)


@frappe.whitelist()
def update_follow(doctype: str, doc_name: str, following: bool):
	"""Toggle follow status"""
	from frappe.desk.form.document_follow import follow_document, unfollow_document

	if following:
		follow_document(doctype, doc_name)
	else:
		unfollow_document(doctype, doc_name)

	return 1
