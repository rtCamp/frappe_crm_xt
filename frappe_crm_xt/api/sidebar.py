"""Return crm_sidebar hook items from all installed apps."""

from __future__ import annotations

import frappe

# Keys forwarded from each hook item to the frontend.
# All are optional except label and type.
_ALLOWED_KEYS = {
	"label",
	"type",
	"doctype",
	"url",
	"icon",
	# list-view customisation
	"default_filters",  # dict  { fieldname: [operator, value] }  - shown in filter UI
	"hidden_filters",  # dict  { fieldname: [operator, value] }  - always applied, never shown
	"fields",  # list  [fieldname, ...]  - column order override
	"default_sort",  # dict  { field: str, dir: "asc"|"desc" }
	"search_field",  # str   fieldname used for the toolbar quick-search input
	"row_url",  # str   URL template for row clicks; {name} = record name
}


@frappe.whitelist()
def get_sidebar_items() -> list[dict]:
	"""
	Reads the ``crm_sidebar`` hook from every installed app and returns a
	merged flat list.  Each item is validated and stripped to allowed keys
	before being sent to the browser.

	Supported hook schema (in any app's hooks.py)::

	    crm_sidebar = [
	        {
	            "label": "Purchase Orders",  # required
	            "type": "list_view",  # "list_view" | "route"
	            "doctype": "Purchase Order",  # required for list_view
	            "icon": "shopping-cart",  # feather icon name
	            "default_filters": {"status": ["=", "To Receive and Bill"]},
	            "fields": ["supplier", "transaction_date", "status"],
	            "default_sort": {"field": "transaction_date", "dir": "desc"},
	        },
	        {
	            "label": "Support",
	            "type": "route",
	            "url": "https://support.example.com",
	            "icon": "external-link",
	        },
	    ]
	"""
	items: list[dict] = []
	for app in frappe.get_installed_apps():
		hook_val = frappe.get_hooks("crm_sidebar", app_name=app)
		if not hook_val:
			continue
		for entry in hook_val:
			if isinstance(entry, dict):
				items.append(_sanitise(entry))
			elif isinstance(entry, list | tuple):
				items.extend(_sanitise(e) for e in entry if isinstance(e, dict))
	return items


def _sanitise(item: dict) -> dict:
	"""Strip unknown keys and apply light validation."""
	out = {k: v for k, v in item.items() if k in _ALLOWED_KEYS}
	# Ensure default_filters / hidden_filters are plain dicts
	if "default_filters" in out and not isinstance(out["default_filters"], dict):
		del out["default_filters"]
	if "hidden_filters" in out and not isinstance(out["hidden_filters"], dict):
		del out["hidden_filters"]
	# Ensure fields is a list of strings
	if "fields" in out:
		if not isinstance(out["fields"], list | tuple):
			del out["fields"]
		else:
			out["fields"] = [str(f) for f in out["fields"]]
	# Ensure default_sort has expected shape
	if "default_sort" in out:
		ds = out["default_sort"]
		if not (isinstance(ds, dict) and "field" in ds):
			del out["default_sort"]
		else:
			out["default_sort"] = {
				"field": str(ds["field"]),
				"dir": "asc" if str(ds.get("dir", "desc")).lower() == "asc" else "desc",
			}
	return out
