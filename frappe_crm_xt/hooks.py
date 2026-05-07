app_name = "frappe_crm_xt"
app_title = "Frappe CRM XT"
app_publisher = "rtcamp"
app_description = "FCRM extensions: frappe_search bar and extensible sidebar list views."
app_email = "support@rtcamp.com"
app_license = "agpl-3"

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
#       "list_view" - opens /xt/list/<doctype> with the built-in list view.
#       "route"     - navigates to an arbitrary URL (internal or external).
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
#       Filters pre-applied when the list view opens AND shown in the filter UI.
#       Users can see and remove these filters.
#       Format: { "fieldname": ["operator", "value"], ... }
#       Example: { "status": ["=", "Open"], "priority": ["=", "High"] }
#
#   hidden_filters (dict, optional)
#       Filters always applied to every query but NEVER shown in the filter UI.
#       Users cannot see or remove these filters — useful for scoping a view to
#       a specific subset without cluttering the filter panel.
#       Format: { "fieldname": ["operator", "value"], ... }
#       Example: { "is_standard": ["=", "Yes"], "module": ["=", "CRM"] }
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
#   row_url         (str, optional)
#       URL template opened when a row is clicked.
#       Use {name} as a placeholder for the record name (URL-encoded automatically).
#       Defaults to /app/{doctype-slug}/{name}  (standard Frappe form view).
#       Example: "/desk/query-report/{name}"  →  opens the ERPNext report runner
#
#   search_field    (str, optional)
#       Fieldname used for the always-visible quick-search input in the toolbar.
#       Defaults to the doctype's title field (usually "name").
#       The input component is chosen automatically based on the field's type:
#         Data / Small Text / Text  → text input  (uses "like %value%" filter)
#         Select / Check            → dropdown    (uses "=" filter)
#         Link                      → autocomplete (uses "=" filter, loads options
#                                      from the linked doctype)
#         Date / Datetime           → date picker  (uses "=" filter)
#         Int / Float / Currency    → text input   (uses "=" filter)
#       Example: "supplier"  (shows supplier autocomplete in the toolbar)
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
#         "hidden_filters":  {"company": ["=", "My Company"]},   # always applied, not shown
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
		"label": "Reports",
		"type": "list_view",
		"doctype": "Report",
		"icon": "chart-bar",
		# Show the same columns as ERPNext's report list
		"fields": ["ref_doctype", "is_standard", "report_type"],
		"default_sort": {"field": "modified", "dir": "desc"},
		# Open the ERPNext report runner instead of the Report form
		"row_url": "/desk/query-report/{name}",
	},
]
