# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from frappe_crm_xt.api.session import get_users


class TestApiSession(UnitTestCase):
	def test_returns_two_lists(self):
		"""get_users returns a 2-tuple of lists"""
		result = get_users()

		self.assertEqual(len(result), 2)
		users, crm_users = result
		self.assertIsInstance(users, list)
		self.assertIsInstance(crm_users, list)

	def test_administrator_present_in_users(self):
		"""Administrator is always returned with System Manager role"""
		users, _ = get_users()

		admin = next((u for u in users if u.name == "Administrator"), None)
		self.assertIsNotNone(admin)
		self.assertEqual(admin.role, "System Manager")
		self.assertIn("System Manager", admin.roles)
		self.assertIn("All", admin.roles)

	def test_administrator_present_in_crm_users(self):
		"""Administrator's System Manager role makes it a CRM user"""
		_, crm_users = get_users()

		admin = next((u for u in crm_users if u.name == "Administrator"), None)
		self.assertIsNotNone(admin)

	def test_user_dict_has_telephony_agent_flag(self):
		"""Each user dict exposes a boolean is_telephony_agent flag"""
		users, _ = get_users()

		admin = next(u for u in users if u.name == "Administrator")
		self.assertIsInstance(admin.is_telephony_agent, bool)

	def test_user_dict_has_session_user_for_current(self):
		"""The session user (Administrator) is flagged session_user=True"""
		# Tests run as Administrator
		self.assertEqual(frappe.session.user, "Administrator")
		users, _ = get_users()

		admin = next(u for u in users if u.name == "Administrator")
		self.assertTrue(getattr(admin, "session_user", False))
