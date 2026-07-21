# Copyright (c) 2026, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from frappe_crm_xt.tasks import deal_inactivity as di

NOTIF = "CRM Slack — CRM Deal Inactivity (7 days)"
HL = "_Test DI Holidays"
# Holiday list marks Fri 2026-07-17 + the weekend 07-18/07-19 as non-working.
HOLIDAYS = ("2026-07-17", "2026-07-18", "2026-07-19")


class TestWorkingDayHelpers(IntegrationTestCase):
	"""Pure working-day / config helpers — no DB needed."""

	def test_calendar_days_when_no_holidays(self):
		empty = frozenset()
		self.assertTrue(di._reached_working_days("2026-01-01", "2026-01-08", empty, 7))  # 7 days after
		self.assertFalse(di._reached_working_days("2026-01-01", "2026-01-07", empty, 7))  # only 6

	def test_holidays_do_not_count(self):
		hol = frozenset({getdate("2026-01-03"), getdate("2026-01-04")})
		# 01-01 → 01-08 is 7 days after, minus 2 holidays = 5 working days
		self.assertFalse(di._reached_working_days("2026-01-01", "2026-01-08", hol, 7))
		# two more calendar days reach 7 working days
		self.assertTrue(di._reached_working_days("2026-01-01", "2026-01-10", hol, 7))

	def test_counting_excludes_last_includes_today(self):
		empty = frozenset()
		self.assertFalse(di._reached_working_days("2026-01-01", "2026-01-01", empty, 1))  # 0 days after
		self.assertTrue(di._reached_working_days("2026-01-01", "2026-01-02", empty, 1))

	def test_threshold_zero_or_negative(self):
		self.assertTrue(di._reached_working_days("2026-01-01", "2026-01-01", frozenset(), 0))
		self.assertTrue(di._reached_working_days("2026-01-01", "2026-01-01", frozenset(), -3))

	def test_is_non_working_day(self):
		hol = frozenset({getdate("2026-01-03")})
		self.assertTrue(di._is_non_working_day("2026-01-03", hol))
		self.assertFalse(di._is_non_working_day("2026-01-02", hol))
		self.assertFalse(di._is_non_working_day("2026-01-02", frozenset()))

	def test_cfg_inactive_days(self):
		self.assertEqual(di._cfg_inactive_days({}), di.DEFAULT_INACTIVE_DAYS)
		self.assertEqual(di._cfg_inactive_days({"deal_inactivity_days": 3}), 3)
		self.assertEqual(di._cfg_inactive_days({"deal_inactivity_days": 0}), di.DEFAULT_INACTIVE_DAYS)
		self.assertEqual(di._cfg_inactive_days({"deal_inactivity_days": "x"}), di.DEFAULT_INACTIVE_DAYS)

	def test_cfg_window_buffer(self):
		self.assertEqual(di._cfg_window_buffer({}), di.DEFAULT_WINDOW_BUFFER_DAYS)  # blank → default
		self.assertEqual(
			di._cfg_window_buffer({"deal_inactivity_window_buffer_days": 0}), 0
		)  # explicit 0 honored
		self.assertEqual(di._cfg_window_buffer({"deal_inactivity_window_buffer_days": 9}), 9)
		self.assertEqual(
			di._cfg_window_buffer({"deal_inactivity_window_buffer_days": -2}), di.DEFAULT_WINDOW_BUFFER_DAYS
		)


