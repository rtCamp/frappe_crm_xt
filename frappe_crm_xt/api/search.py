from __future__ import annotations

import frappe

# Frappe's search_link defaults to 10 rows; the CRM Link control never sends a
# page_length, so dropdowns top out at 10. Bump the default to 20 — the most the
# frontend Autocomplete renders (maxOptions=20). Higher needs a frontend change.
LINK_PAGE_LENGTH = 20


@frappe.whitelist()
def search_link(
	doctype: str,
	txt: str,
	query: str | None = None,
	filters: str | dict | list | None = None,
	page_length: int | None = None,
	searchfield: str | None = None,
	reference_doctype: str | None = None,
	ignore_user_permissions: bool = False,
	*,
	link_fieldname: str | None = None,
):
	"""Default page_length to 20, then delegate to the live search_link override (rtcamp's, else core)."""
	page_length = page_length or LINK_PAGE_LENGTH

	# rtcamp also overrides search_link (custom_enabled/disabled filtering). Chain
	# through it so that behaviour is preserved; fall back to core when absent.
	if "rtcamp" in frappe.get_installed_apps():
		from rtcamp.override.search_link_override import search_link_override

		return search_link_override(
			doctype,
			txt,
			query=query,
			filters=filters,
			page_length=page_length,
			searchfield=searchfield,
			reference_doctype=reference_doctype,
			ignore_user_permissions=ignore_user_permissions,
		)

	from frappe.desk import search as _search

	return _search.search_link(
		doctype,
		txt,
		query=query,
		filters=filters,
		page_length=page_length,
		searchfield=searchfield,
		reference_doctype=reference_doctype,
		ignore_user_permissions=ignore_user_permissions,
		link_fieldname=link_fieldname,
	)


@frappe.whitelist()
def get_search_results(text: str, start: int = 0, limit: int = 10):
	start = int(start)
	limit = int(limit)
	allowed_doctypes = [
		"CRM Lead",
		"CRM Deal",
		"CRM Organization",
		"FCRM Note",
		"CRM Task",
		"Contact",
	]

	if "frappe_search" in frappe.get_installed_apps():
		from frappe_search.api.search import get_global_search_results

		raw = get_global_search_results(
			text=text,
			start=start,
			limit=limit,
			allowed_doctypes=allowed_doctypes,
		)
		results_list, has_more = (
			(raw[0], raw[1]) if (isinstance(raw, list | tuple) and len(raw) == 2) else (raw, False)
		)
		if len(results_list) > limit:
			has_more = True
			results_list = list(results_list)[:limit]
		return results_list, has_more

	from frappe.utils.global_search import search as global_search

	raw = global_search(text, start=start, limit=limit + 1) or []

	has_more = len(raw) > limit
	results = []
	for r in raw[:limit]:
		results.append(
			{
				"doctype": r.get("doctype"),
				"name": r.get("name"),
				"title": r.get("title") or r.get("name"),
				"marked_string": r.get("content") or r.get("name"),
			}
		)

	return results, has_more
