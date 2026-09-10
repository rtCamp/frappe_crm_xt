import frappe

FIELDNAMES = (
	"custom_start_datetime",
	"custom_sync_with_calendar",
	"custom_google_calendar_link",
	"custom_slack_channel_link",
	"custom_original_hourly_rate_exchange_rate",
	"custom_effective_hourly_rate_exchange_rate",
)


def execute():
	names = frappe.get_all(
		"Custom Field",
		filters={
			"dt": ["in", ("CRM Task", "CRM Deal")],
			"fieldname": ["in", FIELDNAMES],
			"description": ["is", "set"],
		},
		pluck="name",
	)
	if not names:
		return

	for name in names:
		frappe.db.set_value("Custom Field", name, "description", "", update_modified=False)