class TestNotifyInactiveDeals(IntegrationTestCase):
	"""Integration: notify_inactive_deals(as_of=...) across weekends/holidays + buffer.
	IntegrationTestCase rolls back the DB after each test, so all setup is transient."""

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

		if not frappe.db.exists("Notification", NOTIF):
			frappe.get_doc(
				{
					"doctype": "Notification",
					"name": NOTIF,
					"subject": "{{ count }} inactive deals",
					"document_type": "CRM Deal",
					"event": "New",
					"channel": "System Notification",
					"message": "{{ doc.organization_name }}",
				}
			).insert(ignore_permissions=True)
		n = frappe.get_doc("Notification", NOTIF)
		n.enabled = 1
		n.slack_webhook_url = None  # no real Slack during tests
		n.condition_type = "Python"
		n.condition = '"_TESTDI" in (doc.organization_name or "")'  # scope to this test's deals
		if not n.message:
			n.message = "{{ doc.organization_name }}"
		n.save(ignore_permissions=True)

		s = frappe.get_single("CRM XT Settings")
		s.deal_inactivity_notification = NOTIF
		s.deal_inactivity_days = 3  # 3 WORKING days
		s.deal_inactivity_use_company_holiday_list = 0
		s.deal_inactivity_holiday_list = HL
		s.deal_inactivity_followup_enabled = 1
		s.deal_inactivity_task_priority = "High"
		s.deal_inactivity_task_title = "_TESTDI: {{ doc.organization_name }}"
		s.deal_inactivity_task_body = "x"
		s.deal_inactivity_window_buffer_days = 4
		s.save(ignore_permissions=True)

	def _deal(self, org, modified):
		d = frappe.get_doc(
			{"doctype": "CRM Deal", "organization_name": org, "status": "Open", "deal_owner": self.owner}
		).insert(ignore_permissions=True)
		for t in frappe.get_all(
			"CRM Task", filters={"reference_doctype": "CRM Deal", "reference_docname": d.name}, pluck="name"
		):
			frappe.delete_doc("CRM Task", t, force=True, ignore_permissions=True, delete_permanently=True)
		frappe.db.set_value("CRM Deal", d.name, "modified", modified + " 10:00:00", update_modified=False)
		return d.name

	def _tasks(self, deal):
		return frappe.db.count(
			"CRM Task",
			{"reference_doctype": "CRM Deal", "reference_docname": deal, "title": ["like", "_TESTDI:%"]},
		)

	def test_working_day_threshold_and_buffer(self):
		# as_of Tue 2026-07-21, threshold 3 working days, holidays 07-17/18/19.
		alpha = self._deal("_TESTDI alpha", "2026-07-15")  # 3 working days → flag
		gamma = self._deal("_TESTDI gamma", "2026-07-16")  # 5 calendar / 2 working → no
		eps = self._deal("_TESTDI epsilon", "2026-07-10")  # idle beyond threshold+buffer → not chased
		di.notify_inactive_deals(as_of="2026-07-21")
		self.assertEqual(self._tasks(alpha), 1)
		self.assertEqual(self._tasks(gamma), 0)
		self.assertEqual(self._tasks(eps), 0)

	def test_buffer_widens_window(self):
		eps = self._deal("_TESTDI epsilon", "2026-07-10")  # idle 11 calendar days
		s = frappe.get_single("CRM XT Settings")
		s.deal_inactivity_window_buffer_days = 8  # window now reaches back to 07-10
		s.save(ignore_permissions=True)
		di.notify_inactive_deals(as_of="2026-07-21")
		self.assertEqual(self._tasks(eps), 1)

	def test_skips_on_holiday_today(self):
		alpha = self._deal("_TESTDI onhol", "2026-07-14")  # would qualify on a working day
		di.notify_inactive_deals(as_of="2026-07-17")  # a holiday in the list
		self.assertEqual(self._tasks(alpha), 0)

	def test_dedup_across_runs(self):
		self._deal("_TESTDI dedup", "2026-07-15")
		di.notify_inactive_deals(as_of="2026-07-21")
		di.notify_inactive_deals(as_of="2026-07-21")
		self.assertEqual(frappe.db.count("CRM Task", {"title": ["like", "_TESTDI: _TESTDI dedup%"]}), 1)

	def test_off_when_no_notification(self):
		s = frappe.get_single("CRM XT Settings")
		s.deal_inactivity_notification = None
		s.save(ignore_permissions=True)
		alpha = self._deal("_TESTDI off", "2026-07-15")
		self.assertIsNone(di.notify_inactive_deals(as_of="2026-07-21"))
		self.assertEqual(self._tasks(alpha), 0)
