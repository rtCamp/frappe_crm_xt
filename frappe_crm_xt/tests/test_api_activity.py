# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase

from frappe_crm_xt.api.activity import (
	_event_participant_emails,
	_event_to_activity,
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

	# ─── _event_participant_emails ─────────────────────────────────────────────

	def test_event_participant_emails_empty_for_unknown(self):
		"""_event_participant_emails returns '' for an event with no participants"""
		self.assertEqual(_event_participant_emails(f"XT-NoEvent-{frappe.generate_hash(length=8)}"), "")
