import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime


def validate(doc, method=None):
	validate_posting_datetime(doc)


def validate_posting_datetime(doc):
	"""Default posting_datetime to now, reject future values, and pin creation to it on insert."""
	if not doc.get("posting_datetime"):
		doc.posting_datetime = now_datetime()

	posting = get_datetime(doc.posting_datetime)
	if posting > now_datetime():
		frappe.throw(_("Posting Datetime cannot be in the future."))
