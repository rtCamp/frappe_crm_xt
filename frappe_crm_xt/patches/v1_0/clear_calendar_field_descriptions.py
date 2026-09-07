import frappe

FIELDNAMES = (
	"custom_start_datetime",
	"custom_sync_with_calendar",
	"custom_google_calendar_link",
)


def execute():
	names = frappe.get_all(
		"Custom Field",
		filters={
			"dt": "CRM Task",
			"fieldname": ["in", FIELDNAMES],
			"description": ["is", "set"],
		},
		pluck="name",
	)
	if not names:
		return

	for name in names:
		frappe.db.set_value("Custom Field", name, "description", "", update_modified=False)
