from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, get_datetime, now_datetime

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

	event = frappe.new_doc("Event")
	event.update(
		{
			"subject": _build_subject(doc),
			"description": doc.get("description") or "",
			"starts_on": starts_on,
			"ends_on": ends_on,
			"event_type": "Private",
			"event_category": "Event",
			"reference_doctype": "CRM Task",
			"reference_docname": doc.name,
		}
	)
	_set_participants(event, doc)
	_apply_google_calendar_bridge(event, doc)

	savepoint = "crm_task_event_create"
	frappe.db.savepoint(savepoint)
	try:
		event.insert(ignore_permissions=True)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(title="Calendar sync failed (CRM Task)", message=frappe.get_traceback())
		doc.db_set("custom_sync_with_calendar", 0)
		frappe.msgprint(
			_("Could not sync this task to the calendar — 'Sync with Calendar' has been turned off."),
			indicator="red",
			title=_("Calendar sync failed"),
		)
		return None
	return event.name


def _update_event(event_name: str, doc) -> None:
	"""Propagate task changes (subject, window, participants, GC link) to its Event.

	Skips the date-window write when the task has neither `custom_start_datetime`
	nor `due_date` — otherwise every unrelated save would slide the Event's
	`starts_on`/`ends_on` forward by `now_datetime()`'s ticking value.
	"""
	event = frappe.get_doc("Event", event_name)

	event.subject = _build_subject(doc)
	event.description = doc.get("description") or ""

	if doc.get("custom_start_datetime") or doc.get("due_date"):
		event.starts_on, event.ends_on = _resolve_event_window(doc)

	_set_participants(event, doc)
	_apply_google_calendar_bridge(event, doc)

	savepoint = "crm_task_event_update"
	frappe.db.savepoint(savepoint)
	try:
		event.save(ignore_permissions=True)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(title="Calendar sync failed (CRM Task)", message=frappe.get_traceback())
		doc.db_set("custom_sync_with_calendar", 0)
		frappe.msgprint(
			_("Could not sync this task to the calendar — 'Sync with Calendar' has been turned off."),
			indicator="red",
			title=_("Calendar sync failed"),
		)


def _apply_google_calendar_bridge(event, doc) -> None:
	"""Link the Event to a Google Calendar so Frappe's integration pushes it."""
	google_calendar = doc.get("custom_google_calendar_link")
	if google_calendar:
		event.google_calendar = google_calendar
		event.sync_with_google_calendar = 1
	else:
		event.google_calendar = None
		event.sync_with_google_calendar = 0


def _build_subject(doc) -> str:
	"""Subject for the Event — falls back to `CRM Task <name>` and truncates to 140 chars."""
	subject = doc.get("title") or f"CRM Task {doc.name}"
	if len(subject) > _EVENT_SUBJECT_MAX:
		subject = subject[: _EVENT_SUBJECT_MAX - 1] + "…"
	return subject


def delete_event_on_task_trash(doc, method=None):
	"""Wired to CRM Task `on_trash` — drop every linked Event so none dangle."""
	for ev in _all_events_for(doc.name):
		_delete_event(ev)


def _resolve_event_window(doc) -> tuple:
	"""Compute (starts_on, ends_on) from the task's `custom_start_datetime` + `due_date`."""
	start_raw = doc.get("custom_start_datetime")
	end_raw = doc.get("due_date")

	start_dt = get_datetime(start_raw) if start_raw else None
	end_dt = get_datetime(end_raw) if end_raw else None

	if start_dt and end_dt:
		return start_dt, end_dt
	if start_dt:
		return start_dt, add_to_date(start_dt, hours=1)
	if end_dt:
		return add_to_date(end_dt, hours=-1), end_dt
	now = now_datetime()
	return now, add_to_date(now, hours=1)


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
			title="Event delete failed (CRM Task)",
			message=f"Failed to delete Event {event_name}:\n{frappe.get_traceback()}",
		)


def _set_participants(event, doc) -> None:
	"""Replace the Event's participants with the task's Users."""
	seen: set[str] = set()
	participants: list[dict] = []
	for row in doc.get("custom_event_participants") or []:
		user = row.get("account") if hasattr(row, "get") else getattr(row, "account", None)
		if user and user not in seen:
			seen.add(user)
			participants.append({"doctype": "User", "docname": user})

	event.set("event_participants", [])
	if participants:
		event.add_participants(participants)
