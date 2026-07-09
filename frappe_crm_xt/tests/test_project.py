# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from frappe_crm_xt.doc_events.project import after_insert


class TestProjectEvents(UnitTestCase):
	def test_after_insert_no_custom_deal(self):
		"""after_insert is a no-op when the project has no custom_deal link"""
		after_insert(frappe._dict())

	def test_after_insert_custom_deal_none(self):
		"""after_insert is a no-op when custom_deal is explicitly None"""
		after_insert(frappe._dict(custom_deal=None))

	def test_after_insert_missing_deal_swallows_error(self):
		"""after_insert swallows DoesNotExistError when custom_deal points to a missing CRM Deal"""
		missing = f"XT-Deal-Missing-{frappe.generate_hash(length=8)}"
		# Should not raise
		after_insert(frappe._dict(custom_deal=missing))
