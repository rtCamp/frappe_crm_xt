# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe import _, qb
from frappe.query_builder.functions import Avg, Count, Max, Min, Round, Sum
from frappe.utils import add_days, getdate
from pypika import Case


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters=filters)
	return columns, data


def get_data(filters=None):
	Deal = qb.DocType("CRM Deal")
	User = qb.DocType("User")

	today = getdate()
	weekday = today.weekday()

	last_monday = add_days(today, -(weekday + 7))
	last_sunday = add_days(today, -(weekday + 1))

	query = (
		qb.from_(Deal)
		.join(User)
		.on(Deal.custom_sales_manager == User.name)
		.select(
			User.full_name.as_("sales_person"),
			Avg(Deal.custom_first_response_time).as_("avg_first_response"),
			Avg(Deal.custom_last_response_time).as_("avg_followup_time"),
			Round(
				Sum(Case().when(Deal.sla_status == "Fulfilled", 1).else_(0)) * 100.0 / Count(Deal.name),
				2,
			).as_("sla_met"),
			Min(Deal.custom_first_response_time).as_("fastest_response"),
			Max(Deal.custom_first_response_time).as_("slowest_response"),
		)
		.where(Deal.modified[last_monday:last_sunday])
		.groupby(Deal.custom_sales_manager)
	)

	return query.run(as_dict=True)


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
