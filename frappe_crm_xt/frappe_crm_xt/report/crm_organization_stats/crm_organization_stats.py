# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe import _, qb
from frappe.query_builder.functions import Count


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters=None):
	Organization = qb.DocType("CRM Organization")
	Deal = qb.DocType("CRM Deal")
	Lead = qb.DocType("CRM Lead")

	query = qb.from_(Organization).select(
		Organization.name,
		Organization.organization_name.as_("title"),
		Organization.annual_revenue,
	)

	# Add filters if provided
	if filters and filters.get("org_type"):
		query = query.where(Organization.custom_org_type == filters.get("org_type"))

	result = query.run(as_dict=True)

	# Add related deals and leads count
	for org in result:
		deals_count = qb.from_(Deal).select(Count("*")).where(Deal.organization == org.get("name")).run()
		leads_count = qb.from_(Lead).select(Count("*")).where(Lead.organization == org.get("name")).run()

		org["deals_count"] = deals_count[0][0] if deals_count else 0
		org["leads_count"] = leads_count[0][0] if leads_count else 0

	return result


def get_columns():
	columns = [
		{
			"label": _("Organization Name"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "CRM Organization",
			"width": 200,
		},
		{
			"label": _("Title"),
			"fieldname": "title",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Annual Revenue"),
			"fieldname": "annual_revenue",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Deals Count"),
			"fieldname": "deals_count",
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"label": _("Leads Count"),
			"fieldname": "leads_count",
			"fieldtype": "Int",
			"width": 100,
		},
	]
	return columns
