"""Sync ``CRM Dashboard`` child-table selections into the rendered layout.

``CRM Dashboard`` gains two custom child tables (see setup/custom_fields.json):

* ``charts`` → Dashboard Chart Link  (field ``chart``)
* ``cards``  → Number Card Link      (field ``card``)

They let an admin drop native Desk Dashboard Charts / Number Cards (including
Report-backed ones) onto the CRM frontend dashboard straight from the Desk form,
without touching the CRM app. This module reconciles those rows into the
``layout`` JSON that the CRM frontend actually renders; ``api.dashboard`` then
resolves the resulting ``deskchart::`` / ``deskcard::`` items at read time.

Reconciliation is *delta-based*: we only add/remove layout items for child rows
that changed in this save. A plain frontend layout edit (child tables untouched)
is left alone, so a widget removed in the CRM UI stays removed.
"""

import frappe

from frappe_crm_xt.api.dashboard import DESK_CARD_PREFIX, DESK_CHART_PREFIX

# Grid geometry mirrors CRM's default_manager_dashboard_layout (20-column grid).
_NUMBER_SIZE = {"w": 4, "h": 3}
_CHART_SIZE = {"w": 10, "h": 9}
_DONUT_TYPES = ("Pie", "Donut")


def validate(doc, method=None):
	sync_layout_from_child_tables(doc)


def sync_layout_from_child_tables(doc):
	"""Add/remove layout items for charts/cards rows that changed in this save."""
	desired = _desired_desk_items(doc)
	previous = _desired_desk_items(doc.get_doc_before_save())  # {} for a new doc

	added = {name: widget for name, widget in desired.items() if name not in previous}
	removed = {name for name in previous if name not in desired}

	if not added and not removed:
		return

	layout = frappe.parse_json(doc.layout or "[]")
	if not isinstance(layout, list):
		layout = []

	if removed:
		layout = [item for item in layout if item.get("name") not in removed]

	present = {item.get("name") for item in layout}
	for name, widget_type in added.items():
		if name in present:
			continue
		layout.append(_new_layout_item(name, widget_type, layout))
		present.add(name)

	doc.layout = frappe.as_json(layout)


def _desired_desk_items(doc):
	"""Map of layout ``name`` → widget ``type`` for the doc's linked charts/cards."""
	if not doc:
		return {}

	items = {}
	for row in doc.get("cards") or []:
		card = row.get("card")
		if card:
			items[f"{DESK_CARD_PREFIX}{card}"] = "number_chart"

	for row in doc.get("charts") or []:
		chart = row.get("chart")
		if not chart:
			continue
		chart_type = frappe.db.get_value("Dashboard Chart", chart, "type")
		items[f"{DESK_CHART_PREFIX}{chart}"] = "donut_chart" if chart_type in _DONUT_TYPES else "axis_chart"

	return items


def _new_layout_item(name, widget_type, layout):
	size = _NUMBER_SIZE if widget_type == "number_chart" else _CHART_SIZE
	return {
		"name": name,
		"type": widget_type,
		"layout": {"x": 0, "y": _next_row(layout), "w": size["w"], "h": size["h"], "i": name},
	}


def _next_row(layout):
	"""First free grid row below every existing item (append at the bottom)."""
	bottom = 0
	for item in layout:
		box = item.get("layout") or {}
		bottom = max(bottom, (box.get("y") or 0) + (box.get("h") or 0))
	return bottom
