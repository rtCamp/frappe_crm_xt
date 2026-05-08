"""
Compatibility stubs for crm_erp_bridge API methods.

When crm_erp_bridge is uninstalled but browsers still have its JavaScript cached,
they continue calling crm_erp_bridge.* API endpoints, causing HTTP 417 errors.

These stubs are registered via override_whitelisted_methods in hooks.py so Frappe
routes those requests here instead of trying to import the missing app.
"""

from __future__ import annotations

import frappe


@frappe.whitelist()
def is_document_followed(doctype: str = "", docname: str = "") -> bool:
	"""Return whether the current user follows the given document."""
	if not (doctype and docname):
		return False
	try:
		from frappe.desk.form.document_follow import is_document_followed as _is_followed

		return bool(_is_followed(doctype, docname, frappe.session.user))
	except Exception:
		return False


@frappe.whitelist()
def toggle_document_follow(doctype: str = "", docname: str = "", unfollow: bool = False):
	"""Follow or unfollow the given document for the current user."""
	if not (doctype and docname):
		return
	try:
		from frappe.desk.form.document_follow import update_follow

		update_follow(doctype, docname, not unfollow)
	except Exception:
		pass


@frappe.whitelist()
def link_address_to_doc(address: str = "", doctype: str = "", docname: str = ""):
	"""No-op stub — crm_erp_bridge address linking is not available."""
	return
