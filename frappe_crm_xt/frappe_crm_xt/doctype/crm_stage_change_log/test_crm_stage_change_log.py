# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe.tests import UnitTestCase

from frappe_crm_xt.frappe_crm_xt.doctype.crm_stage_change_log.crm_stage_change_log import (
	_seconds_between,
	add_stage_change_log,
)


class TestCRMStageChangeLog(UnitTestCase):
	def test_seconds_between_with_datetimes(self):
		"""_seconds_between returns the difference in seconds for datetime inputs"""
		start = datetime(2025, 1, 1, 0, 0, 0)
		end = datetime(2025, 1, 1, 1, 0, 0)

		self.assertEqual(_seconds_between(start, end), 3600.0)

	def test_seconds_between_with_strings(self):
		"""_seconds_between coerces string inputs via get_datetime"""
		self.assertEqual(
			_seconds_between("2025-01-01 00:00:00", "2025-01-01 00:01:00"),
			60.0,
		)

	def test_seconds_between_mixed_inputs(self):
		"""_seconds_between handles a mix of string and datetime inputs"""
		start = "2025-01-01 00:00:00"
		end = datetime(2025, 1, 1, 0, 0, 30)

		self.assertEqual(_seconds_between(start, end), 30.0)

	def test_add_stage_change_log_skips_new_doc(self):
		"""add_stage_change_log is a no-op for an unsaved (new) document"""
		deal = frappe.new_doc("CRM Deal")

		add_stage_change_log(deal)

		self.assertFalse(deal.get("custom_stage_change_log"))
