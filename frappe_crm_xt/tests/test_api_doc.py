# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from frappe_crm_xt.api.doc import get_linked_docs_of_document


class TestApiDoc(UnitTestCase):
	def tearDown(self) -> None:
		frappe.db.rollback()

	def test_unsupported_doctype_passes_rows_through(self):
		"""For doctypes that aren't CRM Lead/Deal, rows are forwarded unchanged"""
		upstream_rows = [
			{"reference_doctype": "Contact", "doc": "C1"},
			{"reference_doctype": "Other", "doc": "O1"},
		]

		with patch("crm.api.doc.get_linked_docs_of_document", return_value=upstream_rows):
			out = get_linked_docs_of_document(doctype="User", docname="Administrator")

		self.assertEqual(out, upstream_rows)

	def test_crm_deal_filters_hidden_reference_doctypes(self):
		"""For CRM Deal parent, rows whose reference_doctype is Contact/Address/Gmail Thread are dropped"""
		upstream_rows = [
			{"reference_doctype": "Contact", "doc": "C1"},
			{"reference_doctype": "Address", "doc": "A1"},
			{"reference_doctype": "Gmail Thread", "doc": "G1"},
			{"reference_doctype": "CRM Task", "doc": "T1"},
		]

		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)

		with patch("crm.api.doc.get_linked_docs_of_document", return_value=upstream_rows):
			out = get_linked_docs_of_document(doctype="CRM Deal", docname=deal.name)

		out_refs = {row["reference_doctype"] for row in out}
		self.assertNotIn("Contact", out_refs)
		self.assertNotIn("Address", out_refs)
		self.assertNotIn("Gmail Thread", out_refs)
		self.assertIn("CRM Task", out_refs)

	def test_crm_lead_filters_hidden_doc_values(self):
		"""For CRM Lead parent, rows whose 'doc' is Contact/Address/Gmail Thread are dropped"""
		# The override also filters on row["doc"] in the hidden set
		upstream_rows = [
			{"reference_doctype": "Something", "doc": "Contact"},
			{"reference_doctype": "Something", "doc": "Other"},
		]

		lead = frappe.get_doc(
			{"doctype": "CRM Lead", "first_name": f"XT-{frappe.generate_hash(length=6)}"}
		).insert(ignore_permissions=True)

		with patch("crm.api.doc.get_linked_docs_of_document", return_value=upstream_rows):
			out = get_linked_docs_of_document(doctype="CRM Lead", docname=lead.name)

		out_docs = [row["doc"] for row in out]
		self.assertNotIn("Contact", out_docs)
		self.assertIn("Other", out_docs)

	def test_empty_upstream_returns_empty(self):
		"""An empty upstream result yields an empty list"""
		deal = frappe.get_doc({"doctype": "CRM Deal"}).insert(ignore_permissions=True)

		with patch("crm.api.doc.get_linked_docs_of_document", return_value=None):
			out = get_linked_docs_of_document(doctype="CRM Deal", docname=deal.name)

		self.assertEqual(out, [])
