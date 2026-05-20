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
from crm.api.activities import get_linked_notes as crm_get_linked_notes
from crm.api.activities import get_linked_tasks as crm_get_linked_tasks
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

	Note: the legacy add-on used `"ToDo"` for the task type — we emit
	`"Task"` since the FCRM doctype is `CRM Task` and the UI now uses
	"Tasks" everywhere. Update the add-on's `CardsActivity.js` switch to
	match.
	"""
	if not name:
		return None

	# `name` is a docname (e.g. "CRM-DEAL-2026-00009"). Look up which doctype
	# it belongs to — Lead or Deal — so we can scope the activity queries
	# correctly. The previous version assigned `doctype = name`, which made
	# every downstream `Communication.reference_doctype` and `Event` filter
	# match nothing.
	doctype = _resolve_reference_doctype(name)
	if not doctype:
		return None

	bucket: list[dict] = []
	bucket += _latest_notes(name)
	bucket += _latest_tasks(name)
	bucket += _latest_emails(doctype, name)
	bucket += _latest_events(doctype, name)

	if not bucket:
		return None

	bucket.sort(key=lambda a: a["timestamp"], reverse=True)
	return bucket[0]


# ─── Per-type collectors (reuse upstream helpers where they exist) ───────────


def _latest_notes(name: str) -> list[dict]:
	"""Wrap `crm.api.activities.get_linked_notes` into the add-on shape."""
	results = []
	for note in crm_get_linked_notes(name)[:5]:
		row = dict(note)
		row["custom_title"] = row.pop("title", "")
		row["note"] = row.pop("content", "")
		row["added_on"] = row.get("modified") or row.get("creation")
		row["attachments"] = crm_get_attachments("FCRM Note", row["name"])
		results.append(
			{
				"type": "Note",
				"timestamp": get_datetime(row["added_on"]),
				"data": row,
			}
		)
	return results


def _latest_tasks(name: str) -> list[dict]:
	"""Wrap `crm.api.activities.get_linked_tasks` into the add-on shape."""
	results = []
	for task in crm_get_linked_tasks(name)[:5]:
		row = dict(task)
		row["custom_title"] = row.pop("title", "")
		row["allocated_to"] = row.pop("assigned_to", "")
		row["date"] = row.pop("due_date", "")
		results.append(
			{
				"type": "Task",  # was "ToDo" in legacy add-on
				"timestamp": get_datetime(row["modified"]),
				"data": row,
			}
		)
	return results


def _latest_emails(doctype: str, name: str) -> list[dict]:
	rows = frappe.get_all(
		"Communication",
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"communication_medium": "Email",
		},
		fields=[
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
		order_by="creation desc",
		limit=5,
	)
	return [
		{
			"type": "Email",
			"timestamp": get_datetime(row["creation"]),
			"data": row,
		}
		for row in rows
	]


def _latest_events(doctype: str, name: str) -> list[dict]:
	# Reuse the feed collector for the same Lead/Deal linkage logic.
	event_rows = _collect_linked_events(doctype, name)
	if not event_rows:
		return []

	full = frappe.get_all(
		"Event",
		filters={"name": ["in", [r["name"] for r in event_rows]]},
		fields=[
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
		order_by="starts_on desc",
		limit=5,
	)
	results = []
	for row in full:
		# The legacy add-on reuses its Email `commData` model for Events, so
		# backfill the email-shaped fields with sensible defaults.
		row["recipients"] = _event_participant_emails(row["name"])
		row["cc"] = ""
		row["bcc"] = ""
		row["read_status"] = 0
		row["delivery_status"] = ""
		results.append(
			{
				"type": "Event",
				"timestamp": get_datetime(row.get("starts_on") or row["modified"]),
				"data": row,
			}
		)
	return results


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
