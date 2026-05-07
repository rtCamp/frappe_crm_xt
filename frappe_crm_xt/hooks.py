app_name = "frappe_crm_xt"
app_title = "Frappe CRM XT"
app_publisher = "rtcamp"
app_description = "FCRM extensions: frappe_search bar and extensible sidebar list views."
app_email = "support@rtcamp.com"
app_license = "mit"

required_apps = ["crm"]

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
