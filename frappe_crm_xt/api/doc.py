"""Override of `crm.api.doc.delete_bulk_docs`.

Adds Contact / Address handling to the upstream delete flow:
  - Reverse direction: Dynamic Link rows on Contact / Address pointing back
    at the Lead / Deal.
  - Forward direction: Link fields on the Lead / Deal whose options is
    Contact / Address (stock `address`, custom `customer_address`,
    `custom_vip_contact`, etc. — picked up from `frappe.get_meta` so
    Custom Fields and Property Setters are respected).

`delete_linked=True` hard-deletes them; otherwise the on_trash hook strips
the Dynamic Link back-references and the forward Link field goes away
with the parent doc. Records still referenced from elsewhere raise
LinkExistsError and are kept (just unlinked).
"""

from __future__ import annotations

import frappe
from frappe import _

_LINK_PARENT_DOCTYPES = ("Contact", "Address")
_SUPPORTED_TARGET_DOCTYPES = ("CRM Lead", "CRM Deal")


@frappe.whitelist()
def delete_bulk_docs(doctype: str, items: str | list, delete_linked: bool = False):
	from crm.api.doc import delete_bulk_docs as upstream_delete_bulk_docs

	if not doctype:
		frappe.throw(_("Doctype is required"))
	if not items:
		frappe.throw(_("Items are required"))

	parsed_items = frappe.parse_json(items) if isinstance(items, str) else items
	if not isinstance(parsed_items, list):
		frappe.throw(_("Items must be a list"))

	# frappe-ui's call() sends booleans as strings.
	delete_linked = str(delete_linked).lower() in ("1", "true", "yes")

	if delete_linked and doctype in _SUPPORTED_TARGET_DOCTYPES:
		for name in parsed_items:
			if not name or not frappe.db.exists(doctype, name):
				continue
			if not frappe.has_permission(doctype, ptype="write", doc=name):
				continue
			linked = _collect_linked_records(doctype, name)
			for parent_dt, parent_names in linked.items():
				for parent_name in parent_names:
					_safe_delete(parent_dt, parent_name, doctype, name)

	return upstream_delete_bulk_docs(doctype=doctype, items=parsed_items, delete_linked=delete_linked)


def _collect_linked_records(target_doctype: str, target_name: str) -> dict[str, set[str]]:
	out: dict[str, set[str]] = {dt: set() for dt in _LINK_PARENT_DOCTYPES}

	for parent_dt in _LINK_PARENT_DOCTYPES:
		for parent_name in frappe.get_all(
			"Dynamic Link",
			filters={
				"parenttype": parent_dt,
				"link_doctype": target_doctype,
				"link_name": target_name,
			},
			pluck="parent",
		):
			if parent_name:
				out[parent_dt].add(parent_name)

	link_field_map: dict[str, list[str]] = {}
	for df in frappe.get_meta(target_doctype).fields:
		if df.fieldtype == "Link" and df.options in _LINK_PARENT_DOCTYPES:
			link_field_map.setdefault(df.options, []).append(df.fieldname)

	if link_field_map:
		fieldnames = [fn for fns in link_field_map.values() for fn in fns]
		row = frappe.db.get_value(target_doctype, target_name, fieldnames, as_dict=True) or {}
		for parent_dt, fields in link_field_map.items():
			for fn in fields:
				val = row.get(fn)
				if val:
					out[parent_dt].add(val)

	return out


def _safe_delete(link_parent_doctype: str, parent_name: str, target_doctype: str, target_name: str) -> None:
	if not frappe.db.exists(link_parent_doctype, parent_name):
		return
	if not frappe.has_permission(link_parent_doctype, ptype="delete", doc=parent_name):
		return
	try:
		frappe.delete_doc(
			link_parent_doctype,
			parent_name,
			ignore_permissions=False,
			delete_permanently=True,
		)
	except (frappe.DoesNotExistError, frappe.LinkExistsError) as exc:
		# Other docs still reference this Contact / Address — leave it.
		# on_trash on the parent Lead / Deal still strips its back-reference.
		frappe.log_error(
			f"CRM XT delete_linked: skipped {link_parent_doctype} {parent_name} "
			f"(target={target_doctype} {target_name}): {exc}",
			"CRM XT Delete Hook",
		)
