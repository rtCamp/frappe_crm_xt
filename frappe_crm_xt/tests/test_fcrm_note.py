# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import add_to_date, get_datetime, now_datetime

from frappe_crm_xt.doc_events.fcrm_note import validate, validate_posting_datetime


class TestFCRMNoteEvents(UnitTestCase):
	def test_missing_posting_datetime_is_auto_filled(self):
		"""validate_posting_datetime defaults to now when the field is empty"""
		doc = frappe._dict()
		validate_posting_datetime(doc)

		self.assertTrue(doc.posting_datetime)
		# Within a one-minute window of "now"
		delta = (now_datetime() - get_datetime(doc.posting_datetime)).total_seconds()
		self.assertLess(abs(delta), 60)

	def test_past_posting_datetime_passes(self):
		"""validate_posting_datetime accepts a past datetime"""
		past = add_to_date(now_datetime(), days=-1)
		doc = frappe._dict(posting_datetime=past)

		validate_posting_datetime(doc)

		self.assertEqual(doc.posting_datetime, past)

	def test_future_posting_datetime_rejected(self):
		"""validate_posting_datetime raises ValidationError for future datetimes"""
		future = add_to_date(now_datetime(), days=1)
		doc = frappe._dict(posting_datetime=future)

		with self.assertRaises(frappe.ValidationError):
			validate_posting_datetime(doc)

	def test_existing_posting_datetime_preserved(self):
		"""validate_posting_datetime does not overwrite a supplied past value"""
		past = add_to_date(now_datetime(), hours=-2)
		doc = frappe._dict(posting_datetime=past)

		validate_posting_datetime(doc)

		self.assertEqual(doc.posting_datetime, past)

	def test_validate_delegates_to_posting_datetime(self):
		"""validate() raises for future datetimes (smoke test through public entry)"""
		future = add_to_date(now_datetime(), days=1)
		with self.assertRaises(frappe.ValidationError):
			validate(frappe._dict(posting_datetime=future))
