# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from erpnext.accounts.utils import get_fiscal_year
from frappe import _, get_all, qb
from frappe.query_builder.functions import Count, Sum
from frappe.utils import getdate
from pypika import Case


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters=None):
	"""Get CRM Deal pipeline status and value distribution"""
	Deal = qb.DocType("CRM Deal")

	query = (
		qb.from_(Deal)
		.select(
			Deal.status.as_("stage"),
			Count(Deal.name).as_("deal_count"),
			Sum(Deal.annual_revenue).as_("total_value"),
		)
		.groupby(Deal.status)
	)

	result = query.run(as_dict=True)

	# Calculate percentages and add metadata
	total_deals = sum(row.get("deal_count", 0) for row in result)
	total_value = sum(row.get("total_value", 0) for row in result)

	for row in result:
		row["deal_percentage"] = (
			round((row.get("deal_count", 0) / total_deals * 100), 2) if total_deals > 0 else 0
		)
		row["value_percentage"] = (
			round((row.get("total_value", 0) / total_value * 100), 2) if total_value > 0 else 0
		)

	return result


def get_columns():
	columns = [
		{
			"label": _("Deal Stage"),
			"fieldname": "stage",
			"fieldtype": "Data",
			"width": 150,
		},
		{
			"label": _("Deal Count"),
			"fieldname": "deal_count",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("% of Deals"),
			"fieldname": "deal_percentage",
			"fieldtype": "Percent",
			"width": 120,
		},
		{
			"label": _("Total Value"),
			"fieldname": "total_value",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("% of Value"),
			"fieldname": "value_percentage",
			"fieldtype": "Percent",
			"width": 120,
		},
	]
	return columns
