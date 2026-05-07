"""Return crm_sidebar hook items from all installed apps."""
from __future__ import annotations
import frappe


@frappe.whitelist()
def get_sidebar_items() -> list[dict]:
    """
    Reads the ``crm_sidebar`` hook from every installed app and returns a
    merged flat list.

    Each app defines in its hooks.py::

        crm_sidebar = [
            {"label": "Purchase Orders", "type": "list_view", "doctype": "Purchase Order", "icon": "file-text"},
            {"label": "Support",         "type": "route",     "url": "https://support.example.com"},
        ]

    Supported item keys:
        label   (str)  – sidebar label
        type    (str)  – "list_view" | "route"
        doctype (str)  – required when type == "list_view"
        url     (str)  – required when type == "route"
        icon    (str)  – optional Feather icon name (default "list")
    """
    items: list[dict] = []
    for app in frappe.get_installed_apps():
        hook_val = frappe.get_hooks("crm_sidebar", app_name=app)
        if not hook_val:
            continue
        for entry in hook_val:
            if isinstance(entry, dict):
                items.append(entry)
            elif isinstance(entry, (list, tuple)):
                items.extend(e for e in entry if isinstance(e, dict))
    return items
