"""Maintains CRM Deal `custom_incoming_sla_due`: the moment an unanswered incoming email
falls due = the incoming-email time advanced by the configured amount — either N **working
days** or N calendar **hours** (`incoming_alert_unit`) — always holiday-aware, so the due lands
on a working day (a Fri incoming with the weekend off falls on Mon, not Sat).

The actual alert is sent by a *native* Frappe Notification with event "Minutes After" on this
field — Frappe's offset scheduler (every 5 min) fires it and dedups via its own
`datetime_last_run`. This module only keeps the datetime correct; it does no sending.

Called from the Gmail-thread sync (doc_events/gmail_thread.py), the single writer of the
incoming/response timestamps — some of those writes use db_set and bypass doc-event hooks,
so a CRM Deal hook wouldn't reliably see them. Config lives on CRM XT Settings and is shared
with the deal-inactivity digest (threshold, holiday list, weekend fallback).
"""

import frappe
from frappe.utils import add_days, get_datetime, getdate

from frappe_crm_xt.utils import holiday as hu

SETTINGS = "CRM XT Settings"
DEFAULT_WORKING_DAYS = 1
CLOSED_STATUSES = ("Won", "Lost")
DUE = "custom_incoming_sla_due"
INCOMING = "custom_last_incoming_email_time"
RESPONSE_FIELDS = ("last_responded_on", "custom_last_response_by")


def refresh_incoming_due(parent):
	"""(Re)compute or clear `custom_incoming_sla_due` on a CRM Deal from its current
	incoming-email / reply timestamps. Writes only when the value changes."""
	if getattr(parent, "doctype", None) != "CRM Deal" or not parent.meta.has_field(DUE):
		return
	due = _compute_due(parent)
	if _same(parent.get(DUE), due):
		return
	parent.db_set(DUE, due, update_modified=False)


def _compute_due(parent):
	"""The SLA-due datetime, or None when nothing is pending (feature off, no incoming
	email, already answered, or deal closed)."""
	if not parent.meta.has_field(INCOMING):
		return None
	if not frappe.db.exists("DocType", SETTINGS):
		return None
	settings = frappe.get_cached_doc(SETTINGS)
	if not settings.get("incoming_alert_enabled"):
		return None

	incoming = parent.get(INCOMING)
	if not incoming or parent.get("status") in CLOSED_STATUSES:
		return None
	incoming = get_datetime(incoming)

	# answered — a reply strictly after the incoming email clears the clock
	responses = [
		get_datetime(parent.get(f)) for f in RESPONSE_FIELDS if parent.meta.has_field(f) and parent.get(f)
	]
	if responses and max(responses) > incoming:
		return None

	amount = _cfg_amount(settings)
	unit = settings.get("incoming_alert_unit") or "Working Days"
	weekends = bool(settings.get("deal_inactivity_weekend_holidays"))
	holiday_list = hu.resolve_holiday_list(
		parent,
		bool(settings.get("deal_inactivity_use_company_holiday_list")),
		settings.get("deal_inactivity_holiday_list"),
		{},
	)
	start = getdate(incoming)
	# Prefetch holidays over a range that covers however far the due could land.
	span_days = amount if unit != "Hours" else (amount // 24 + 2)
	holidays = hu.holiday_dates(holiday_list, start, add_days(start, span_days + hu.MAX_LOOKBACK))
	if unit == "Hours":
		return hu.add_hours_deferred(incoming, amount, holidays, weekends=weekends)
	return hu.add_working_days(incoming, amount, holidays, weekends=weekends)


def _cfg_amount(settings):
	"""Unanswered-after amount (in the configured unit); DEFAULT_WORKING_DAYS when blank."""
	try:
		n = int(settings.get("incoming_alert_working_days") or 0)
	except (TypeError, ValueError):
		n = 0
	return n if n > 0 else DEFAULT_WORKING_DAYS


def _same(a, b):
	"""Datetime-equality tolerant of None and str/datetime mix."""
	a = get_datetime(a) if a else None
	b = get_datetime(b) if b else None
	return a == b
