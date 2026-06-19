# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from frappe_crm_xt.api.contact import (
	_build_address_display,
	get_contact_by_email,
	get_crm_summary_by_email,
	get_linked_leads,
)


class TestApiContact(UnitTestCase):
	def tearDown(self) -> None:
		frappe.db.rollback()

	# ─── _build_address_display ────────────────────────────────────────────────

	def test_address_display_for_none(self):
		"""Empty / None address name returns an empty string"""
		self.assertEqual(_build_address_display(None), "")
		self.assertEqual(_build_address_display(""), "")

	def test_address_display_for_missing(self):
		"""Non-existent address name returns an empty string"""
		self.assertEqual(_build_address_display(f"XT-NoAddr-{frappe.generate_hash(length=8)}"), "")

	# ─── get_contact_by_email ──────────────────────────────────────────────────

	def test_get_contact_by_email_empty(self):
		"""Empty email returns None"""
		self.assertIsNone(get_contact_by_email(""))
		self.assertIsNone(get_contact_by_email(None))

	def test_get_contact_by_email_unknown(self):
		"""Unknown email returns None"""
		self.assertIsNone(get_contact_by_email(f"missing-{frappe.generate_hash(length=8)}@example.com"))

	def test_get_contact_by_email_returns_shape(self):
		"""A known email returns a dict with the documented fields"""
		email = f"xt-{frappe.generate_hash(length=8)}@example.com"
		frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "XT Contact",
				"email_ids": [{"email_id": email, "is_primary": 1}],
			}
		).insert(ignore_permissions=True)

		out = get_contact_by_email(email)

		self.assertIsNotNone(out)
		for key in ("name", "full_name", "designation", "mobile_no", "email_id", "address"):
			self.assertIn(key, out)
		self.assertEqual(out["email_id"], email)

	# ─── get_linked_leads ──────────────────────────────────────────────────────

	def test_get_linked_leads_empty_input(self):
		"""Empty contact returns an empty list"""
		self.assertEqual(get_linked_leads(""), [])
		self.assertEqual(get_linked_leads(None), [])

	def test_get_linked_leads_by_shared_email(self):
		"""A Contact and CRM Lead sharing the same email surface in the linked-leads list"""
		email = f"xt-lead-{frappe.generate_hash(length=8)}@example.com"

		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "XT Linked",
				"email_ids": [{"email_id": email, "is_primary": 1}],
			}
		).insert(ignore_permissions=True)
		lead = frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": "XT Lead",
				"email": email,
			}
		).insert(ignore_permissions=True)

		out = get_linked_leads(contact.name)

		lead_names = [row.get("name") for row in out]
		self.assertIn(lead.name, lead_names)

	# ─── get_crm_summary_by_email ──────────────────────────────────────────────

	def test_summary_empty_email(self):
		"""Empty email yields the empty summary shape"""
		out = get_crm_summary_by_email("")

		self.assertEqual(out, {"person": None, "leads": [], "deals": []})

	def test_summary_no_matches(self):
		"""An unknown email yields the empty summary shape"""
		out = get_crm_summary_by_email(f"none-{frappe.generate_hash(length=8)}@example.com")

		self.assertEqual(out, {"person": None, "leads": [], "deals": []})

	def test_summary_lead_only_fallback(self):
		"""An email matching only a CRM Lead populates person from the lead (source='lead')"""
		email = f"xt-leadonly-{frappe.generate_hash(length=8)}@example.com"
		frappe.get_doc(
			{
				"doctype": "CRM Lead",
				"first_name": "XT",
				"last_name": "LeadOnly",
				"email": email,
			}
		).insert(ignore_permissions=True)

		out = get_crm_summary_by_email(email)

		self.assertIsNotNone(out["person"])
		self.assertEqual(out["person"]["source"], "lead")
		self.assertEqual(out["person"]["email_id"], email)
		self.assertEqual(out["deals"], [])
		self.assertTrue(out["leads"])
