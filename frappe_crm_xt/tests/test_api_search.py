# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from frappe_crm_xt.api.search import LINK_PAGE_LENGTH, get_search_results, search_link


class TestApiSearch(UnitTestCase):
	def test_search_link_defaults_to_link_page_length(self):
		"""search_link with page_length=None returns at most LINK_PAGE_LENGTH rows"""
		rows = search_link(doctype="User", txt="", page_length=None)

		self.assertLessEqual(len(rows), LINK_PAGE_LENGTH)

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
