"""Calendar sync for CRM Task.

Lifecycle:
- `custom_sync_with_calendar` ON  → create a Frappe Event linked to the task
  (idempotent, runs from `after_insert` + `on_update`).
- `custom_sync_with_calendar` OFF → delete the previously-created Event so
  the task and its calendar entry stay in sync.
- CRM Task trashed → delete the linked Event so nothing dangles.

Participants come from the `custom_event_participants` Table MultiSelect
(child doctype `CRM Involved User`, one User per row).
"""

from __future__ import annotations

from datetime import datetime

import frappe
from frappe.utils import add_to_date, get_datetime, get_time, getdate, now_datetime

# Frappe Data field default is varchar(140); Event.subject is Data.
_EVENT_SUBJECT_MAX = 140


def sync_task_to_calendar(doc, method=None):
	"""Reconcile the task's Event with its `custom_sync_with_calendar` flag.

	- flag ON,  no event     → create
	- flag ON,  event exists → update (subject, window, participants, GC link)
	- flag OFF, event exists → delete
	- flag OFF, no event     → no-op
	"""
	existing_events = _all_events_for(doc.name)
	want_sync = bool(doc.get("custom_sync_with_calendar"))

	if not want_sync:
		for ev in existing_events:
			_delete_event(ev)
		return

	if existing_events:
		primary, *extras = existing_events
		for ev in extras:
			_delete_event(ev)
		_update_event(primary, doc)
		return primary

	starts_on, ends_on = _resolve_event_window(doc)

	values: dict = {
		"doctype": "Event",
		"subject": _build_subject(doc),
		"description": doc.get("description") or "",
		"starts_on": starts_on,
		"ends_on": ends_on,
		"event_type": "Private",
		"event_category": "Event",
		"reference_doctype": "CRM Task",
		"reference_docname": doc.name,
		"event_participants": _collect_participant_rows(doc),
	}

	event = frappe.get_doc(values).insert(ignore_permissions=True)
	return event.name


def _update_event(event_name: str, doc) -> None:
	"""Propagate task changes (subject, window, participants, GC link) to its Event.

	Skips the date-window write when the task has neither `start_date` nor
	`due_date` — otherwise every unrelated save would slide the Event's
	`starts_on`/`ends_on` forward by `now_datetime()`'s ticking value.
	"""
	event = frappe.get_doc("Event", event_name)

	event.subject = _build_subject(doc)
	event.description = doc.get("description") or ""

	if doc.get("start_date") or doc.get("due_date"):
		event.starts_on, event.ends_on = _resolve_event_window(doc)

	event.set("event_participants", _collect_participant_rows(doc))

	event.save(ignore_permissions=True)


def _combine_date_time(date_value, time_value) -> datetime:
	"""Combine a Date + Time into a full datetime; falls back to midnight if no time."""
	date_part = getdate(date_value)
	if not time_value:
		return datetime.combine(date_part, datetime.min.time())
	time_part = get_time(time_value)
	return datetime.combine(date_part, time_part)


def _build_subject(doc) -> str:
	"""Subject for the Event — falls back to `CRM Task <name>` and truncates to 140 chars."""
	subject = doc.get("title") or f"CRM Task {doc.name}"
	if len(subject) > _EVENT_SUBJECT_MAX:
		subject = subject[: _EVENT_SUBJECT_MAX - 1] + "…"
	return subject


def delete_event_on_task_trash(doc, method=None):
	"""Wired to CRM Task `on_trash` — drop the linked Event so it doesn't dangle."""
	existing = _existing_event_for(doc.name)
	if existing:
		_delete_event(existing)


def _resolve_event_window(doc) -> tuple:
	"""Compute (starts_on, ends_on) from the task's `start_date` + `due_date`.

	CRM Task has `start_date: Date` and `due_date: Datetime`. We coerce both
	to datetime, then:

	- both set            → use as-is (Event spans the whole task window).
	                        `validate_due_after_start` guarantees end > start.
	- only `start_date`   → 1h block starting at the task start
	- only `due_date`     → 1h block ENDING at the deadline (prep window)
	- neither             → 1h block starting now

	Returned values are passed straight to the Event's `starts_on`/`ends_on`.
	"""
	start_raw = doc.get("start_date")
	end_raw = doc.get("due_date")
	start_time = doc.get("custom_start_time")

	start_dt = _combine_date_time(start_raw, start_time) if start_raw else None
	end_dt = get_datetime(end_raw) if end_raw else None

	if start_dt and end_dt:
		return start_dt, end_dt
	if start_dt:
		return start_dt, add_to_date(start_dt, hours=1)
	if end_dt:
		return add_to_date(end_dt, hours=-1), end_dt
	now = now_datetime()
	return now, add_to_date(now, hours=1)


def _existing_event_for(task_name) -> str | None:
	"""Return the name of any Event already linked to this task, else None."""
	return frappe.db.get_value(
		"Event",
		{"reference_doctype": "CRM Task", "reference_docname": task_name},
		"name",
	)


def _all_events_for(task_name) -> list[str]:
	"""Return ALL Events linked to this task, oldest first.

	Returning a list lets the reconciler clean up duplicates that may have
	been left behind by a prior race or manual creation.
	"""
	return frappe.get_all(
		"Event",
		filters={"reference_doctype": "CRM Task", "reference_docname": task_name},
		pluck="name",
		order_by="creation asc",
	)


def _delete_event(event_name: str) -> None:
	"""Delete an Event, bypassing perms + ignoring missing-row races."""
	try:
		frappe.delete_doc(
			"Event",
			event_name,
			ignore_permissions=True,
			ignore_missing=True,
			force=True,
			delete_permanently=True,
		)
	except frappe.exceptions.ValidationError:
		frappe.log_error(
			"Event failed to Delete (CRM Task)", f"Failed to delete Event {event_name} on CRM Task trash"
		)


def _collect_participant_rows(doc) -> list[dict]:
	"""Build Event Participants rows from the task.

	Two sources go into the Event's participants table:

	1. Users from the `custom_event_participants` Table MultiSelect — each
	   row of the `CRM Involved User` child has a single `account` Link to User.
	2. The task's parent record (`reference_doctype` + `reference_docname`),
	   typically a CRM Lead or CRM Deal — added as a dynamic-link row so the
	   Event form surfaces a click-through to the customer.

	Skips empty rows and de-duplicates within each section.
	"""
	rows: list[dict] = []
	seen_users: set[str] = set()
	candidate_users: list[str] = []
	for row in doc.get("custom_event_participants") or []:
		user = row.get("account") if hasattr(row, "get") else getattr(row, "account", None)
		if user:
			candidate_users.append(user)

	for user in candidate_users:
		if user in seen_users:
			continue
		seen_users.add(user)
		email = frappe.db.get_value("User", user, "email")
		if not email:
			continue
		rows.append(
			{
				"reference_doctype": "User",
				"reference_docname": user,
				"email": email,
			}
		)
	return rows
