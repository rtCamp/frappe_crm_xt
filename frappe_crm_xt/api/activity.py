"""
Override of crm.api.activities.get_activities.

Calls the upstream FCRM handler first, then merges frappe_gmail_thread entries
when that app is installed.  Degrades cleanly: if frappe_gmail_thread is absent
this is a pure passthrough.

Response shape expected by FCRM's Activities.vue:
	(activities, calls, notes, tasks, attachments)   ← 5-tuple
"""

from __future__ import annotations

import frappe
from crm.api.activities import get_attachments as crm_get_attachments
from frappe.utils import get_datetime

LINKED_DTS = ("CRM Lead", "CRM Deal")


@frappe.whitelist()
def get_activities(name: str):
	from crm.api.activities import get_activities as _upstream

	activities, calls, notes, tasks, attachments = _upstream(name)
	activities = list(activities)

	# Resolve the doctype ONCE up front — both the gmail-thread block and the
	# event-injection block below need it. (The previous version only set
	# `doctype` inside the gmail-thread branch, so it crashed with
	# UnboundLocalError when frappe_gmail_thread wasn't installed.)
	doctype = _resolve_reference_doctype(name)
	is_lead = doctype == "CRM Lead"

	# Append Gmail-thread entries when that integration is present.
	if "frappe_gmail_thread" in frappe.get_installed_apps() and doctype:
		from frappe_gmail_thread.api.activity import get_linked_gmail_threads

		threads = get_linked_gmail_threads(doctype, name)

		for thread in threads:
			doc = thread["template_data"]["doc"]
			activities.append(
				{
					"activity_type": "communication",
					"communication_type": "Email",
					"communication_date": doc["communication_date"],
					"creation": doc["creation"],
					"data": {
						"subject": doc["subject"],
						"content": doc["content"],
						"sender_full_name": doc["sender_full_name"],
						"sender": doc["sender"],
						"recipients": doc["recipients"],
						"cc": doc["cc"],
						"bcc": doc["bcc"],
						"attachments": doc["attachments"],
						"read_by_recipient": doc["read_by_recipient"],
						"delivery_status": doc["delivery_status"],
					},
					"is_lead": is_lead,
				}
			)

	# Append Event entries linked to this Deal/Lead.
	if doctype:
		for ev in _collect_linked_events(doctype, name):
			activities.append(_event_to_activity(ev, is_lead))

	activities.sort(key=lambda x: x.get("creation", "") or "", reverse=True)

	note_list = [n.get("name") for n in notes]

	note_extra_column = frappe.get_all("FCRM Note", {"name": ["in", note_list]}, ["name", "posting_datetime"])
	note_map = {n.get("name"): n.get("posting_datetime") for n in note_extra_column}
	for note in notes:
		note["modified"] = note_map.get(note["name"]) or note.get("creation")

	return activities, calls, notes, tasks, attachments


def _collect_linked_events(doctype: str, name: str) -> list[dict]:
	"""Events linked either via top-level reference or via participants."""
	direct = frappe.get_all(
		"Event",
		filters={"reference_doctype": doctype, "reference_docname": name},
		pluck="name",
	)
	via_participant = frappe.get_all(
		"Event Participants",
		filters={
			"parenttype": "Event",
			"reference_doctype": doctype,
			"reference_docname": name,
		},
		pluck="parent",
	)
	event_names = list({*direct, *via_participant})
	if not event_names:
		return []

	return frappe.get_all(
		"Event",
		filters={"name": ["in", event_names]},
		fields=["name", "subject", "starts_on", "owner", "creation"],
		order_by="creation desc",
	)


def _event_to_activity(event: dict, is_lead: bool) -> dict:
	when = (
		frappe.utils.format_datetime(event["starts_on"], "EEE, MMM d 'at' h:mm a")
		if event.get("starts_on")
		else ""
	)
	subject = event.get("subject") or "Untitled event"
	value = f"{subject} · {when}" if when else subject

	return {
		"activity_type": "added",
		"creation": event.get("creation"),
		"owner": event.get("owner") or "Administrator",
		"data": {
			"field": "event",
			"field_label": "Event",
			"value": value,
		},
		"is_lead": is_lead,
	}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Gmail Add-on: latest-activity endpoint
