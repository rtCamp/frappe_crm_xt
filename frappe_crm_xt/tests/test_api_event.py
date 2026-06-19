# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from datetime import datetime, time

from frappe.tests import UnitTestCase

from frappe_crm_xt.api.event import (
	_calculate_trigger_datetime,
	_format_time_remaining,
	_get_interval_kwargs,
	_get_trigger_window_duration,
	_split_participant_emails,
)


class TestApiEventHelpers(UnitTestCase):
	# ─── _split_participant_emails ─────────────────────────────────────────────

	def test_split_participant_emails_none_or_empty(self):
		"""Empty / None CSV yields an empty list"""
		self.assertEqual(_split_participant_emails(None), [])
		self.assertEqual(_split_participant_emails(""), [])

	def test_split_participant_emails_basic(self):
		"""Two-email CSV splits into trimmed strings"""
		self.assertEqual(
			_split_participant_emails("a@x.com, b@x.com"),
			["a@x.com", "b@x.com"],
		)

	def test_split_participant_emails_strips_empty_and_whitespace(self):
		"""Extra commas, whitespace and blanks are removed"""
		self.assertEqual(
			_split_participant_emails("a@x.com , , b@x.com,   "),
			["a@x.com", "b@x.com"],
		)

	# ─── _get_interval_kwargs ──────────────────────────────────────────────────

	def test_get_interval_kwargs_known(self):
		"""All four documented intervals map to their negative offset"""
		self.assertEqual(_get_interval_kwargs("minutes", 3), {"minutes": -3})
		self.assertEqual(_get_interval_kwargs("hours", 2), {"hours": -2})
		self.assertEqual(_get_interval_kwargs("days", 1), {"days": -1})
		self.assertEqual(_get_interval_kwargs("weeks", 4), {"weeks": -4})

	def test_get_interval_kwargs_unknown_falls_back_to_hours(self):
		"""An unknown interval falls back to {'hours': -before_value}"""
		self.assertEqual(_get_interval_kwargs("centuries", 2), {"hours": -2})

	# ─── _get_trigger_window_duration ──────────────────────────────────────────

	def test_window_duration_per_interval(self):
		"""Window duration matches the per-interval mapping"""
		self.assertEqual(_get_trigger_window_duration("minutes"), {"minutes": 5})
		self.assertEqual(_get_trigger_window_duration("hours"), {"hours": 1})
		self.assertEqual(_get_trigger_window_duration("days"), {"hours": 8})
		self.assertEqual(_get_trigger_window_duration("weeks"), {"days": 4})

	def test_window_duration_unknown(self):
		"""Unknown intervals fall back to a 1-hour window"""
		self.assertEqual(_get_trigger_window_duration("centuries"), {"hours": 1})

	# ─── _calculate_trigger_datetime ───────────────────────────────────────────

	def test_calculate_trigger_all_day_days(self):
		"""All-day event + days interval + time_of_day combines date - days with the time"""
		event_start = datetime(2025, 6, 10, 0, 0, 0)
		trigger = _calculate_trigger_datetime(
			event_start, before_value=2, interval="days", all_day_event=True, time_of_day=time(9, 0)
		)

		self.assertEqual(trigger, datetime(2025, 6, 8, 9, 0))

	def test_calculate_trigger_all_day_weeks(self):
		"""All-day event + weeks interval + time_of_day combines date - weeks with the time"""
		event_start = datetime(2025, 6, 10, 0, 0, 0)
		trigger = _calculate_trigger_datetime(
			event_start, before_value=1, interval="weeks", all_day_event=True, time_of_day=time(8, 30)
		)

		self.assertEqual(trigger, datetime(2025, 6, 3, 8, 30))

	def test_calculate_trigger_non_all_day(self):
		"""Non-all-day uses add_to_date with the negative interval kwargs"""
		event_start = datetime(2025, 6, 10, 10, 0, 0)
		trigger = _calculate_trigger_datetime(
			event_start, before_value=30, interval="minutes", all_day_event=False, time_of_day=None
		)

		self.assertEqual(trigger, datetime(2025, 6, 10, 9, 30))

	# ─── _format_time_remaining ────────────────────────────────────────────────

	def test_format_time_remaining_all_labels(self):
		"""Each interval gets its documented plural label"""
		self.assertEqual(_format_time_remaining(5, "minutes"), "5 minute(s)")
		self.assertEqual(_format_time_remaining(2, "hours"), "2 hour(s)")
		self.assertEqual(_format_time_remaining(3, "days"), "3 day(s)")
		self.assertEqual(_format_time_remaining(1, "weeks"), "1 week(s)")

	def test_format_time_remaining_unknown(self):
		"""Unknown intervals fall back to 'unit(s)'"""
		self.assertEqual(_format_time_remaining(7, "centuries"), "7 unit(s)")
