"""
Event notification scheduler for frappe_crm_xt.

Ported from crm.api.event (PR #1501 — "feat: Event Notifications and more").
Runs as scheduled tasks; sends in-browser realtime notifications (and optionally
emails) to event owners and participants ahead of their events.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import frappe
from frappe.utils import add_to_date, now_datetime

# ── Public API ────────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_doc_events(doctype: str, docname: str) -> list[dict]:
	"""
	Return all Events linked to *doctype/docname* via Event Participants,
	together with their participant rows.

	Frappe's client.get_list on the child doctype 'Event Participants' requires
	an explicit doctype-level read permission that most CRM roles don't have.
	This method runs server-side and uses ignore_permissions for the child-table
	queries only (the parent Event records are still filtered through the normal
	permission model).
	"""
	# 1. Find Event names that have a participant row pointing at this document.
	linked = frappe.get_all(
		"Event Participants",
		filters={"reference_doctype": doctype, "reference_docname": docname},
		fields=["parent"],
		ignore_permissions=True,
	)
	if not linked:
		return []

	names = list({row.parent for row in linked})

	# 2. Fetch the Event records (respects Event read permissions).
	events = frappe.get_all(
		"Event",
		filters=[["name", "in", names]],
		fields=[
			"name",
			"status",
			"subject",
			"description",
			"starts_on",
			"ends_on",
			"all_day",
			"event_type",
			"location",
			"color",
			"owner",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=50,
	)

	# 3. Fetch all participant rows for those events in one query.
	all_parts = frappe.get_all(
		"Event Participants",
		filters=[["parent", "in", names]],
		fields=["name", "parent", "email", "reference_doctype", "reference_docname"],
		ignore_permissions=True,
		limit_page_length=500,
	)

	# 4. Attach participants to each event.
	parts_by_event: dict[str, list] = {}
	for p in all_parts:
		parts_by_event.setdefault(p.parent, []).append(p)

	for ev in events:
		ev["event_participants"] = parts_by_event.get(ev.name, [])

	return events


# ── Public scheduler entry-points ─────────────────────────────────────────────


def trigger_offset_event_notifications():
	"""Called every scheduler tick ("all").  Handles minute-level offsets."""
	_process("minutes")


def trigger_hourly_event_notifications():
	_process("hours")


def trigger_daily_event_notifications():
	_process("days")


def trigger_weekly_event_notifications():
	_process("weeks")


# ── Core processing ────────────────────────────────────────────────────────────


def _process(interval: str):
	if frappe.flags.in_import or frappe.flags.in_patch:
		return

	now = now_datetime()

	rows = frappe.db.sql(
		"""
        SELECT
            e.name            AS event_name,
            e.subject,
            e.starts_on,
            e.ends_on,
            e.owner,
            e.description,
            e.all_day         AS all_day_event,
            en.type           AS notification_type,
            en.before         AS before_value,
            en.time           AS time_of_day,
            en.interval       AS notification_interval,
            ep.email          AS participant_email,
            ep_all.emails_csv AS participant_emails_csv,
            CASE WHEN en.parent IS NULL THEN 0 ELSE 1 END AS has_custom_notifications
        FROM `tabEvent` e
        LEFT JOIN `tabEvent Notifications`  en      ON e.name = en.parent
                                                   AND en.interval = %(interval)s
        LEFT JOIN `tabEvent Participants`   ep      ON e.name = ep.parent
                                                   AND ep.email = %(user)s
        LEFT JOIN (
            SELECT parent, GROUP_CONCAT(email) AS emails_csv
            FROM `tabEvent Participants`
            GROUP BY parent
        ) AS ep_all ON ep_all.parent = e.name
        WHERE (
            e.starts_on >= %(now)s
            OR (%(now)s >= e.starts_on AND %(now)s < e.ends_on)
        )
        AND (e.owner = %(user)s OR ep.email = %(user)s)
        AND e.status != 'Cancelled'
        ORDER BY e.starts_on, e.name
        """,
		{"interval": interval, "user": frappe.session.user, "now": now},
		as_dict=True,
	)

	for row in rows:
		csv = row.pop("participant_emails_csv", None) or ""
		row["event_participants"] = [e.strip() for e in csv.split(",") if e.strip()]

	notifications = _collect_notifications(rows, interval)

	for n in notifications:
		try:
			_maybe_fire(n, now, interval)
		except Exception:
			frappe.log_error(
				f"[crm-xt] notification error for event {n.get('event_name')}",
				"Event Notification",
			)


def _collect_notifications(rows: list[dict], interval: str) -> list[dict]:
	custom, default_candidates = [], {}
	for row in rows:
		if row.get("has_custom_notifications") == 1:
			custom.append(row)
		else:
			key = row["event_name"]
			if key not in default_candidates:
				default_candidates[key] = row

	result = list(custom)

	if default_candidates:
		result.extend(_apply_global_notifications(list(default_candidates.values()), interval))

	return result


def _apply_global_notifications(events: list[dict], interval: str) -> list[dict]:
	try:
		settings = frappe.get_single("FCRM Settings")
	except Exception:
		return []

	global_notifs = []
	for table_attr, all_day_only in (
		("event_notifications", False),
		("all_day_event_notifications", True),
	):
		for n in getattr(settings, table_attr, None) or []:
			if n.interval == interval:
				global_notifs.append((n, all_day_only))

	if not global_notifs:
		return []

	out = []
	for ev in events:
		is_all_day = bool(ev.get("all_day_event"))
		for n, all_day_only in global_notifs:
			if all_day_only and not is_all_day:
				continue
			if not all_day_only and is_all_day:
				continue
			out.append(
				{
					"event_name": ev["event_name"],
					"notification_type": n.type,
					"before_value": n.before,
					"time_of_day": n.time,
					"subject": ev["subject"],
					"starts_on": ev["starts_on"],
					"ends_on": ev["ends_on"],
					"owner": ev["owner"],
					"description": ev.get("description", ""),
					"all_day_event": is_all_day,
					"event_participants": ev.get("event_participants", []),
				}
			)
	return out


def _maybe_fire(n: dict, now: datetime, interval: str):
	starts_on = n["starts_on"]
	ends_on = n["ends_on"]
	before = n.get("before_value", 1) or 1

	trigger_dt = _calc_trigger(
		starts_on,
		before,
		interval,
		n.get("all_day_event"),
		n.get("time_of_day"),
	)

	in_progress = starts_on <= now < ends_on
	trigger_passed = now > trigger_dt
	window = _window(interval)

	if in_progress and trigger_passed:
		win_start, win_end = trigger_dt, ends_on
	else:
		win_start = add_to_date(trigger_dt, **{k: -v for k, v in window.items()})
		win_end = add_to_date(trigger_dt, **window)

	if not (win_start <= now <= win_end):
		return

	ntype = (n.get("notification_type") or "Notification").strip()
	if ntype == "Email":
		_send_email(n, before, interval)
	else:
		frappe.publish_realtime("event_notification", n)


def _calc_trigger(starts_on, before, interval, all_day_event, time_of_day) -> datetime:
	if all_day_event and time_of_day and interval in ("days", "weeks"):
		offset = timedelta(days=before) if interval == "days" else timedelta(weeks=before)
		trigger_date = (starts_on.date() if hasattr(starts_on, "date") else starts_on) - offset
		return datetime.combine(trigger_date, time_of_day)

	mapping = {
		"minutes": {"minutes": -before},
		"hours": {"hours": -before},
		"days": {"days": -before},
		"weeks": {"weeks": -before},
	}
	return add_to_date(starts_on, **(mapping.get(interval) or {"hours": -before}))


def _window(interval: str) -> dict:
	return {
		"minutes": {"minutes": 5},
		"hours": {"hours": 1},
		"days": {"hours": 8},
		"weeks": {"days": 4},
	}.get(interval, {"hours": 1})


def _send_email(n: dict, before: int, interval: str):
	try:
		recipients = set()
		owner = n.get("owner")
		if owner and owner != "Administrator":
			recipients.add(owner)
		for email in n.get("event_participants") or []:
			recipients.add(email)
		if not recipients:
			return

		labels = {
			"minutes": "minute(s)",
			"hours": "hour(s)",
			"days": "day(s)",
			"weeks": "week(s)",
		}
		time_str = f"{before} {labels.get(interval, 'unit(s)')}"
		subject = f"Event Reminder: {n.get('subject', 'Upcoming Event')}"
		message = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;">
  <h2>Event Reminder</h2>
  <h3>{frappe.utils.escape_html(n.get('subject',''))}</h3>
  <p><strong>Starts:</strong> {n.get('starts_on')}</p>
  <p><strong>Time remaining:</strong> {time_str}</p>
  {('<p>' + frappe.utils.escape_html(n.get('description','')) + '</p>') if n.get('description') else ''}
</div>"""

		frappe.sendmail(
			recipients=list(recipients),
			subject=subject,
			message=message,
			reference_doctype="Event",
			reference_name=n.get("event_name"),
			now=True,
		)
	except Exception:
		frappe.log_error(
			f"[crm-xt] email notification failed for event {n.get('event_name')}",
			"Event Email Notification",
		)
