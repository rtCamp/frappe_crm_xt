"""Dynamic CRM dashboard bridge.

Overrides ``crm.api.dashboard.get_dashboard`` / ``get_chart`` (registered in
hooks.py ``override_whitelisted_methods``) so the Frappe CRM frontend dashboard
can render widgets sourced from native Frappe **Desk** artifacts:

* **Dashboard Charts** (``Count`` / ``Sum`` / ``Average`` / ``Group By`` and
  ``Report``-backed) and **Number Cards** (``Document Type`` / ``Report``),
* grouped on a single Frappe **Dashboard** (default name ``"Frappe CRM
  Dashboard"``, overridable via the ``crm_desk_dashboard`` hook).

Every chart/card on that Dashboard is auto-injected into the CRM
``Manager Dashboard`` layout and its data is computed live and reshaped into the
CRM frontend's chart-config shapes (``number_chart`` / ``axis_chart`` /
``donut_chart``). Built-in CRM charts are delegated, unchanged, to the upstream
``crm.api.dashboard`` functions.

Nothing in ``apps/crm`` is modified, and no custom storage doctype is
introduced — the Desk dashboard builder UI is the management surface.
"""

import frappe
from crm.api import dashboard as crm_dashboard
from crm.fcrm.doctype.crm_dashboard.crm_dashboard import create_default_manager_dashboard
from crm.utils import sales_user_only
from frappe import _
from frappe.desk.doctype.dashboard_chart.dashboard_chart import get as dashboard_chart_get
from frappe.desk.doctype.number_card.number_card import get_result as number_card_get_result
from frappe.desk.query_report import run as run_query_report

DESK_CHART_PREFIX = "deskchart::"
DESK_CARD_PREFIX = "deskcard::"
DEFAULT_SOURCE_DASHBOARD = "Frappe CRM Dashboard"


# ─── whitelisted overrides ──────────────────────────────────────────────────


@frappe.whitelist()
@sales_user_only
def get_dashboard(from_date: str | None = None, to_date: str | None = None, user: str | None = None):
	"""Return the CRM dashboard layout with each item's ``data`` populated.

	Built-in CRM charts resolve via the upstream functions; charts/cards from the
	source Desk Dashboard are auto-injected and resolved here.
	"""
	from_date, to_date, user = _normalize(from_date, to_date, user)

	layout = _load_layout()
	_inject_desk_widgets(layout)

	for item in layout:
		item["data"] = _resolve_chart_data(item.get("name"), item.get("type"), from_date, to_date, user)

	return layout


@frappe.whitelist()
@sales_user_only
def get_chart(
	name: str,
	type: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	user: str | None = None,
):
	"""Return a single chart's data (built-in or Desk-backed)."""
	from_date, to_date, user = _normalize(from_date, to_date, user)

	data = _resolve_chart_data(name, type, from_date, to_date, user)
	if data is None:
		return {"error": _("Invalid chart name")}
	return data


# ─── layout assembly ────────────────────────────────────────────────────────


def _normalize(from_date, to_date, user):
	"""Replicate upstream period defaulting + Sales-User self-scoping."""
	if not from_date or not to_date:
		from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
		to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

	roles = frappe.get_roles(frappe.session.user)
	is_manager = "Sales Manager" in roles or "System Manager" in roles
	if "Sales User" in roles and not is_manager:
		user = frappe.session.user

	return from_date, to_date, user


def _load_layout():
	"""Load the Manager Dashboard layout (creating the default if absent)."""
	if not frappe.db.exists("CRM Dashboard", "Manager Dashboard"):
		layout = frappe.parse_json(create_default_manager_dashboard())
		frappe.db.commit()
		return layout
	return frappe.parse_json(frappe.db.get_value("CRM Dashboard", "Manager Dashboard", "layout") or "[]")


def _source_dashboard_name():
	"""Name of the Desk Dashboard to surface (hook override → default → None)."""
	hooked = frappe.get_hooks("crm_desk_dashboard")
	name = hooked[-1] if hooked else DEFAULT_SOURCE_DASHBOARD
	return name if name and frappe.db.exists("Dashboard", name) else None


def _desk_widget_items():
	"""Layout stubs (``name`` + CRM ``type``) for the source Dashboard's widgets.

	Cards first, then charts — mirroring the Desk dashboard order. Heatmap and
	Custom charts are skipped (no CRM renderer / no generic resolution). The
	Dashboard membership is read directly (not permission-filtered) — data-level
	permissions are enforced later when each widget is actually run.
	"""
	name = _source_dashboard_name()
	if not name:
		return []

	dashboard = frappe.get_doc("Dashboard", name)
	items = []

	for link in dashboard.cards or []:
		if link.card and frappe.db.exists("Number Card", link.card):
			items.append({"name": DESK_CARD_PREFIX + link.card, "type": "number_chart"})

	for link in dashboard.charts or []:
		if not link.chart:
			continue
		meta = frappe.db.get_value("Dashboard Chart", link.chart, ["chart_type", "type"], as_dict=True)
		if not meta or meta.chart_type == "Custom" or meta.type == "Heatmap":
			continue
		crm_type = "donut_chart" if meta.type in ("Pie", "Donut") else "axis_chart"
		items.append(
			{"name": DESK_CHART_PREFIX + link.chart, "type": crm_type, "full": link.get("width") == "Full"}
		)

	return items


