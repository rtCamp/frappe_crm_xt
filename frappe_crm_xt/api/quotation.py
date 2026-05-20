from __future__ import annotations

import frappe


@frappe.whitelist()
def update_missing_values(source_name: str) -> dict:
	"""Return items + currency for the CRM Deal → Quotation auto-fill (public/js/quotation_auto_items.js)."""
	deal = frappe.get_cached_doc("CRM Deal", source_name)

	candidate_codes = {row.product_code for row in deal.products if row.product_code}

	# Confirm which CRM Products have a matching ERPNext Item — only those
	# get `item_code` set on the Quotation row; the rest fall back to
	# item_name/description so the user can resolve the Item manually.
	existing_items: set[str] = set()
	if candidate_codes:
		existing_items = set(
			frappe.get_all(
				"Item",
				filters={"item_code": ("in", list(candidate_codes))},
				pluck="item_code",
			)
		)

	# Pull CRM Product descriptions in one round-trip — used as a fallback
	# when item_code is unresolved (otherwise ERPNext auto-fills description
	# from the Item master).
	descriptions: dict[str, str] = {}
	if candidate_codes:
		descriptions = {
			p["name"]: p["description"]
			for p in frappe.get_all(
				"CRM Product",
				filters={"name": ("in", list(candidate_codes))},
				fields=["name", "description"],
			)
		}

	items: list[dict] = []
	for row in deal.products:
		item_code = row.product_code if row.product_code in existing_items else None
		items.append(
			{
				"item_code": item_code,
				"item_name": row.product_name or row.product_code,
				"description": descriptions.get(row.product_code) or row.product_name or row.product_code,
				"qty": row.get("qty") or 1,
				"rate": row.get("rate") or 0,
				"uom": row.get("uom") or "Nos",
				"discount_percentage": row.get("discount_percentage") or 0,
				"discount_amount": row.get("discount_amount") or 0,
			}
		)

	return {
		"items": items,
		"currency": deal.currency,
	}
