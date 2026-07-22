"""Shared holiday / working-day helpers.

Used by both the deal-inactivity digest (tasks/deal_inactivity.py) and the incoming-email
SLA-due field (doc_events/incoming_sla.py). A "working day" is any day NOT in the resolved
Holiday List; an empty/absent list means every day is a working day. Holiday rows come
from ERPNext's `Holiday` child table (`is_half_day = 0` only). ERPNext already ships
`is_holiday(list, date)` and `get_holiday_list_for_employee(employee)`, but has no
"working-days-between" / "Nth working day" utilities — those live here.
"""

import frappe
from frappe.utils import add_days, add_to_date, get_datetime, getdate

# Safety cap for walk-backs/forwards (guards a pathologically holiday-dense calendar).
MAX_LOOKBACK = 90


ERPNEXT_CRM_SETTINGS = "ERPNext CRM Settings"


def company_holiday_list(company):
	"""A Company's default Holiday List (or None)."""
	return frappe.db.get_value("Company", company, "default_holiday_list") if company else None


def erpnext_settings_company():
	"""The company configured on ERPNext CRM Settings ("Company in ERPNext site"), or None.
	This is the single company used for holiday resolution — never computed per deal."""
	if not frappe.db.exists("DocType", ERPNEXT_CRM_SETTINGS):
		return None
	return frappe.db.get_single_value(ERPNEXT_CRM_SETTINGS, "erpnext_company")


def resolve_holiday_list(use_company, fixed):
	"""Holiday List to count working days against: the ERPNext CRM Settings company's default
	Holiday List (when `use_company` is on) → `fixed` → None. The company comes from ERPNext
	CRM Settings ("Company in ERPNext site") and is read once per run — it is NOT derived from
	each deal, so every deal is evaluated against the same calendar."""
	if use_company:
		hl = company_holiday_list(erpnext_settings_company())
		if hl:
			return hl
	return fixed or None


def holiday_dates(holiday_list, start, end, cache=None):
	"""Frozenset of full-day holiday dates in [start, end]. Pass a dict as `cache` to
	memoize per list across a run. No list → empty set (every day is a working day)."""
	if not holiday_list:
		return frozenset()
	if cache is not None and holiday_list in cache:
		return cache[holiday_list]
	rows = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "is_half_day": 0, "holiday_date": ["between", [start, end]]},
		pluck="holiday_date",
	)
	result = frozenset(getdate(d) for d in rows)
	if cache is not None:
		cache[holiday_list] = result
	return result


def is_non_working_day(date, holidays):
	"""Non-working iff `date` is in the holiday set. With no Holiday List resolved the set is
	empty, so every day counts as a working day."""
	return getdate(date) in holidays


def working_days_between(start_dt, end_dt, holidays, stop_at=None):
	"""Count working days in (start_dt, end_dt] (exclusive of start, inclusive of end).
	If `stop_at` is given, stops early once the count exceeds it (cheap threshold tests)."""
	end = getdate(end_dt)
	day = add_days(getdate(start_dt), 1)
	count = 0
	while getdate(day) <= end:
		if not is_non_working_day(day, holidays):
			count += 1
			if stop_at is not None and count > stop_at:
				return count
		day = add_days(day, 1)
	return count


def nth_working_day_back(today, n, holidays):
	"""Date of the n-th working day counting back from `today` (today itself is the 1st if
	it is a working day). Non-working days push it earlier; capped by MAX_LOOKBACK."""
	count = 0
	d = getdate(today)
	floor = getdate(add_days(today, -(n + MAX_LOOKBACK)))
	while d >= floor:
		if not is_non_working_day(d, holidays):
			count += 1
			if count == n:
				return d
		d = add_days(d, -1)
	return floor


def add_working_days(from_dt, n, holidays):
	"""Advance a datetime forward by `n` working days (skipping non-working days), preserving
	the time-of-day. e.g. 'incoming email time + 1 working day'. The result always lands on a
	working day, so an alert scheduled off it never fires on a holiday."""
	dt = get_datetime(from_dt)
	d = getdate(dt)
	count = 0
	guard = 0
	while count < n and guard < (n + MAX_LOOKBACK):
		d = add_days(d, 1)
		if not is_non_working_day(d, holidays):
			count += 1
		guard += 1
	return get_datetime(f"{getdate(d)} {dt.strftime('%H:%M:%S')}")


def add_hours_deferred(from_dt, hours, holidays):
	"""Advance a datetime by `hours` *calendar* hours, then — if it lands on a non-working
	day — defer to the next working day (same time-of-day), so an alert scheduled off it never
	fires on a holiday. The "N hours after" counterpart to add_working_days (working-day count).
	e.g. Fri 10:00 + 24h = Sat 10:00 → deferred → Mon 10:00 (Sat listed as a holiday)."""
	due = get_datetime(add_to_date(get_datetime(from_dt), hours=hours))
	d = getdate(due)
	guard = 0
	while is_non_working_day(d, holidays) and guard < MAX_LOOKBACK:
		d = add_days(d, 1)
		guard += 1
	return get_datetime(f"{getdate(d)} {due.strftime('%H:%M:%S')}")
