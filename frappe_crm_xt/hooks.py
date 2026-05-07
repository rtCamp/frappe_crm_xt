app_name = "frappe_crm_xt"
app_title = "Frappe CRM XT"
app_publisher = "rtcamp"
app_description = "FCRM extensions: frappe_search bar and ERPNext-aware gmail-thread activities."
app_email = "support@rtcamp.com"
app_license = "mit"

required_apps = ["crm"]

# ─── API overrides ────────────────────────────────────────────────────────────
#
# Our app sits after crm (and crm_erp_bridge) in apps.txt, so our override
# wins.  The handler calls the appropriate upstream first (bridge proxy when
# crm_erp_bridge is installed, original CRM otherwise), then merges
# frappe_gmail_thread activities when that app is present.
#
override_whitelisted_methods = {
    "crm.api.activities.get_activities": "frappe_crm_xt.api.activity.get_activities",
}

# ─── CRM Sidebar hook (example / self-test) ───────────────────────────────────
#
# Any installed app can define this hook to inject items below "Call Logs"
# in the FCRM sidebar.  frappe_crm_xt injects its own example item so the
# feature can be validated after install.
#
# Supported keys:
#   label   (str)  – sidebar label
#   type    (str)  – "list_view" | "route"
#   doctype (str)  – required when type == "list_view"
#   url     (str)  – required when type == "route"
#   icon    (str)  – optional Feather icon name (default "list")
#
crm_sidebar = [
    {"label": "CRM Leads", "type": "list_view", "doctype": "CRM Lead", "icon": "users"},
]
