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

_DELETE_WHEN_ORPHANED = ("Address",)


def on_trash(doc, method=None):
	if not doc.name:
		return

	for parent_dt in _LINK_PARENT_DOCTYPES:
		link_filters = {
			"parenttype": parent_dt,
			"link_doctype": doc.doctype,
			"link_name": doc.name,
		}

		if parent_dt in _DELETE_WHEN_ORPHANED:
			_detach_or_delete(parent_dt, link_filters)
		else:
			# Just drop the back-reference rows; the parent record stays.
			frappe.db.delete("Dynamic Link", link_filters)

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


def _detach_or_delete(parent_dt, link_filters):
	"""For each parent linked to the doc being trashed: if our link is its only
	one, delete the parent outright (delete_doc cascades its child rows); else
	just remove our back-reference row, leaving the parent intact."""
	from collections import Counter

	parent_dt_filter = {"parenttype": parent_dt}
	# Count our matching rows per parent in one query (handles the rare case of a
	# parent carrying more than one link to the same doc).
	ours_by_parent = Counter(frappe.get_all("Dynamic Link", filters=link_filters, pluck="parent"))

	for name, ours in ours_by_parent.items():
		total = frappe.db.count("Dynamic Link", {**parent_dt_filter, "parent": name})

		if total > ours:
			# Other links remain → keep the parent, drop only our row(s).
			frappe.db.delete("Dynamic Link", {**link_filters, "parent": name})
			continue

		# No other links → the parent is orphaned; delete it (rows cascade).
		try:
			frappe.delete_doc(parent_dt, name, delete_permanently=True)
		except Exception:
			# A stuck orphan (e.g. still referenced via a Link field elsewhere)
			# must not block the parent Lead/Deal delete — log it, but still drop
			# our back-reference row so the delete isn't blocked by it.
			frappe.db.delete("Dynamic Link", {**link_filters, "parent": name})
			frappe.log_error(
				title="Address already Linked [Delete Failed]",
				message=f"{parent_dt} {name}: {frappe.get_traceback()}",
			)
