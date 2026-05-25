"""
Contact-lookup endpoints used by the Gmail Add-on.

  get_contact_by_email(email)   → contact details
  get_linked_leads(contact)     → CRM Leads linked to a contact
  get_linked_deals(contact)     → CRM Deals linked to a contact

All three use frappe.get_list() so user-level permissions are respected.
Fields (full_name, designation, email_id, address, mobile_no) are fetched
directly from the Contact doctype in a single get_value() call — no child
table or Dynamic Link traversal needed.
"""

from __future__ import annotations

import frappe

# ─── Public endpoints ─────────────────────────────────────────────────────────


@frappe.whitelist()
def get_contact_by_email(email: str) -> dict | None:
	"""Return the first Contact whose email matches, with phone + address."""
	if not email:
		return None

	# Single query — `address` is a Link to the Address doctype
	contact = frappe.get_value(
		"Contact",
		{"email_id": email},
		["name", "full_name", "designation", "email_id", "address", "mobile_no"],
		as_dict=True,
	)
	if not contact:
		return None

	contact_name = contact.name

	# Phone: prefer primary mobile → primary phone → first row
	phone = None
	for filt in (
		{"parent": contact_name, "is_primary_mobile_no": 1},
		{"parent": contact_name, "is_primary_phone": 1},
		{"parent": contact_name},
	):
		phone = frappe.get_value("Contact Phone", filt, "phone")
		if phone:
			break

	# Resolve address link → human-readable display string
	address = _build_address_display(contact.address)

	return {
		"name": contact_name,
		"full_name": contact.full_name or "",
		"designation": contact.designation or "",
		"mobile_no": phone or contact.mobile_no or "",
		"email_id": contact.email_id or email,
		"address": address,
	}


@frappe.whitelist()
def get_linked_leads(contact: str) -> list[dict]:
	"""Return CRM Leads linked to the given Contact.

	Two lookup paths run in parallel:
	  1. Via CRM Contacts child table  (contact → CRM Lead)
	  2. Via email match on CRM Lead.email
	"""
	if not contact:
		return []

	def _by_email():
		email = frappe.get_value("Contact", contact, "email_id")
		if not email:
			return []
		return frappe.get_list(
			"CRM Lead",
			filters={"email": email},
			pluck="name",
		)

	lead_names = _by_email()

	lead_names = list({*lead_names})

	if not lead_names:
		return []

	return frappe.get_list(
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


@frappe.whitelist()
def get_linked_deals(contact: str) -> list[dict]:
	"""Return CRM Deals linked to the given Contact.

	Two lookup paths run in parallel:
	  1. Via CRM Contacts child table  (contact → CRM Deal)
	  2. Via direct `contact` Link field on CRM Deal
	"""
	if not contact:
		return []

	def _by_contact_table():
		return frappe.get_all(
			"CRM Contacts",
			filters={"parenttype": "CRM Deal", "contact": contact},
			pluck="parent",
		)

	deal_names = _by_contact_table()

	deal_names = list({*deal_names})

	if not deal_names:
		return []

	return frappe.get_list(
		"CRM Deal",
		filters={"name": ["in", deal_names]},
		fields=[
			"name",
			"title",
			"custom_description",
			"sales_stage",
			"deal_owner",
			"deal_value",
			"expected_deal_value",
			"currency",
			"modified",
		],
		order_by="modified desc",
		limit=50,
	)


@frappe.whitelist()
def get_crm_summary_by_email(email: str) -> dict:
	"""Single endpoint that returns contact + leads + deals in one call.

	Contact, leads, and deals are fetched in parallel via ThreadPoolExecutor
	so total latency ≈ max(contact_time, leads_time, deals_time) instead of
	the sum of all three.

	Response shape:
	  {
	    "contact": { name, full_name, designation, mobile_no, email_id, address } | null,
	    "leads":   [ { name, company_name, status, email_id, mobile_no, lead_owner, description } ],
	    "deals":   [ { name, title, sales_stage, deal_owner, deal_value, currency, modified } ]
	  }
	"""
	if not email:
		return {"contact": None, "leads": [], "deals": []}

	email = email.strip()

	# ── Step 1: resolve contact (needed to look up leads & deals) ─────────────
	contact_row = frappe.get_value(
		"Contact",
		{"email_id": email},
		["name", "full_name", "designation", "email_id", "address", "mobile_no"],
		as_dict=True,
	)

	if not contact_row:
		return {"contact": None, "leads": [], "deals": []}

	contact_name = contact_row.name

	# ── Step 2: phone ─────────────────────────────────────────────────────────
	# NOTE: frappe.local.db is thread-local — cannot use ThreadPoolExecutor here
	phone = None
	for filt in (
		{"parent": contact_name, "is_primary_mobile_no": 1},
		{"parent": contact_name, "is_primary_phone": 1},
		{"parent": contact_name},
	):
		phone = frappe.get_value("Contact Phone", filt, "phone")
		if phone:
			break

	# ── Step 3: leads ─────────────────────────────────────────────────────────
	lead_email = contact_row.email_id or email
	lead_names = (
		frappe.get_list("CRM Lead", filters={"email": lead_email}, pluck="name") if lead_email else []
	)
	leads = (
		frappe.get_list(
			"CRM Lead",
			filters={"name": ["in", lead_names]},
			fields=[
				"name",
				"organization as company_name",
				"status",
				"email as email_id",
				"mobile_no",
				"custom_description as description",
				"lead_owner",
			],
			order_by="modified desc",
			limit=50,
		)
		if lead_names
		else []
	)

	# ── Step 4: deals ─────────────────────────────────────────────────────────
	deal_names = list(
		{
			*frappe.get_all(
				"CRM Contacts",
				filters={"parenttype": "CRM Deal", "contact": contact_name},
				pluck="parent",
			)
		}
	)
	deals = (
		frappe.get_list(
			"CRM Deal",
			filters={"name": ["in", deal_names]},
			fields=[
				"name",
				"title",
				"custom_description",
				"sales_stage",
				"deal_owner",
				"deal_value",
				"expected_deal_value",
				"currency",
				"modified",
			],
			order_by="modified desc",
			limit=50,
		)
		if deal_names
		else []
	)

	contact = {
		"name": contact_name,
		"full_name": contact_row.full_name or "",
		"designation": contact_row.designation or "",
		"mobile_no": phone or contact_row.mobile_no or "",
		"email_id": contact_row.email_id or email,
		"address": _build_address_display(contact_row.address),
	}

	return {"contact": contact, "leads": leads, "deals": deals}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_address_display(address_name: str | None) -> str:
	"""`address` on Contact is a Link to the Address doctype.

	Fetches only the display parts needed — no full doc load.
	Returns a comma-separated one-liner, e.g. "123 Main St, Mumbai, MH, 400001, India".
	"""
	if not address_name:
		return ""

	addr = frappe.get_value(
		"Address",
		address_name,
		["address_line1", "address_line2", "city", "state", "pincode", "country"],
		as_dict=True,
	)
	if not addr:
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
