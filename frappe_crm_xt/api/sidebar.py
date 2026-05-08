"""Return crm_sidebar hook items from all installed apps."""

from __future__ import annotations

import frappe

# Keys forwarded from each hook item to the frontend.
_ALLOWED_KEYS = {
	"label",
	"type",
	"doctype",
	"url",
	"icon",
	# list-view customisation
	"default_filters",
	"hidden_filters",
	"fields",
	"default_sort",
	"search_field",
	"row_url",
	# group type
	"items",
}


@frappe.whitelist()
def get_sidebar_items() -> list[dict]:
	"""
	Reads the ``crm_sidebar`` hook from every installed app and returns a
	merged flat list.  Each item is validated and stripped to allowed keys
	before being sent to the browser.

	Supported item types:

	``list_view``   Opens the built-in list view for a DocType.
	``route``       Navigates to an arbitrary URL.
	``separator``   Renders a horizontal divider line.
	``group``       Collapsible section; child items live in ``items``.
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
	item_type = item.get("type")

	# ── Separator ──────────────────────────────────────────────────────────────
	if item_type == "separator":
		return {"type": "separator"}

	out = {k: v for k, v in item.items() if k in _ALLOWED_KEYS}

	# ── Group ──────────────────────────────────────────────────────────────────
	if item_type == "group":
		if isinstance(out.get("items"), list | tuple):
			out["items"] = [_sanitise(i) for i in out["items"] if isinstance(i, dict)]
		else:
			out["items"] = []
		return out

	# ── list_view / route ──────────────────────────────────────────────────────
	if "default_filters" in out and not isinstance(out["default_filters"], dict):
		del out["default_filters"]
	if "hidden_filters" in out and not isinstance(out["hidden_filters"], dict):
		del out["hidden_filters"]
	if "fields" in out:
		if not isinstance(out["fields"], list | tuple):
			del out["fields"]
		else:
			out["fields"] = [str(f) for f in out["fields"]]
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
