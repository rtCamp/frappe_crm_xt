# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.doc_events.deal import create_checklist, validate, validate_probability


class TestDealEvents(IntegrationTestCase):
	def test_probability_within_bounds(self):
		"""validate_probability accepts 0, 50 and 100"""
		for value in (0, 50, 100):
			validate_probability(frappe._dict(probability=value))

	def test_probability_below_zero(self):
		"""validate_probability rejects negative values"""
		with self.assertRaises(frappe.ValidationError):
			validate_probability(frappe._dict(probability=-1))

	def test_probability_above_hundred(self):
		"""validate_probability rejects values above 100"""
		with self.assertRaises(frappe.ValidationError):
			validate_probability(frappe._dict(probability=150))

	def test_probability_missing_treated_as_zero(self):
		"""validate_probability treats missing field as 0 (in-range)"""
		validate_probability(frappe._dict())

	def test_validate_delegates_to_probability(self):
		"""validate() raises on out-of-range probability (smoke test through public entry)"""
		with self.assertRaises(frappe.ValidationError):
			validate(frappe._dict(probability=200))

	def test_create_checklist_no_field(self):
		"""create_checklist is a no-op when field or value is falsy"""
		doc = frappe._dict(name="XT-NOOP", deal_owner=None)
		create_checklist(doc)
		create_checklist(doc, field="status")
		create_checklist(doc, field=None, value="Won")

	def test_create_checklist_unknown_field(self):
		"""create_checklist is a no-op for fields it does not map"""
		doc = frappe._dict(name="XT-NOOP", deal_owner=None)
		create_checklist(doc, field="not_a_real_field", value="anything")

	def test_create_checklist_no_matching_items(self):
		"""create_checklist creates no CRM Task when the checklist parent has no rows"""
		# Use a status name guaranteed not to have a checklist
		marker = f"XT-Deal-{frappe.generate_hash(length=8)}"
		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)
		create_checklist(
			frappe._dict(name=deal.name, deal_owner=None),
			field="status",
			value=marker,
		)
		# Filter on the marker title so the app's own after_insert checklist task
		# (created for the default deal status) doesn't make this non-deterministic.
		tasks = frappe.get_all(
			"CRM Task",
			filters={
				"reference_doctype": "CRM Deal",
				"reference_docname": deal.name,
				"title": f"Checklist for {marker}",
			},
			pluck="name",
		)
		self.assertEqual(tasks, [])
