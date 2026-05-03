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
