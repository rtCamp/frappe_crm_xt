import frappe
from frappe import _
from frappe.utils import get_link_to_form


def after_insert(doc, method=None):
	"""Add cross-comments when project is linked to a won deal"""
	if not doc.get("custom_deal", None):
		return

	try:
		deal = frappe.get_doc("CRM Deal", doc.custom_deal)

		deal.add_comment(
			"Info",
			_("Project {0} has been created from the CRM Deal marked as Won.").format(
				get_link_to_form("Project", doc.name)
			),
		)
		doc.add_comment(
			"Info",
			_("This Project is linked to CRM Deal {0}, which was marked as Won").format(
				get_link_to_form("CRM Deal", deal.name)
			),
		)
	except frappe.DoesNotExistError:
		return
