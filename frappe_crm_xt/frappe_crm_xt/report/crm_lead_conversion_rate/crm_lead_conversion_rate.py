# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe import _, qb
from frappe.query_builder.functions import Count, Round, Sum
from frappe.utils import getdate
from pypika import Case, Criterion, CustomFunction


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters):
	fiscal_year = get_fiscal_year(fiscal_year=filters.get("year"), as_dict=True)

	month = int(filters.get("month", "0"))

	start_date = fiscal_year.year_start_date
	end_date = fiscal_year.year_end_date

	# sales_person: use `deal_owner` field on CRM Deal
	assignee_expr = "d.deal_owner"

	subquery_month_cond = ""
	main_month_cond = ""
	if month:
		subquery_month_cond = f" AND MONTH(l.creation) = {int(month)}"
		main_month_cond = " AND MONTH(d.creation) = %s"

	query = f"""
	SELECT
		{assignee_expr} AS sales_person,
		(
			SELECT COUNT(*)
			FROM `tabCRM Lead` l
			WHERE l.lead_owner = {assignee_expr}
			AND l.creation BETWEEN %s AND %s
			{subquery_month_cond}
		) AS leads_assigned,
		COUNT(d.name) AS deals_created,
		SUM(CASE WHEN d.status = 'Won' THEN 1 ELSE 0 END) AS deals_won,
		ROUND(SUM(CASE WHEN d.status = 'Won' THEN 1 ELSE 0 END) * 100.0 / COUNT(d.name), 2) AS conversion_rate,
		d.creation AS period
	FROM `tabCRM Deal` d
		LEFT JOIN `tabUser` u ON u.name = {assignee_expr}
		WHERE {assignee_expr} IS NOT NULL
	  AND d.creation BETWEEN %s AND %s
	  {main_month_cond}
		GROUP BY {assignee_expr}, YEAR(d.creation), MONTH(d.creation)
	"""

	# params for main query: if month provided, params already include month at end
	if month:
		# params currently [start_date, end_date, month] -> we need start,end for subquery and start,end,month for main
		sql_params = [start_date, end_date, start_date, end_date, month]
	else:
		sql_params = [start_date, end_date, start_date, end_date]

	result = frappe.db.sql(query, tuple(sql_params), as_dict=True)
	for row in result:
		row["period"] = getdate(row["period"]).strftime("%B, %Y")

	return result


def get_columns():
	columns = [
		{
			"label": _("Sales Person"),
			"fieldname": "sales_person",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Leads Assigned"),
			"fieldname": "leads_assigned",
			"fieldtype": "Float",
			"width": 200,
		},
		{
			"label": _("Deals Created"),
			"fieldname": "deals_created",
			"fieldtype": "Float",
			"width": 200,
		},
		{
			"label": _("Deals Won"),
			"fieldname": "deals_won",
			"fieldtype": "Float",
			"width": 200,
		},
		{
			"label": _("Conversion Rate"),
			"fieldname": "conversion_rate",
			"fieldtype": "Percent",
			"width": 200,
		},
		{"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 200},
	]
	return columns
