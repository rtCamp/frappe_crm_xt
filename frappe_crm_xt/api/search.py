"""
Search API for frappe_crm_xt.

Two backends are supported (tried in order):

1. frappe_search  — full-text search via the frappe_search app (if installed).
2. Frappe global search — built-in ``frappe.utils.global_search`` (always available).

Response shape:
    (results_list, has_more_bool)

Each result dict:
    { doctype, name, marked_string }   ← marked_string may contain <mark> tags
"""

from __future__ import annotations

import frappe

FCRM_DOCTYPES: list[str] = [
	"CRM Lead",
	"CRM Deal",
	"Contact",
	"CRM Organization",
	"FCRM Note",
	"CRM Task",
	"Event",
	"CRM Call Log",
]


@frappe.whitelist()
def get_search_results(text: str, start: int = 0, limit: int = 50):
	"""
	Unified search endpoint for frappe_crm_xt.

	Uses frappe_search when installed; falls back to Frappe's built-in
	global search otherwise.
	"""
	start = int(start)
	limit = int(limit)
	allowed_doctypes = FCRM_DOCTYPES

	# ── Backend 1: frappe_search (optional) ───────────────────────────────────
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

	# ── Backend 2: Frappe built-in global search ───────────────────────────────
	from frappe.utils.global_search import search as _frappe_global_search

	allowed_set = set(allowed_doctypes)
	raw = _frappe_global_search(text, start=start, page_length=limit * 3) or []
	results: list[dict] = []
	for r in raw:
		if r.get("doctype") not in allowed_set:
			continue
		results.append(
			{
				"doctype": r["doctype"],
				"name": r["name"],
				"marked_string": r.get("content") or r["name"],
			}
		)
		if len(results) >= limit:
			break
	has_more = len(raw) >= limit * 3
	return results, has_more
