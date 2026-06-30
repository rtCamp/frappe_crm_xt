import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def after_install():
	"""Apply customisations and seed default field layouts (install only)."""
	install()
	install_fields_layout()
	install_desk_dashboard()


def install():
	"""Apply all rtcamp-side CRM customisations (idempotent; runs on migrate)."""
	install_custom_fields()
	install_property_setters()


def install_custom_fields():
	"""Install / refresh custom fields from custom_fields.json."""
	data_file = Path(__file__).parent / "custom_fields.json"
	create_custom_fields(json.loads(data_file.read_text()), update=True)


def install_property_setters():
	"""Install / refresh property setters from property_setters.json."""
	data_file = Path(__file__).parent / "property_setters.json"
	for ps in json.loads(data_file.read_text()):
		make_property_setter(
			doctype=ps["doctype"],
			fieldname=ps.get("fieldname"),
			property=ps["property"],
			value=ps["value"],
			property_type=ps["property_type"],
			validate_fields_for_doctype=False,
			for_doctype=ps.get("for_doctype", False),
		)


def install_fields_layout():
	"""Seed/refresh default CRM field layouts, overwriting existing ones (install only)."""
	data_file = Path(__file__).parent / "crm_fields_layout.json"
	for entry in json.loads(data_file.read_text()):
		if frappe.db.exists("CRM Fields Layout", entry["name"]):
			doc = frappe.get_doc("CRM Fields Layout", entry["name"])
			doc.layout = entry["layout"]
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(
				{
					"doctype": "CRM Fields Layout",
					"dt": entry["dt"],
					"type": entry["type"],
					"layout": entry["layout"],
				}
			).insert(ignore_permissions=True)


# Native Desk Dashboard surfaced on the CRM frontend dashboard (see
# frappe_crm_xt.api.dashboard). Each chart/card is backed by a report shipped by
# this app; the Desk dashboard UI (/app/dashboard) is the management surface.
DESK_DASHBOARD_NAME = "Frappe CRM Dashboard"

DESK_DASHBOARD_CHARTS = [
	{
		"chart_name": "CRM Deals by Stage",
		"report": "CRM Deal Pipeline",
		"type": "Donut",
		"x_field": "stage",
		"y_fields": ["deal_count"],
		"width": "Half",
	},
	{
		"chart_name": "CRM Organizations: Deals vs Leads",
		"report": "CRM Organization Stats",
		"type": "Bar",
		"x_field": "title",
		"y_fields": ["deals_count", "leads_count"],
		"width": "Full",
	},
]

DESK_DASHBOARD_CARDS = [
	{
		"label": "CRM Avg SLA Met %",
		"report": "CRM Average Response",
		"report_field": "sla_met",
		"report_function": "Average",
	},
]


def install_desk_dashboard():
	"""Seed the 'CRM' Desk Dashboard with Report-backed charts/cards (idempotent).

	Skips any chart/card whose report is missing, and never duplicates existing
	charts, cards, or dashboard links — safe to re-run.
	"""
	chart_links = []
	for spec in DESK_DASHBOARD_CHARTS:
		if not frappe.db.exists("Report", spec["report"]):
			continue
		if not frappe.db.exists("Dashboard Chart", spec["chart_name"]):
			frappe.get_doc(
				{
					"doctype": "Dashboard Chart",
					"chart_name": spec["chart_name"],
					"chart_type": "Report",
					"report_name": spec["report"],
					"type": spec["type"],
					"x_field": spec["x_field"],
					"y_axis": [{"y_field": y} for y in spec["y_fields"]],
					"filters_json": "{}",
					"is_public": 1,
				}
			).insert(ignore_permissions=True)
		chart_links.append({"chart": spec["chart_name"], "width": spec["width"]})

	card_links = []
	for spec in DESK_DASHBOARD_CARDS:
		if not frappe.db.exists("Report", spec["report"]):
			continue
		card_name = frappe.db.get_value("Number Card", {"label": spec["label"]})
		if not card_name:
			card = frappe.get_doc(
				{
					"doctype": "Number Card",
					"label": spec["label"],
					"type": "Report",
					"report_name": spec["report"],
					"report_field": spec["report_field"],
					"report_function": spec["report_function"],
					"filters_json": "[]",
					"is_public": 1,
				}
			).insert(ignore_permissions=True)
			card_name = card.name
		card_links.append(card_name)

	if not chart_links:
		# Dashboard requires at least one chart; nothing to seed without reports.
		return

	if frappe.db.exists("Dashboard", DESK_DASHBOARD_NAME):
		dashboard = frappe.get_doc("Dashboard", DESK_DASHBOARD_NAME)
	else:
		dashboard = frappe.get_doc({"doctype": "Dashboard", "dashboard_name": DESK_DASHBOARD_NAME})

	existing_charts = {row.chart for row in dashboard.charts}
	for link in chart_links:
		if link["chart"] not in existing_charts:
			dashboard.append("charts", link)

	existing_cards = {row.card for row in dashboard.cards}
	for card_name in card_links:
		if card_name not in existing_cards:
			dashboard.append("cards", {"card": card_name})

	dashboard.save(ignore_permissions=True)