# ─────────────────────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_latest_activity(name: str) -> dict | None:
	"""Return the most recent Note / Task / Email / Event for a Lead or Deal.

	Shape matches the legacy `next_crm.api.activities.get_latest_activity`:

	    { "type": "Note" | "Task" | "Email" | "Event",
	      "timestamp": <datetime>,
	      "data": { ... } }
	"""
	if not name:
		return None

	doctype = _resolve_reference_doctype(name)
	if not doctype:
		return None

	# Cheap pre-flight: query the most-recent single row from each source
	# (4 indexed lookups), pick the winner, then fully hydrate ONLY that one.
	# Avoids the previous "fetch all notes/tasks + N+1 attachment loads".
	candidates: list[tuple] = []

	note = frappe.db.get_value(
		"FCRM Note",
		{"reference_docname": name},
		["name", "modified", "creation"],
		order_by="modified desc",
		as_dict=True,
	)
	if note:
		candidates.append((get_datetime(note.modified or note.creation), "Note", note.name))

	task = frappe.db.get_value(
		"CRM Task",
		{"reference_docname": name},
		["name", "modified"],
		order_by="modified desc",
		as_dict=True,
	)
	if task:
		candidates.append((get_datetime(task.modified), "Task", task.name))

	email = frappe.db.get_value(
		"Communication",
		{
			"reference_doctype": doctype,
			"reference_name": name,
			"communication_medium": "Email",
		},
		["name", "creation"],
		order_by="creation desc",
		as_dict=True,
	)
	if email:
		candidates.append((get_datetime(email.creation), "Email", email.name))

	event_name = _latest_event_name(doctype, name)
	if event_name:
		ev_meta = frappe.db.get_value("Event", event_name, ["starts_on", "modified"], as_dict=True)
		ev_ts = get_datetime(ev_meta.starts_on or ev_meta.modified)
		candidates.append((ev_ts, "Event", event_name))

	if not candidates:
		return None

	candidates.sort(key=lambda c: c[0], reverse=True)
	ts, kind, docname = candidates[0]
	return {"type": kind, "timestamp": ts, "data": _hydrate(kind, docname)}


def _hydrate(kind: str, docname: str) -> dict:
	if kind == "Note":
		row = (
			frappe.db.get_value(
				"FCRM Note",
				docname,
				["name", "title", "content", "owner", "modified", "creation"],
				as_dict=True,
			)
			or {}
		)
		row["custom_title"] = row.pop("title", "")
		row["note"] = row.pop("content", "")
		row["added_on"] = row.get("modified") or row.get("creation")
		row["attachments"] = crm_get_attachments("FCRM Note", docname)
		return row
	if kind == "Task":
		row = (
			frappe.db.get_value(
				"CRM Task",
				docname,
				[
					"name",
					"title",
					"description",
					"assigned_to",
					"due_date",
					"priority",
					"status",
					"modified",
					"creation",
				],
				as_dict=True,
			)
			or {}
		)
		row["custom_title"] = row.pop("title", "")
		row["allocated_to"] = row.pop("assigned_to", "")
		row["date"] = row.pop("due_date", "")
		return row
	if kind == "Email":
		return (
			frappe.db.get_value(
				"Communication",
				docname,
				[
					"name",
					"subject",
					"sender",
					"content",
					"recipients",
					"cc",
					"bcc",
					"read_by_recipient as read_status",
					"delivery_status",
					"creation",
				],
				as_dict=True,
			)
			or {}
		)
	# Event
	row = (
		frappe.db.get_value(
			"Event",
			docname,
			[
				"name",
				"subject",
				"owner as sender",
				"description as content",
				"starts_on",
				"ends_on",
				"event_category",
				"event_type",
				"modified",
			],
			as_dict=True,
		)
		or {}
	)
	row["recipients"] = _event_participant_emails(docname)
	row["cc"] = ""
	row["bcc"] = ""
	row["read_status"] = 0
	row["delivery_status"] = ""
	return row


def _latest_event_name(doctype: str, name: str) -> str | None:
	"""Most recent Event linked to this Lead/Deal via reference or participant."""
	direct = frappe.db.get_value(
		"Event",
		{"reference_doctype": doctype, "reference_docname": name},
		["name", "modified"],
		order_by="modified desc",
		as_dict=True,
	)
	via = frappe.db.get_value(
		"Event Participants",
		{
			"parenttype": "Event",
			"reference_doctype": doctype,
			"reference_docname": name,
		},
		["parent as name", "modified"],
		order_by="modified desc",
		as_dict=True,
	)
	if direct and via:
		return direct.name if direct.modified >= via.modified else via.name
	return (direct or via).name if (direct or via) else None


# ─── Shared helpers ──────────────────────────────────────────────────────────


def _resolve_reference_doctype(name: str) -> str | None:
	"""Return the doctype (CRM Lead / CRM Deal) that owns this docname,
	or None if `name` matches neither."""
	for dt in LINKED_DTS:
		if frappe.db.exists(dt, name):
			return dt
	return None


def _event_participant_emails(event_name: str) -> str:
	emails = frappe.get_all(
		"Event Participants",
		filters={"parenttype": "Event", "parent": event_name},
		pluck="email",
	)
	return ", ".join(e for e in emails if e)
