# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from frappe import _, get_meta, parse_json, qb
from frappe.utils import add_days, getdate
from frappe.utils import today as get_today


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_data(filters=None):
	filters = filters or {}
	to_date = getdate(filters.get("to_date") or get_today())
	from_date = getdate(filters.get("from_date") or add_days(to_date, -30))
	meta = get_meta("CRM Deal")
	Deal = qb.DocType("CRM Deal")
	Version = qb.DocType("Version")
	query = (
		qb.from_(Version)
		.select(Version.docname, Version.owner, Version.creation, Version.data, Deal.title)
		.left_join(Deal)
		.on(Version.docname == Deal.name)
		.where(
			(Version.ref_doctype == "CRM Deal")
			& (Version.creation >= from_date)
			& (Version.creation < add_days(to_date, 1))
			& (Version.data.isnotnull())
		)
	)
	versions = query.run(as_dict=True)

	results = []
	for version in versions:
		res = []
		updated_data = parse_json(version.data).get("changed", [])
		for fields in updated_data:
			try:
				label = meta.get_field(fields[0]).label
			except Exception:
				label = fields[0]
			res.append(
				{
					"deal_name": version.docname,
					"deal_title": version.title or version.docname,
					"fields_updated": label or fields[0],
					"previous_value": fields[1],
					"updated_value": fields[2],
					"changed_by": version.owner,
					"updated_on": version.creation,
				}
			)
		results.extend(res)

	return results


def get_columns():
	columns = [
		{
			"label": _("Deal Name"),
			"fieldname": "deal_name",
			"fieldtype": "Link",
			"options": "CRM Deal",
			"width": 200,
		},
		{
			"label": _("Deal Title"),
			"fieldname": "deal_title",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Fields Updated"),
			"fieldname": "fields_updated",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Previous Value"),
			"fieldname": "previous_value",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Updated Value"),
			"fieldname": "updated_value",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Changed By"),
			"fieldname": "changed_by",
			"fieldtype": "Link",
			"options": "User",
			"width": 200,
		},
		{
			"label": _("Updated On"),
			"fieldname": "updated_on",
			"fieldtype": "Datetime",
			"width": 200,
		},
	]
	return columns
