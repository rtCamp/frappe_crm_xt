# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from frappe_crm_xt.api.follow import is_document_followed


class TestApiFollow(UnitTestCase):
	def test_is_document_followed_returns_falsy_when_not_following(self):
		"""is_document_followed returns a falsy value when there is no Document Follow row"""
		result = is_document_followed(
			"CRM Lead", f"XT-NoSuchLead-{__import__('frappe').generate_hash(length=8)}"
		)

		self.assertFalse(result)

	def test_is_document_followed_accepts_arbitrary_doctype(self):
		"""is_document_followed does not raise for a non-existent doctype/docname combo"""
		# It just queries Document Follow, so an unknown doctype string is fine
		result = is_document_followed("Made Up Doctype", "Made Up Name")

		self.assertFalse(result)
