// Copyright (c) 2026, rtcamp and contributors
// For license information, please see license.txt

frappe.query_reports["CRM Lead Conversion Rate"] = {
	filters: [
		{
			fieldname: "year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
		},
		{
			fieldname: "month",
			label: __("Month"),
			fieldtype: "Select",
			options: ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"],
		},
	],
};
