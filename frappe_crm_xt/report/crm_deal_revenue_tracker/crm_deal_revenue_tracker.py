# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from erpnext.setup.utils import get_exchange_rate
from frappe import _, qb


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters=None):
	start_date = filters.get("from_date") if filters else None
	end_date = filters.get("to_date") if filters else None

	Deal = qb.DocType("CRM Deal")
	Organization = qb.DocType("CRM Organization")
	User = qb.DocType("User")

	query = (
		qb.from_(Deal)
		.left_join(Organization)
		.on(Deal.org == Organization.name)
		.left_join(User)
		.on(Deal.custom_sales_manager == User.name)
		.select(
			Deal.name.as_("deal_name"),
			Deal.title.as_("deal_title"),
			Deal.status.as_("deal_status"),
			Organization.name.as_("organization"),
			Organization.title.as_("org_title"),
			Deal.value.as_("deal_value"),
			Deal.currency.as_("currency"),
			Deal.modified.as_("last_updated"),
			User.full_name.as_("sales_manager"),
			Deal.custom_deal_type,
			Deal.custom_complexity_level,
		)
	)

	if start_date and end_date:
		query = query.where(Deal.modified[start_date:end_date])

	result = query.run(as_dict=True)
	return get_result(result)


def get_result(result):
	"""Process and enrich deal data with currency conversion"""
	for row in result:
		if row.get("currency") and row.get("currency") != "USD":
			exchange_rate = get_exchange_rate(row.get("currency"), "USD")
			row["usd_value"] = row.get("deal_value", 0) * (exchange_rate or 1)
		else:
			row["usd_value"] = row.get("deal_value", 0)

	return result


def get_columns():
	columns = [
		{
			"label": _("Deal Name"),
			"fieldname": "deal_name",
			"fieldtype": "Link",
			"options": "CRM Deal",
			"width": 150,
		},
		{
			"label": _("Deal Title"),
			"fieldname": "deal_title",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Status"),
			"fieldname": "deal_status",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Organization"),
			"fieldname": "organization",
			"fieldtype": "Link",
			"options": "CRM Organization",
			"width": 150,
		},
		{
			"label": _("Organization Title"),
			"fieldname": "org_title",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Deal Value"),
			"fieldname": "deal_value",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Data",
			"width": 80,
		},
		{
			"label": _("USD Value"),
			"fieldname": "usd_value",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Sales Manager"),
			"fieldname": "sales_manager",
			"fieldtype": "Link",
			"options": "User",
			"width": 150,
		},
		{
			"label": _("Deal Type"),
			"fieldname": "custom_deal_type",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Complexity"),
			"fieldname": "custom_complexity_level",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Last Updated"),
			"fieldname": "last_updated",
			"fieldtype": "Datetime",
			"width": 180,
		},
	]
	return columns
