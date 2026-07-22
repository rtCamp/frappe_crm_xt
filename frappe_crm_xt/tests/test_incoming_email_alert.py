# Copyright (c) 2026, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_datetime

from frappe_crm_xt.doc_events import incoming_sla as iss

HL = "_Test IEA Holidays"
HOLIDAYS = ("2026-07-18", "2026-07-19", "2026-07-25", "2026-07-26")  # weekends in range


class TestIncomingSlaDue(IntegrationTestCase):
	"""incoming_sla.refresh_incoming_due(deal): maintains custom_incoming_sla_due =
	incoming email time advanced by N working days (holiday-aware), or blank."""

	def setUp(self):
		self.owner = (
			frappe.db.get_value(
				"User",
				{"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
				"name",
			)
			or "Administrator"
		)

		if not frappe.db.exists("Holiday List", HL):
			hl = frappe.get_doc(
				{
					"doctype": "Holiday List",
					"holiday_list_name": HL,
					"from_date": "2026-06-01",
					"to_date": "2026-08-31",
				}
			)
			for d in HOLIDAYS:
				hl.append("holidays", {"holiday_date": d, "description": "t"})
			hl.insert(ignore_permissions=True)

		# Baseline settings (reset before every test since it's a shared Single).
		s = frappe.get_single("CRM XT Settings")
		s.incoming_alert_enabled = 1
		s.incoming_alert_working_days = 1
		s.incoming_alert_unit = "Working Days"
		s.deal_inactivity_use_company_holiday_list = 0
		s.deal_inactivity_holiday_list = HL
		s.deal_inactivity_weekend_holidays = 0
		s.save(ignore_permissions=True)

	def _deal(self, org, incoming=None, response=None, status="Open"):
		d = frappe.get_doc(
			{"doctype": "CRM Deal", "organization_name": org, "status": "Open", "deal_owner": self.owner}
		).insert(ignore_permissions=True)
		if incoming:
			frappe.db.set_value(
				"CRM Deal", d.name, "custom_last_incoming_email_time", incoming, update_modified=False
			)
		if response:
			frappe.db.set_value("CRM Deal", d.name, "last_responded_on", response, update_modified=False)
		if status != "Open":  # bypass hooks (Won/Lost would trigger ERPNext customer creation)
			frappe.db.set_value("CRM Deal", d.name, "status", status, update_modified=False)
		d.reload()
		return d

	def _due(self, name):
		return frappe.db.get_value("CRM Deal", name, "custom_incoming_sla_due")

	def test_sets_due_next_working_day(self):
		d = self._deal("a", incoming="2026-07-20 10:00:00")  # Mon → due Tue same time
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-21 10:00:00"))

	def test_holiday_aware_pushes_past_weekend(self):
		d = self._deal("b", incoming="2026-07-17 09:30:00")  # Fri; 07-18/19 are holidays → due Mon
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-20 09:30:00"))

	def test_multi_working_day_threshold(self):
		s = frappe.get_single("CRM XT Settings")
		s.incoming_alert_working_days = 3
		s.save(ignore_permissions=True)
		d = self._deal("c", incoming="2026-07-16 08:00:00")  # Thu; skip 18/19 → Fri,Mon,Tue = 07-21
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-21 08:00:00"))

	def test_answered_clears_due(self):
		d = self._deal("d", incoming="2026-07-20 10:00:00", response="2026-07-20 12:00:00")
		iss.refresh_incoming_due(d)
		self.assertIsNone(self._due(d.name))

	def test_closed_clears_due(self):
		d = self._deal("e", incoming="2026-07-20 10:00:00", status="Won")
		iss.refresh_incoming_due(d)
		self.assertIsNone(self._due(d.name))

	def test_disabled_clears_due(self):
		d = self._deal("f", incoming="2026-07-20 10:00:00")
		iss.refresh_incoming_due(d)
		self.assertIsNotNone(self._due(d.name))
		s = frappe.get_single("CRM XT Settings")
		s.incoming_alert_enabled = 0
		s.save(ignore_permissions=True)
		d.reload()
		iss.refresh_incoming_due(d)
		self.assertIsNone(self._due(d.name))

	def test_weekend_fallback_without_holiday_list(self):
		s = frappe.get_single("CRM XT Settings")
		s.deal_inactivity_holiday_list = None
		s.deal_inactivity_weekend_holidays = 1
		s.save(ignore_permissions=True)
		d = self._deal("g", incoming="2026-07-17 09:00:00")  # Fri, no HL, weekend fallback → Mon
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-20 09:00:00"))

	def test_hours_mode_plain(self):
		s = frappe.get_single("CRM XT Settings")
		s.incoming_alert_unit = "Hours"
		s.incoming_alert_working_days = 24
		s.save(ignore_permissions=True)
		d = self._deal("i", incoming="2026-07-20 10:00:00")  # Mon +24h = Tue 10:00 (working)
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-21 10:00:00"))

	def test_hours_mode_defers_off_weekend(self):
		s = frappe.get_single("CRM XT Settings")
		s.incoming_alert_unit = "Hours"
		s.incoming_alert_working_days = 24
		s.save(ignore_permissions=True)
		# Fri 10:00 + 24h = Sat 10:00 (holiday) → deferred to Mon 10:00
		d = self._deal("j", incoming="2026-07-17 10:00:00")
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-20 10:00:00"))

	def test_hours_mode_48h_still_defers_to_monday(self):
		s = frappe.get_single("CRM XT Settings")
		s.incoming_alert_unit = "Hours"
		s.incoming_alert_working_days = 48
		s.save(ignore_permissions=True)
		# Fri 10:00 + 48h = Sun 10:00 (holiday) → deferred to Mon 10:00
		d = self._deal("k", incoming="2026-07-17 10:00:00")
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-20 10:00:00"))

	def test_newer_incoming_pushes_due(self):
		d = self._deal("h", incoming="2026-07-20 10:00:00")
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-21 10:00:00"))
		# a newer incoming email advances the due to the next working day after it
		frappe.db.set_value(
			"CRM Deal",
			d.name,
			"custom_last_incoming_email_time",
			"2026-07-21 15:00:00",
			update_modified=False,
		)
		d.reload()
		iss.refresh_incoming_due(d)
		self.assertEqual(get_datetime(self._due(d.name)), get_datetime("2026-07-22 15:00:00"))
