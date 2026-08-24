import frappe


def get_linked_gmail_thread_list(doctype, docname):
	return frappe.get_all(
		"Gmail Thread",
		filters={"reference_doctype": doctype, "reference_name": docname},
		pluck="name",
	)


def link_gmail_threads(doctype, docname, doc):
	"""Move the Gmail Threads on (doctype, docname) onto `doc`."""
	for gmail_thread in get_linked_gmail_thread_list(doctype, docname):
		gmail_thread_doc = frappe.get_doc("Gmail Thread", gmail_thread)
		gmail_thread_doc.reference_doctype = doc.doctype
		gmail_thread_doc.reference_name = doc.name
		gmail_thread_doc.save()
