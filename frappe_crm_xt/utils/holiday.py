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


def holiday_dates(holiday_list, start, end):
	"""Frozenset of full-day holiday dates in [start, end]. No list → empty set (every day is
	a working day)."""
	if not holiday_list:
		return frozenset()
	rows = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "is_half_day": 0, "holiday_date": ["between", [start, end]]},
		pluck="holiday_date",
	)
	return frozenset(getdate(d) for d in rows)


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


def add_hours_deferred(from_dt, hours, holidays):
	"""Advance a datetime by `hours` *calendar* hours, then — if it lands on a non-working day —
	defer to the next working day (same time-of-day), so an alert scheduled off it never fires
	on a holiday. e.g. Fri 10:00 + 24h = Sat 10:00 → deferred → Mon 10:00 (Sat listed as a
	holiday)."""
	due = get_datetime(add_to_date(get_datetime(from_dt), hours=hours))
	d = getdate(due)
	guard = 0
	while is_non_working_day(d, holidays) and guard < MAX_LOOKBACK:
		d = add_days(d, 1)
		guard += 1
	if is_non_working_day(d, holidays):
		# >MAX_LOOKBACK consecutive non-working days — impossible for a real calendar; log so a
		# genuinely broken Holiday List surfaces instead of silently returning a holiday date.
		frappe.log_error(
			title="Holiday deferral cap hit",
			message=f"add_hours_deferred hit the {MAX_LOOKBACK}-day cap from {due}.",
		)
	# Keep `due`'s time-of-day (incl. microseconds); only move the date to the working day.
	return due.replace(year=d.year, month=d.month, day=d.day)
