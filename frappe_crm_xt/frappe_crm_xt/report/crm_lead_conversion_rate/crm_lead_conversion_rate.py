# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

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

	Month = CustomFunction("MONTH", ["month"])
	Year = CustomFunction("YEAR", ["year"])

	Deal = qb.DocType("CRM Deal")
	Lead = qb.DocType("CRM Lead")
	User = qb.DocType("User")

	sub_query_where_conditions = [
		Lead.custom_assigned_to == Deal.custom_sales_manager,
		Lead.creation[fiscal_year.year_start_date : fiscal_year.year_end_date],
	]
	if month:
		sub_query_where_conditions.append(Month(Lead.creation) == month)

	query_where_conditions = [
		Deal.custom_sales_manager.isnotnull(),
		Deal.creation[fiscal_year.year_start_date : fiscal_year.year_end_date],
	]
	if month:
		query_where_conditions.append(Month(Deal.creation) == month)

	query = (
		qb.from_(Deal)
		.join(User)
		.on(Deal.custom_sales_manager == User.name)
		.select(
			User.full_name.as_("sales_person"),
			(qb.from_(Lead).select(Count("*")).where(Criterion.all(sub_query_where_conditions))).as_(
				"leads_assigned"
			),
			Count(Deal.name).as_("deals_created"),
			Sum(Case().when(Deal.status == "Won", 1).else_(0)).as_("deals_won"),
			Round(
				Sum(Case().when(Deal.status == "Won", 1).else_(0)) * 100.0 / Count(Deal.name),
				2,
			).as_("conversion_rate"),
			Deal.creation.as_("period"),
		)
		.where(Criterion.all(query_where_conditions))
		.groupby(Deal.custom_sales_manager, Year(Deal.creation), Month(Deal.creation))
	)
	result = query.run(as_dict=True)
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
