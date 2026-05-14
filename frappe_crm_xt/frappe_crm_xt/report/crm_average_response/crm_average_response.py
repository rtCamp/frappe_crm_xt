# Copyright (c) 2026, rtCamp and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, getdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters=filters)
	return columns, data


def get_data(filters=None):
	today = getdate()
	weekday = today.weekday()

	last_monday = add_days(today, -(weekday + 7))
	last_sunday = add_days(today, -(weekday + 1))

	query = """
	SELECT
		t.deal_owner AS sales_person,
		AVG(t.first_response_time) AS avg_first_response,
		AVG(t.custom_last_response_time) AS avg_followup_time,
        ROUND(
            SUM(CASE WHEN t.sla_status = 'Fulfilled' THEN 1 ELSE 0 END) * 100.0 / COUNT(t.name),
            2
        ) AS sla_met,
        MIN(t.first_response_time) AS fastest_response,
        MAX(t.first_response_time) AS slowest_response
	FROM `tabCRM Deal` t
	LEFT JOIN `tabUser` u ON u.name = t.deal_owner
	WHERE t.modified BETWEEN %s AND %s
	GROUP BY t.deal_owner
    """

	return frappe.db.sql(query, (last_monday, last_sunday), as_dict=True)


def get_columns():
	columns = [
		{
			"label": _("Sales Person"),
			"fieldname": "sales_person",
			"fieldtype": "Link",
			"options": "User",
			"width": 200,
		},
		{
			"label": _("Avg First Response"),
			"fieldname": "avg_first_response",
			"fieldtype": "Duration",
			"width": 200,
		},
		{
			"label": _("Avg Follow-up Time"),
			"fieldname": "avg_followup_time",
			"fieldtype": "Duration",
			"width": 200,
		},
		{
			"label": _("SLA Met %"),
			"fieldname": "sla_met",
			"fieldtype": "Percent",
			"width": 200,
		},
		{
			"label": _("Fastest Response"),
			"fieldname": "fastest_response",
			"fieldtype": "Duration",
			"width": 200,
		},
		{
			"label": _("Slowest Response"),
			"fieldname": "slowest_response",
			"fieldtype": "Duration",
		},
	]
	return columns
