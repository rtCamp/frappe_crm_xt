# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from frappe_crm_xt.api.sidebar import _sanitise, get_sidebar_items


class TestApiSidebar(UnitTestCase):
	def test_get_sidebar_items_returns_list(self):
		"""get_sidebar_items returns a list of dicts gathered from hooks"""
		items = get_sidebar_items()

		self.assertIsInstance(items, list)
		for item in items:
			self.assertIsInstance(item, dict)

	def test_get_sidebar_items_includes_list_views_group(self):
		"""The List Views group declared in hooks.py is present and contains its children"""
		items = get_sidebar_items()

		groups = [i for i in items if i.get("type") == "group" and i.get("label") == "List Views"]
		self.assertTrue(groups, "Expected a 'List Views' group from frappe_crm_xt hooks")
		group = groups[0]
		child_labels = [c.get("label") for c in group.get("items", [])]
		self.assertIn("Reports", child_labels)
		self.assertIn("Converted Leads", child_labels)

	def test_sanitise_separator_drops_everything_else(self):
		"""Sanitising a separator collapses to just {'type': 'separator'}"""
		out = _sanitise({"type": "separator", "label": "ignored", "icon": "ignored"})

		self.assertEqual(out, {"type": "separator"})

	def test_sanitise_strips_unknown_keys(self):
		"""Unknown keys are dropped from list_view items"""
		out = _sanitise(
			{
				"type": "list_view",
				"label": "Reports",
				"doctype": "Report",
				"icon": "list",
				"unknown_key": "should be removed",
				"another": 42,
			}
		)

		self.assertEqual(out["type"], "list_view")
		self.assertEqual(out["label"], "Reports")
		self.assertEqual(out["doctype"], "Report")
		self.assertNotIn("unknown_key", out)
		self.assertNotIn("another", out)

	def test_sanitise_group_recurses(self):
		"""A group's child items are recursively sanitised"""
		out = _sanitise(
			{
				"type": "group",
				"label": "Group",
				"items": [
					{"type": "list_view", "label": "L1", "doctype": "DT", "junk": True},
					{"type": "separator"},
				],
			}
		)

		self.assertEqual(out["type"], "group")
		self.assertEqual(len(out["items"]), 2)
		self.assertNotIn("junk", out["items"][0])
		self.assertEqual(out["items"][1], {"type": "separator"})

	def test_sanitise_drops_invalid_default_filters(self):
		"""default_filters that aren't a dict are dropped"""
		out = _sanitise(
			{"type": "list_view", "label": "X", "doctype": "DT", "default_filters": ["not", "a", "dict"]}
		)

		self.assertNotIn("default_filters", out)

	def test_sanitise_normalises_fields_to_str_list(self):
		"""fields gets coerced to a list of strings"""
		out = _sanitise({"type": "list_view", "label": "X", "doctype": "DT", "fields": ["a", 1, "b"]})

		self.assertEqual(out["fields"], ["a", "1", "b"])

	def test_sanitise_drops_fields_when_not_listy(self):
		"""fields that is not a list/tuple is removed"""
		out = _sanitise({"type": "list_view", "label": "X", "doctype": "DT", "fields": "not-a-list"})

		self.assertNotIn("fields", out)

	def test_sanitise_default_sort_normalisation(self):
		"""default_sort with a field is normalised; missing 'field' or non-dict is dropped"""
		ok = _sanitise(
			{
				"type": "list_view",
				"label": "X",
				"doctype": "DT",
				"default_sort": {"field": "creation", "dir": "ASC"},
			}
		)
		self.assertEqual(ok["default_sort"], {"field": "creation", "dir": "asc"})

		bad_no_field = _sanitise(
			{"type": "list_view", "label": "X", "doctype": "DT", "default_sort": {"dir": "asc"}}
		)
		self.assertNotIn("default_sort", bad_no_field)

		bad_invalid_dir_defaults_desc = _sanitise(
			{
				"type": "list_view",
				"label": "X",
				"doctype": "DT",
				"default_sort": {"field": "name", "dir": "sideways"},
			}
		)
		self.assertEqual(bad_invalid_dir_defaults_desc["default_sort"]["dir"], "desc")
