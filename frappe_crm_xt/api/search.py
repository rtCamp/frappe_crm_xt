"""
Search API for frappe_crm_xt.

Provides a single whitelisted endpoint that:
  1. Determines the correct doctype list (FCRM native vs. ERPNext bridge).
  2. Delegates to frappe_search when installed for full-text results.
  3. Falls back to a basic frappe.get_list name-match otherwise.

Response shape matches frappe_search:
    (results_list, has_more_bool)

Each result dict:
    { doctype, name, marked_string }   ← marked_string may contain <mark> tags
"""

from __future__ import annotations

import frappe

# ── Doctype lists ──────────────────────────────────────────────────────────────
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

BRIDGE_DOCTYPES: list[str] = [
    "Lead",
    "Opportunity",
    "Contact",
    "CRM Organization",
    "FCRM Note",
    "CRM Task",
    "Event",
    "CRM Call Log",
]


def _search_doctypes() -> list[str]:
    if "crm_erp_bridge" in frappe.get_installed_apps():
        return BRIDGE_DOCTYPES
    return FCRM_DOCTYPES


# ── Public endpoint ────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_search_results(text: str, start: int = 0, limit: int = 50):
    """
    Unified search endpoint for frappe_crm_xt.

    Calls frappe_search.api.search.get_global_search_results when the app is
    installed; falls back to a simple name-match via frappe.get_list otherwise.

    Custom logic (e.g. boosting, extra filters, post-processing) belongs here.
    """
    start = int(start)
    limit = int(limit)
    allowed_doctypes = _search_doctypes()

    if "frappe_search" in frappe.get_installed_apps():
        from frappe_search.api.search import get_global_search_results

        raw = get_global_search_results(
            text=text,
            start=start,
            limit=limit,
            allowed_doctypes=allowed_doctypes,
        )
        # frappe_search filters by doctype after fetching, so it can return
        # more rows than `limit`.  Enforce our limit and propagate has_more.
        results_list, has_more = (raw[0], raw[1]) if (isinstance(raw, (list, tuple)) and len(raw) == 2) else (raw, False)
        if len(results_list) > limit:
            has_more = True
            results_list = list(results_list)[:limit]
        return results_list, has_more

    # ── Fallback: frappe built-in global search ────────────────────────────────
    # Uses the __global_search table (populated via in_global_search=1 fields),
    # filtered to FCRM doctypes.
    try:
        from frappe.utils.global_search import search as _frappe_global_search

        allowed_set = set(allowed_doctypes)
        # Fetch more than limit so filtering by doctype leaves enough results
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
    except Exception:
        pass

    # ── Last-resort: name-match via get_list ───────────────────────────────────
    results = []
    for dt in allowed_doctypes[:4]:
        try:
            rows = frappe.get_list(
                dt,
                filters={"name": ["like", f"%{text}%"]},
                fields=["name"],
                limit=10,
            )
            for row in rows:
                results.append({"doctype": dt, "name": row.name, "marked_string": row.name})
        except Exception:
            continue
    return results, False
