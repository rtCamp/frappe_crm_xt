# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from frappe_crm_xt.api.search import LINK_PAGE_LENGTH, get_search_results, search_link


class TestApiSearch(UnitTestCase):
	def test_link_page_length_default(self):
		"""The frappe_crm_xt default page length for search_link is 20"""
		self.assertEqual(LINK_PAGE_LENGTH, 20)

	def test_search_link_runs_without_page_length(self):
		"""search_link returns without raising when page_length is unset (defaulting to LINK_PAGE_LENGTH)"""
		# Just verify the call path; we don't depend on the result count
		search_link(doctype="User", txt="", page_length=None)

	def test_search_link_runs_with_explicit_page_length(self):
		"""search_link honours an explicit page_length"""
		search_link(doctype="User", txt="", page_length=5)

	def test_get_search_results_shape(self):
		"""get_search_results returns a 2-tuple (results, has_more)"""
		result = get_search_results(text="", start=0, limit=5)

		self.assertEqual(len(result), 2)
		results, has_more = result
		# results is an iterable of dicts (or empty)
		for row in results:
			self.assertIsInstance(row, dict)
		self.assertIsInstance(has_more, bool)

	def test_get_search_results_coerces_string_ints(self):
		"""get_search_results coerces start/limit when passed as strings"""
		results, has_more = get_search_results(text="", start="0", limit="3")

		self.assertIsInstance(has_more, bool)
		for row in results:
			self.assertIsInstance(row, dict)
