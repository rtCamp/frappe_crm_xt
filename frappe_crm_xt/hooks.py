app_name = "frappe_crm_xt"
app_title = "Frappe CRM XT"
app_publisher = "rtcamp"
app_description = "FCRM extensions: frappe_search bar and extensible sidebar list views."
app_email = "support@rtcamp.com"
app_license = "mit"

required_apps = ["crm"]

# ─── CRM Sidebar hook ─────────────────────────────────────────────────────────
#
# Any installed Frappe app can define this hook to inject items into the FCRM
# sidebar (inserted below "Call Logs").
#
# Each item is a dict with the following keys:
#
#   label          (str, required)
#       Sidebar display label, e.g. "Purchase Orders"
#
#   type           (str, required)  "list_view" | "route"
#       "list_view" – opens /xt/list/<doctype> with the built-in list view.
#       "route"     – navigates to an arbitrary URL (internal or external).
#
#   doctype        (str)  Required when type == "list_view".
#       Frappe DocType name, e.g. "Purchase Order"
#
#   url            (str)  Required when type == "route".
#       Destination URL, e.g. "/app/purchase-order" or "https://example.com"
#
#   icon           (str, optional)  Lucide icon name (default: "list")
#       Any of the 1600+ Lucide icon names work — see https://lucide.dev/icons/
#       Common examples: users, user, briefcase, file-text, package,
#         shopping-cart, tag, inbox, phone, calendar, square-check,
#         dollar-sign, trending-up, activity, star, settings, grid-2x2,
#         building, building-2, list, external-link, link, layout-grid
#
#   default_filters (dict, optional)
#       Filters pre-applied when the list view opens.
#       Format: { "fieldname": ["operator", "value"], ... }
#       Example: { "status": ["=", "Open"], "priority": ["=", "High"] }
#
#   fields          (list[str], optional)
#       Ordered list of fieldnames to display as columns.
#       Overrides the auto-detected in_list_view columns from the DocType.
#       The title field and "Modified" are always included automatically.
#       Example: ["item_name", "status", "supplier", "grand_total"]
#
#   default_sort    (dict, optional)
#       Initial sort applied when the list opens.
#       Keys: "field" (fieldname str) and "dir" ("asc" | "desc").
#       Example: { "field": "creation", "dir": "desc" }
#
# ─── Example ──────────────────────────────────────────────────────────────────
#
# crm_sidebar = [
#     {
#         "label": "Purchase Orders",
#         "type": "list_view",
#         "doctype": "Purchase Order",
#         "icon": "shopping-cart",   # any name from lucide.dev/icons
#         "default_filters": {"status": ["=", "To Receive and Bill"]},
#         "fields": ["supplier", "transaction_date", "status", "grand_total"],
#         "default_sort": {"field": "transaction_date", "dir": "desc"},
#     },
#     {
#         "label": "Support Portal",
#         "type": "route",
#         "url": "https://support.example.com",
#         "icon": "external-link",
#     },
# ]
#
crm_sidebar = [
    {
        "label": "CRM Leads",
        "type": "list_view",
        "doctype": "CRM Lead",
        "icon": "users",
    },
]
