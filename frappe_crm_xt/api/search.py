from __future__ import annotations

import frappe


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
