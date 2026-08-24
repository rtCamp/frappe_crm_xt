"""Move already-converted leads' Gmail Threads onto their deals.

`CRM Deal.after_insert` handles conversions from now on; deals converted before
that hook existed still have their threads on the source lead, so their timeline
shows nothing. Oldest deal first, so a lead behind two deals gives its threads to
the earlier one. Once moved a thread no longer matches, so this is re-runnable.

No-op when `frappe_gmail_thread` isn't installed.
"""

import frappe

from frappe_crm_xt.utils.gmail_thread import link_gmail_threads


def execute():
	if "frappe_gmail_thread" not in frappe.get_installed_apps():
		return
	if not frappe.db.exists("DocType", "Gmail Thread"):
		return

	deals = frappe.get_all(
		"CRM Deal",
		filters={"lead": ["is", "set"]},
		fields=["name", "lead"],
		order_by="creation asc",
	)
	for deal in deals:
		if not get_thread_count(deal.lead):
			continue
		link_gmail_threads("CRM Lead", deal.lead, frappe.get_doc("CRM Deal", deal.name))
		frappe.db.commit()


def get_thread_count(lead):
	return frappe.db.count("Gmail Thread", {"reference_doctype": "CRM Lead", "reference_name": lead})
