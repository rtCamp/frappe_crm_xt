"""
Contact-lookup endpoints used by the Gmail Add-on.

Mirrors the three endpoints the legacy `next_crm` add-on consumes:

  - get_contact_by_email(email)        → contact details
  - get_linked_leads(contact)          → CRM Leads linked to a contact
  - get_linked_opportunities(contact)  → CRM Deals linked to a contact

The legacy add-on calls these via Bearer-token auth against a Frappe site;
keeping the URL paths under `frappe_crm_xt.api.contact.*` means the add-on
only needs a one-line `next_crm` → `frappe_crm_xt` swap in its Constants
file (no UI / shape changes).

FCRM-to-NextCRM doctype mapping (so the JSON shapes match what the add-on
already renders):

  Lead → CRM Lead
  Opportunity → CRM Deal
  Contact → Contact (unchanged)

Field renames are aliased server-side so the response keys stay the same as
the legacy responses: e.g. `opportunity_owner` ← CRM Deal.deal_owner,
`opportunity_amount` ← CRM Deal.expected_deal_value, etc.
"""

from __future__ import annotations

import frappe


@frappe.whitelist()
def get_contact_by_email(email: str) -> dict | None:
	"""Return the first Contact whose primary email matches `email`."""
	if not email:
		return None

	# Frappe Contact has email in a child table (`Contact Email`).
	# Look up via the child table, then load the parent Contact.
	parents = frappe.get_all(
		"Contact Email",
		filters={"email_id": email.strip()},
		pluck="parent",
		limit=1,
	)
	if not parents:
		return None

	doc = frappe.get_doc("Contact", parents[0])
	address = _resolve_primary_address(doc)

	return {
		"name": doc.name,
		"full_name": doc.full_name or "",
		"designation": doc.designation or "",
		"mobile_no": _primary_phone(doc) or "",
		"email_id": _primary_email(doc) or email,
		"address": address,
	}


@frappe.whitelist()
def get_linked_leads(contact: str) -> list[dict]:
	"""Return CRM Leads that reference the given Contact docname.

	A CRM Lead has no built-in `contact` link in stock FCRM, but it does
	track contacts via the `Contacts` child table (`CRM Contacts`). We look
	up rows where `contact == <docname>` and load their parent Lead.
	"""
	if not contact:
		return []

	lead_names = frappe.get_all(
		"CRM Contacts",
		filters={"parenttype": "CRM Lead", "contact": contact},
		pluck="parent",
	)
	# Fallback: also match by email (covers leads that were never linked
	# to a Contact record but share an address with this Contact).
	email = frappe.db.get_value("Contact", contact, "email_id")
	if email:
		extra = frappe.get_all(
			"CRM Lead",
			filters={"email": email},
			pluck="name",
		)
		lead_names = list({*lead_names, *extra})

	if not lead_names:
		return []

	leads = frappe.get_all(
		"CRM Lead",
		filters={"name": ["in", lead_names]},
		fields=[
			"name",
			"organization as company_name",
			"organization as organization_name",
			"status",
			"email as email_id",
			"mobile_no",
			"custom_description as description",
			"lead_owner",
		],
		order_by="modified desc",
		limit=50,
	)
	return leads


@frappe.whitelist()
def get_linked_deals(contact: str) -> list[dict]:
	"""Return CRM Deals linked to the given Contact (mapped to the legacy
	`opportunity_*` shape so the add-on renders them unchanged)."""
	if not contact:
		return []

	deal_names = frappe.get_all(
		"CRM Contacts",
		filters={"parenttype": "CRM Deal", "contact": contact},
		pluck="parent",
	)
	# Fallback by contact link directly on the deal (FCRM has a `contact`
	# Link field on CRM Deal — covers older single-contact deals).
	extra = frappe.get_all(
		"CRM Deal",
		filters={"contact": contact},
		pluck="name",
	)
	deal_names = list({*deal_names, *extra})

	if not deal_names:
		return []

	deals = frappe.get_all(
		"CRM Deal",
		filters={"name": ["in", deal_names]},
		fields=[
			"name",
			"title",
			"custom_description",
			"sales_stage",
			"deal_owner",
			"expected_deal_value",
			"deal_value",
			"currency",
			"modified",
		],
		order_by="modified desc",
		limit=50,
	)
	return deals


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _primary_email(contact_doc) -> str | None:
	for row in contact_doc.get("email_ids") or []:
		if row.is_primary:
			return row.email_id
	# Fall back to the first row if none is flagged primary.
	rows = contact_doc.get("email_ids") or []
	return rows[0].email_id if rows else None


def _primary_phone(contact_doc) -> str | None:
	for row in contact_doc.get("phone_nos") or []:
		if row.is_primary_mobile_no:
			return row.phone
	for row in contact_doc.get("phone_nos") or []:
		if row.is_primary_phone:
			return row.phone
	rows = contact_doc.get("phone_nos") or []
	return rows[0].phone if rows else None


def _resolve_primary_address(contact_doc) -> str:
	"""Return a flat one-line address derived from the contact's primary
	Address record, or an empty string if none is linked."""
	links = [link for link in (contact_doc.get("links") or []) if link.link_doctype == "Address"]
	if not links:
		return "No Address Found"

	address_name = links[0].link_name
	try:
		addr = frappe.get_doc("Address", address_name)
	except frappe.DoesNotExistError:
		return ""

	parts = [
		addr.address_line1,
		addr.address_line2,
		addr.city,
		addr.state,
		addr.pincode,
		addr.country,
	]
	return ", ".join(p for p in parts if p)