def _inject_desk_widgets(layout):
	"""Append layout items for Desk widgets not already present (idempotent)."""
	existing = {item.get("name") for item in layout}
	widgets = _desk_widget_items()
	if not widgets:
		return

	next_y = max(
		(
			item["layout"]["y"] + item["layout"]["h"]
			for item in layout
			if isinstance(item.get("layout"), dict)
		),
		default=0,
	)
	x = row_height = 0

	for widget in widgets:
		if widget["name"] in existing:
			continue

		if widget["type"] == "number_chart":
			width, height = 4, 3
		else:
			width, height = (20 if widget.get("full") else 10), 7

		if x + width > 20:
			x, next_y, row_height = 0, next_y + row_height, 0

		layout.append(
			{
				"name": widget["name"],
				"type": widget["type"],
				"layout": {"x": x, "y": next_y, "w": width, "h": height, "i": widget["name"]},
			}
		)
		existing.add(widget["name"])
		x += width
		row_height = max(row_height, height)


def _resolve_chart_data(name, widget_type, from_date, to_date, user):
	"""Dispatch a layout item to its data source."""
	if not name:
		return None

	builtin = f"get_{name}"
	if hasattr(crm_dashboard, builtin):
		return getattr(crm_dashboard, builtin)(from_date, to_date, user)

	if name.startswith(DESK_CHART_PREFIX):
		return _resolve_dashboard_chart(name[len(DESK_CHART_PREFIX) :], widget_type, from_date, to_date)

	if name.startswith(DESK_CARD_PREFIX):
		return _resolve_number_card(name[len(DESK_CARD_PREFIX) :])

	return None


# ─── Desk Dashboard Chart → CRM config ──────────────────────────────────────


def _resolve_dashboard_chart(chart_name, widget_type, from_date, to_date):
	if not frappe.db.exists("Dashboard Chart", chart_name):
		return _empty_config(widget_type)

	try:
		chart = frappe.get_doc("Dashboard Chart", chart_name)
		if chart.chart_type == "Report":
			labels, datasets = _report_series(chart.report_name, chart.filters_json, chart)
		elif chart.chart_type in ("Count", "Sum", "Average", "Group By"):
			config = (
				dashboard_chart_get(chart_name=chart.name, from_date=from_date, to_date=to_date, refresh=1)
				or {}
			)
			labels = config.get("labels") or []
			datasets = config.get("datasets") or []
		else:
			return _empty_config(widget_type)
	except Exception:
		frappe.clear_last_message()
		_log_failure("Dashboard Chart", chart_name)
		return _empty_config(widget_type)

	title = chart.get("chart_name") or chart_name
	if (chart.type or "Bar") in ("Pie", "Donut"):
		return _to_donut(title, labels, datasets)
	return _to_axis(title, labels, datasets, "line" if chart.type == "Line" else "bar")


def _report_series(report_name, filters_json, chart):
	"""Run a Report and return (labels, datasets) per the chart's x_field/y_axis."""
	result = (
		run_query_report(
			report_name=report_name, filters=_report_filters(filters_json), ignore_prepared_report=True
		)
		or {}
	)

	report_chart = result.get("chart")
	if chart.get("use_report_chart") and report_chart and report_chart.get("data"):
		data = report_chart["data"]
		return (data.get("labels") or []), (data.get("datasets") or [])

	columns = result.get("columns") or []
	rows = result.get("result") or []
	if result.get("add_total_row") and rows:
		rows = rows[:-1]

	label_of = {
		c.get("fieldname"): (c.get("label") or c.get("fieldname")) for c in columns if isinstance(c, dict)
	}
	x_field = chart.get("x_field")
	y_fields = [row.y_field for row in (chart.y_axis or []) if row.y_field]

	labels = [row.get(x_field) for row in rows] if x_field else list(range(len(rows)))
	datasets = [
		{"name": label_of.get(y, y), "values": [_to_number(row.get(y)) for row in rows]} for y in y_fields
	]
	return labels, datasets


# ─── Desk Number Card → CRM number_chart ────────────────────────────────────


