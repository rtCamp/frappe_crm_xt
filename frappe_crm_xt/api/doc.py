"""Override of `crm.api.doc.remove_linked_doc_reference` for the Unlink case.

Upstream clears `reference_doctype` / `reference_docname` on the linked
doc. Correct for FCRM Note / Task / Call Log / Notification, wrong for:

  - Contact / Address — back-references live on `<doctype>.links` (Dynamic
    Link rows: link_doctype + link_name). Writing `reference_docname` is
    a no-op, so Unlink silently does nothing.

  - Gmail Thread — uses `reference_name` instead of `reference_docname`.
    Upstream clears `reference_doctype` but leaves `reference_name`
    populated; the next save raises "Reference Document Type must be set
    first" on the now-orphan Dynamic Link. Upstream catches it but the
    red toast has already been registered.

We handle those three doctypes ourselves for unlink only. Everything else,
plus the delete branch (`delete=True`), falls through to upstream.

The parent context for Contact / Address comes from the Referer header
(`/crm/(leads|deals|contacts|organizations)/<name>` — the modal is always
opened from one of those routes). If it can't be parsed, those items also
fall through to upstream.
"""

from __future__ import annotations

import re
from urllib.parse import unquote

import frappe

_LINK_PARENT_DOCTYPES = ("Contact", "Address")
_GMAIL_THREAD = "Gmail Thread"

_REFERER_SLUG_MAP = {
	"leads": "CRM Lead",
	"deals": "CRM Deal",
	"contacts": "Contact",
	"organizations": "CRM Organization",
}
_REFERER_RE = re.compile(r"/crm/(leads|deals|contacts|organizations)/([^/?#]+)")


def _is_truthy(val) -> bool:
	return str(val).lower() in ("1", "true", "yes")


@frappe.whitelist()
def remove_linked_doc_reference(items: str | list, remove_contact: bool = False, delete: bool = False):
	from crm.api.doc import remove_linked_doc_reference as upstream

	# Delete path is upstream's job — we only fix unlink.
	if _is_truthy(delete):
		return upstream(items=items, remove_contact=remove_contact, delete=delete)

	parsed_items = frappe.parse_json(items) if isinstance(items, str) else items
	if not isinstance(parsed_items, list):
		parsed_items = []

	parent_doctype, parent_name = _infer_parent_from_referer()

	handled: list[dict] = []
	passthrough: list[dict] = []
	for item in parsed_items:
		if not isinstance(item, dict) or not item.get("doctype") or not item.get("docname"):
			continue
		dt = item["doctype"]
		if dt == _GMAIL_THREAD:
			handled.append(item)
		elif dt in _LINK_PARENT_DOCTYPES and parent_doctype and parent_name:
			handled.append(item)
		else:
			passthrough.append(item)

	for item in handled:
		dt = item["doctype"]
		if dt == _GMAIL_THREAD:
			_unlink_gmail_thread(item["docname"])
		else:
			_unlink_contact_or_address(
				linked_doctype=dt,
				linked_name=item["docname"],
				parent_doctype=parent_doctype,
				parent_name=parent_name,
			)

	if passthrough:
		return upstream(items=passthrough, remove_contact=remove_contact, delete=False)
	return "success"


def _infer_parent_from_referer() -> tuple[str | None, str | None]:
	if not getattr(frappe.local, "request", None):
		return None, None
	referer = frappe.local.request.headers.get("Referer") or ""
	match = _REFERER_RE.search(referer)
	if not match:
		return None, None
	slug, raw = match.groups()
	return _REFERER_SLUG_MAP.get(slug), unquote(raw)


def _unlink_gmail_thread(thread_name: str) -> None:
	if not thread_name or not frappe.db.exists(_GMAIL_THREAD, thread_name):
		return
	if not frappe.has_permission(_GMAIL_THREAD, "write", thread_name):
		return
	# db.set_value bypasses the doctype's validate hook (which would re-read
	# the reference fields and refuse the empty values).
	frappe.db.set_value(
		_GMAIL_THREAD,
		thread_name,
		{"reference_doctype": "", "reference_name": ""},
		update_modified=False,
	)


def _unlink_contact_or_address(
	linked_doctype: str,
	linked_name: str,
	parent_doctype: str,
	parent_name: str,
) -> None:
	"""Drop the row in `<linked>.links` that points at the parent.

	Deletes the `Dynamic Link` row directly rather than going through
	`doc.save()`. Going through save runs Address / Contact's full lifecycle
	(autoname, geolocation hooks, custom validations etc.), which can
	silently swallow or rewrite the child-table mutation. The row itself is
	a pure back-reference — direct delete is the right semantics.
	"""
	if not frappe.db.exists(linked_doctype, linked_name):
		return
	if not frappe.has_permission(linked_doctype, "write", linked_name):
		return

	frappe.db.delete(
		"Dynamic Link",
		{
			"parenttype": linked_doctype,
			"parent": linked_name,
			"link_doctype": parent_doctype,
			"link_name": parent_name,
		},
	)
	frappe.clear_document_cache(linked_doctype, linked_name)
