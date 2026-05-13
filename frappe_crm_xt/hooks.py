app_name = "frappe_crm_xt"
app_title = "Frappe CRM XT"
app_publisher = "rtcamp"
app_description = "FCRM extensions: frappe_search bar and extensible sidebar list views."
app_email = "support@rtcamp.com"
app_license = "agpl-3"

required_apps = ["crm"]

fixtures = [
	{
		"dt": "Property Setter",
		"filters": [
			["property", "=", "in_global_search"],
			["doc_type", "in", ["CRM Lead", "CRM Deal", "CRM Organization", "FCRM Note", "CRM Task"]],
		],
	},
	{"dt": "Custom Field", "filters": [["dt", "=", "CRM Deal Status"]]},
]

# ─── Doc events ───────────────────────────────────────────────────────────────

doc_events = {
	"CRM Deal": {
		"before_save": "frappe_crm_xt.api.deal.before_save",
		"after_insert": "frappe_crm_xt.api.deal.after_insert",
	},
	"Gmail Thread": {
		"validate": "frappe_crm_xt.doc_events.gmail_thread.validate",
		"on_update": "frappe_crm_xt.doc_events.gmail_thread.on_update",
	},
}

# ─── API overrides ────────────────────────────────────────────────────────────
#
# Intercept FCRM's get_activities so we can append frappe_gmail_thread entries.
# frappe_crm_xt must be listed after crm in apps.txt for the override to win.
#
override_whitelisted_methods = {
	# Append frappe_gmail_thread activity entries to FCRM's activity feed.
	"crm.api.activities.get_activities": "frappe_crm_xt.api.activity.get_activities",
}

# ─── Scheduler ────────────────────────────────────────────────────────────────
#
# Event notification scheduler — sends in-browser realtime alerts (and
# optionally emails) to event owners and participants ahead of their events.
#
scheduler_events = {
	"all": ["frappe_crm_xt.api.event.trigger_offset_event_notifications"],
	"hourly": ["frappe_crm_xt.api.event.trigger_hourly_event_notifications"],
	"daily": ["frappe_crm_xt.api.event.trigger_daily_event_notifications"],
	"weekly": ["frappe_crm_xt.api.event.trigger_weekly_event_notifications"],
}

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
#   type           (str, required)  "list_view" | "route" | "separator" | "group"
#       "list_view"  - opens /xt/list/<doctype> with the built-in list view.
#       "route"      - navigates to an arbitrary URL (internal or external).
#       "separator"  - renders a horizontal divider line; no other keys needed.
#       "group"      - collapsible section; child items live in the "items" key.
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
#   items           (list, optional)  Only for type == "group".
#       Child items — each follows the same schema (list_view, route, separator).
#       Groups do NOT nest inside other groups (only one level deep).
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
#     {"type": "separator"},          # ── horizontal divider ──────────────────
#     {
#         "label": "Procurement",     # ── collapsible group ───────────────────
#         "type": "group",
#         "icon": "package",
#         "items": [
#             {
#                 "label": "Suppliers",
#                 "type": "list_view",
#                 "doctype": "Supplier",
#                 "icon": "building",
#             },
#             {"type": "separator"},
#             {
#                 "label": "Support Portal",
#                 "type": "route",
#                 "url": "https://support.example.com",
#                 "icon": "external-link",
#             },
#         ],
#     },
# ]
#
crm_sidebar = [
	{"type": "separator"},
	{
		"label": "Frappe CRM XT",
		"type": "group",
		"icon": "layout-grid",
		"items": [
			{
				"label": "Events",
				"type": "list_view",
				"doctype": "Event",
				"icon": "calendar",
				"fields": ["subject", "starts_on", "ends_on", "event_type", "status"],
				"default_sort": {"field": "starts_on", "dir": "desc"},
				"row_url": "/app/event/{name}",
			},
			{
				"label": "Reports",
				"type": "list_view",
				"doctype": "Report",
				"icon": "chart-bar",
				"fields": ["ref_doctype", "is_standard", "report_type"],
				"default_sort": {"field": "modified", "dir": "desc"},
				"row_url": "/desk/query-report/{name}",
			},
		],
	},
]

# ─── Setup hooks ──────────────────────────────────────────────────────────────
#
# Install/refresh the CRM-side custom fields that mirror rtcamp's ERPNext-side
# customisations. Lets the ERPNext → Frappe CRM migrator auto-map fields by
# same-name match without any per-row review by the user.
#
# create_custom_fields(..., update=True) is idempotent — safe to call on every
# migrate.

after_install = "frappe_crm_xt.setup.install_custom_fields"
after_migrate = "frappe_crm_xt.setup.install_custom_fields"