def _resolve_number_card(card_name):
	if not frappe.db.exists("Number Card", card_name):
		return {"title": "", "value": 0}

	prefix = suffix = None
	try:
		card = frappe.get_doc("Number Card", card_name)
		if card.type == "Report":
			result = (
				run_query_report(
					report_name=card.report_name,
					filters=_report_filters(card.filters_json),
					ignore_prepared_report=True,
				)
				or {}
			)
			rows = result.get("result") or []
			if result.get("add_total_row") and rows:
				rows = rows[:-1]
			field = card.report_field
			values = [_to_number(r.get(field)) for r in rows if field and r.get(field) is not None]
			value = _reduce(values, card.report_function or "Sum")
			# Derive prefix/suffix from the column's fieldtype, not card.currency
			# (Frappe defaults card.currency even on percentage/duration columns).
			prefix, suffix = _number_affixes(_column_fieldtype(result.get("columns"), field))
		elif card.type == "Document Type":
			value = number_card_get_result(doc=card, filters=card.filters_json)
			if card.get("currency"):
				prefix = frappe.db.get_value("Currency", card.currency, "symbol") or None
		else:
			value = 0
	except Exception:
		frappe.clear_last_message()
		_log_failure("Number Card", card_name)
		return {"title": card_name, "value": 0}

	out = {"title": card.get("label") or card_name, "value": value}
	if prefix:
		out["prefix"] = prefix
	if suffix:
		out["suffix"] = suffix
	return out


# ─── shaping helpers ────────────────────────────────────────────────────────

# Defensive caps: a report-backed chart can have arbitrarily many rows (e.g. one
# per organization). Beyond these limits we keep the top-N points by value so the
# frontend stays responsive; the subtitle records what was dropped.
MAX_AXIS_POINTS = 25
MAX_DONUT_SLICES = 12


def _to_axis(title, labels, datasets, series_type):
	names = _unique_names([(ds.get("name") if isinstance(ds, dict) else None) for ds in datasets])
	data = []
	for i, label in enumerate(labels):
		item = {"label": label}
		for j, ds in enumerate(datasets):
			values = (ds.get("values") if isinstance(ds, dict) else []) or []
			item[names[j]] = _to_number(values[i]) if i < len(values) else 0
		data.append(item)

	def row_total(row):
		return 0
		# return sum(v for k, v in row.items() if k != "label" and isinstance(v, (int, float)))

	data, subtitle = _cap_points(data, row_total, MAX_AXIS_POINTS)
	config = {
		"data": data,
		"title": title,
		"xAxis": {"key": "label", "title": "", "type": "category"},
		"yAxis": {"title": ""},
		"series": [{"name": name, "type": series_type} for name in names],
	}
	if subtitle:
		config["subtitle"] = subtitle
	return config


def _to_donut(title, labels, datasets):
	values = []
	if datasets and isinstance(datasets[0], dict):
		values = datasets[0].get("values") or []
	data = [
		{"label": labels[i], "value": _to_number(values[i]) if i < len(values) else 0}
		for i in range(len(labels))
	]
	data, subtitle = _cap_points(data, lambda row: row.get("value", 0), MAX_DONUT_SLICES)
	config = {"data": data, "title": title, "categoryColumn": "label", "valueColumn": "value"}
	if subtitle:
		config["subtitle"] = subtitle
	return config


def _cap_points(rows, value_getter, limit):
	"""Keep the top-``limit`` rows by value (only when exceeded), else original order."""
	if len(rows) <= limit:
		return rows, None
	total = len(rows)
	capped = sorted(rows, key=value_getter, reverse=True)[:limit]
	return capped, _("Top {0} of {1}").format(limit, total)


def _empty_config(widget_type):
	if widget_type == "number_chart":
		return {"title": "", "value": 0}
	if widget_type == "donut_chart":
		return {"data": [], "title": "", "categoryColumn": "label", "valueColumn": "value"}
	return {
		"data": [],
		"title": "",
		"xAxis": {"key": "label", "type": "category"},
		"yAxis": {"title": ""},
		"series": [],
	}


def _unique_names(raw_names):
	seen, out = {}, []
	for i, name in enumerate(raw_names):
		name = name or f"Series {i + 1}"
		if name in seen:
			seen[name] += 1
			name = f"{name} ({seen[name]})"
		else:
			seen[name] = 1
		out.append(name)
	return out


def _report_filters(filters_json):
	"""Report ``execute(filters)`` expects a dict — coerce anything else to {}."""
	try:
		parsed = frappe.parse_json(filters_json) if filters_json else {}
	except (ValueError, TypeError):
		parsed = {}
	return parsed if isinstance(parsed, dict) else {}


def _column_fieldtype(columns, fieldname):
	for column in columns or []:
		if isinstance(column, dict) and column.get("fieldname") == fieldname:
			return column.get("fieldtype")
	return None


def _number_affixes(fieldtype):
	"""(prefix, suffix) for a number card, inferred from its column fieldtype."""
	if fieldtype == "Percent":
		return None, "%"
	if fieldtype == "Currency":
		currency = frappe.db.get_default("currency")
		symbol = frappe.db.get_value("Currency", currency, "symbol") if currency else None
		return symbol, None
	return None, None


def _to_number(value):
	try:
		return frappe.utils.flt(value)
	except (ValueError, TypeError):
		return 0


def _reduce(values, fn):
	if not values:
		return 0
	if fn == "Average":
		return sum(values) / len(values)
	if fn == "Minimum":
		return min(values)
	if fn == "Maximum":
		return max(values)
	return sum(values)


def _log_failure(doctype, name):
	frappe.log_error(
		title="CRM dynamic dashboard: widget resolution failed",
		message=f"{doctype} '{name}'\n\n{frappe.get_traceback()}",
	)
