"""on_trash for CRM Lead and CRM Deal.

Cleans up loose back-references so the parent delete can proceed:

  - Contact / Address — back-references on their `links` child table
    (Dynamic Link rows).
  - Gmail Thread — back-reference on its own `reference_doctype` /
    `reference_name` fields.

Frappe's `delete_doc` runs `on_trash` **before** the dynamic-link
existence check (frappe/model/delete_doc.py: on_trash at L165, link
check at L173), so removing the rows here lets the delete proceed
without LinkExistsError, no `ignore_links_on_delete` hook required.
"""

from __future__ import annotations

import frappe

_LINK_PARENT_DOCTYPES = ("Contact", "Address")
_GMAIL_THREAD = "Gmail Thread"


def on_trash(doc, method=None):
	if not doc.name:
		return

	for parent_dt in _LINK_PARENT_DOCTYPES:
		frappe.db.delete(
			"Dynamic Link",
			{
				"parenttype": parent_dt,
				"link_doctype": doc.doctype,
				"link_name": doc.name,
			},
		)

	for thread_name in frappe.get_all(
		_GMAIL_THREAD,
		filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
		pluck="name",
	):
		# db.set_value bypasses Gmail Thread's own validate hook (which would
		# re-read the now-empty reference fields and reject the update).
		frappe.db.set_value(
			_GMAIL_THREAD,
			thread_name,
			{"reference_doctype": "", "reference_name": ""},
			update_modified=False,
		)
