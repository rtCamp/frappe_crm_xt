# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.api.activity import (
	_deferred_version_grouping,
	_event_participant_emails,
	_event_to_activity,
	_group_versions,
	_note_to_activity,
	_resolve_reference_doctype,
	_task_to_activity,
	get_activities,
	get_latest_activity,
)


class TestApiActivity(IntegrationTestCase):
	# ─── public entry points ───────────────────────────────────────────────────

	def test_get_activities_returns_five_tuple(self):
		"""get_activities returns the (activities, calls, notes, tasks, attachments) 5-tuple"""
		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)

		result = get_activities(deal.name)

		self.assertEqual(len(result), 5)
		# Each element of the tuple is a list the frontend iterates over.
		for component in result:
			self.assertIsInstance(component, list)

	def test_get_latest_activity_returns_none_or_dict(self):
		"""get_latest_activity returns None (or a dict) for a deal with no activity"""
		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)

		out = get_latest_activity(deal.name)

		self.assertTrue(out is None or isinstance(out, dict))

	# ─── _resolve_reference_doctype ────────────────────────────────────────────

	def test_resolve_returns_crm_deal(self):
		"""_resolve_reference_doctype identifies CRM Deal names"""
		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)

		self.assertEqual(_resolve_reference_doctype(deal.name), "CRM Deal")

	def test_resolve_returns_crm_lead(self):
		"""_resolve_reference_doctype identifies CRM Lead names"""
		lead = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": f"XT-Resolve-{frappe.generate_hash(length=6)}"}
		).insert(ignore_permissions=True)

		self.assertEqual(_resolve_reference_doctype(lead.name), "CRM Lead")

	def test_resolve_returns_none_for_unknown(self):
		"""_resolve_reference_doctype returns None when the name matches no CRM doctype"""
		self.assertIsNone(_resolve_reference_doctype(f"XT-NoSuch-{frappe.generate_hash(length=8)}"))

	# ─── _event_to_activity ────────────────────────────────────────────────────

	def test_event_to_activity_with_full_data(self):
		"""_event_to_activity builds a properly-shaped dict"""
		out = _event_to_activity(
			{
				"name": "EV1",
				"subject": "Kickoff",
				"starts_on": datetime(2025, 1, 1, 10, 30),
				"owner": "user@example.com",
				"creation": datetime(2025, 1, 1, 10, 0),
			},
			is_lead=True,
		)

		self.assertEqual(out["activity_type"], "added")
		self.assertEqual(out["owner"], "user@example.com")
		self.assertEqual(out["data"]["field"], "event")
		self.assertEqual(out["data"]["field_label"], "Event")
		self.assertTrue(out["data"]["value"].startswith("Kickoff"))
		self.assertIn("·", out["data"]["value"])
		self.assertTrue(out["is_lead"])

	def test_event_to_activity_without_starts_on(self):
		"""When starts_on is missing, value is just the subject (no separator)"""
		out = _event_to_activity({"subject": "Bare"}, is_lead=False)

		self.assertEqual(out["data"]["value"], "Bare")
		self.assertFalse(out["is_lead"])

	def test_event_to_activity_subject_fallback(self):
		"""Missing subject falls back to 'Untitled event'"""
		out = _event_to_activity({}, is_lead=False)

		self.assertIn("Untitled event", out["data"]["value"])
		self.assertEqual(out["owner"], "Administrator")

	# ─── _note_to_activity ─────────────────────────────────────────────────────

	def test_note_to_activity_uses_posting_datetime(self):
		"""_note_to_activity stamps creation with posting_datetime when provided"""
		posting = datetime(2025, 6, 1, 12, 0)
		out = _note_to_activity({"title": "My Note", "creation": "1999-01-01"}, posting, is_lead=True)

		self.assertEqual(out["creation"], posting)
		self.assertEqual(out["data"]["value"], "My Note")
		self.assertEqual(out["data"]["field"], "note")
		self.assertTrue(out["is_lead"])

	def test_note_to_activity_falls_back_to_creation(self):
		"""When posting_datetime is None, creation flows through"""
		out = _note_to_activity({"title": "N", "creation": "2024-01-01"}, None, is_lead=False)

		self.assertEqual(out["creation"], "2024-01-01")
		self.assertFalse(out["is_lead"])

	def test_note_to_activity_title_fallback(self):
		"""Missing title falls back to 'Untitled note'"""
		out = _note_to_activity({}, None, is_lead=False)

		self.assertEqual(out["data"]["value"], "Untitled note")
		self.assertEqual(out["owner"], "Administrator")

	# ─── _task_to_activity ─────────────────────────────────────────────────────

	def test_task_to_activity_owner_override(self):
		"""_task_to_activity uses the supplied owner over the task's own owner"""
		out = _task_to_activity(
			{"title": "T", "owner": "task_owner@example.com"}, "override@example.com", True
		)

		self.assertEqual(out["owner"], "override@example.com")
		self.assertEqual(out["data"]["field"], "task")
		self.assertEqual(out["data"]["value"], "T")
		self.assertTrue(out["is_lead"])

	def test_task_to_activity_fallbacks(self):
		"""Missing owner and title fall back to defaults"""
		out = _task_to_activity({}, None, False)

		self.assertEqual(out["owner"], "Administrator")
		self.assertEqual(out["data"]["value"], "Untitled task")

	# ─── version grouping ──────────────────────────────────────────────────────

	@staticmethod
	def _row(owner, label, value, minute, activity_type="added"):
		return {
			"activity_type": activity_type,
			"creation": datetime(2026, 1, 1, 10, minute),
			"owner": owner,
			"data": {"field_label": label, "value": value},
		}

	def test_task_run_collapses_into_one_expandable_row(self):
		"""Consecutive same-owner rows fold into one 'Show +N changes' entry"""
		rows = [self._row("wp@example.com", "Task", f"Task {i}", i) for i in range(5)]

		out = _group_versions(rows)

		self.assertEqual(len(out), 1)
		# The frontend renders "Show +{len(other_versions) + 1} changes from <user>".
		self.assertEqual(len(out[0]["other_versions"]), 4)
		self.assertEqual(out[0]["owner"], "wp@example.com")

	def test_different_owners_are_not_merged(self):
		"""A run by another owner starts its own group"""
		rows = [
			self._row("wp@example.com", "Task", "A", 0),
			self._row("wp@example.com", "Task", "B", 1),
			self._row("bob@example.com", "Task", "C", 2),
		]

		out = _group_versions(rows)

		self.assertEqual(len(out), 2)
		self.assertEqual(out[0]["owner"], "wp@example.com")
		self.assertEqual(len(out[0]["other_versions"]), 1)
		self.assertNotIn("other_versions", out[1])

	def test_lone_row_stays_ungrouped(self):
		"""A single activity keeps its detailed one-liner"""
		out = _group_versions([self._row("wp@example.com", "Task", "Solo", 0)])

		self.assertEqual(len(out), 1)
		self.assertNotIn("other_versions", out[0])
		self.assertEqual(out[0]["data"]["value"], "Solo")

	def test_non_version_activities_pass_through(self):
		"""Comments and emails are never folded into a version group"""
		rows = [
			self._row("wp@example.com", "Task", "A", 0),
			self._row("wp@example.com", None, None, 1, activity_type="comment"),
		]

		out = _group_versions(rows)

		self.assertIn("comment", [r["activity_type"] for r in out])

	def test_deferred_grouping_restores_upstream(self):
		"""The context manager puts crm's real grouper back afterwards"""
		import crm.api.activities as upstream

		original = upstream.handle_multiple_versions
		with _deferred_version_grouping():
			self.assertIsNot(upstream.handle_multiple_versions, original)
		self.assertIs(upstream.handle_multiple_versions, original)

	def test_deferred_grouping_restores_on_error(self):
		"""An exception inside the block still restores the real grouper"""
		import crm.api.activities as upstream

		original = upstream.handle_multiple_versions
		with self.assertRaises(ValueError), _deferred_version_grouping():
			raise ValueError("boom")
		self.assertIs(upstream.handle_multiple_versions, original)

	def test_task_burst_groups_end_to_end(self):
		"""A real deal with a batch of tasks yields one collapsible row"""
		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)
		for i in range(5):
			frappe.get_doc(
				{
					"doctype": "CRM Task",
					"title": f"Bulk task {i}",
					"reference_doctype": "CRM Deal",
					"reference_docname": deal.name,
				}
			).insert(ignore_permissions=True)

		activities, *_ = get_activities(deal.name)

		# `creation` rows carry a plain string in `data`, so guard the lookup.
		def is_task_row(activity):
			data = activity.get("data")
			return isinstance(data, dict) and data.get("field_label") == "Task"

		task_rows = [a for a in activities if is_task_row(a)]
		self.assertEqual(len(task_rows), 1, "the 5 tasks should collapse into one row")
		self.assertEqual(len(task_rows[0]["other_versions"]), 4)
		# Every task is still reachable once expanded.
		titles = [task_rows[0]["data"]["value"]] + [
			o["data"]["value"] for o in task_rows[0]["other_versions"]
		]
		self.assertCountEqual(titles, [f"Bulk task {i}" for i in range(5)])

	# ─── _event_participant_emails ─────────────────────────────────────────────

	def test_event_participant_emails_empty_for_unknown(self):
		"""_event_participant_emails returns '' for an event with no participants"""
		self.assertEqual(_event_participant_emails(f"XT-NoEvent-{frappe.generate_hash(length=8)}"), "")
