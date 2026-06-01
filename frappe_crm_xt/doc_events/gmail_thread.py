import frappe
from frappe.core.utils import get_parent_doc
from frappe.utils import get_datetime


def validate(doc, method):
	update_sales_user_in_thread(doc)


def update_sales_user_in_thread(doc):
	"""
	Updates the `involved_users` field in the given document by appending users
	from a specific user group if the document is related to the "CRM" module.

	"""
	from frappe import get_all, get_cached_value

	if not doc.reference_doctype or not doc.reference_name:
		return
	module = get_cached_value("DocType", doc.reference_doctype, "module")

	if module != "FCRM":
		return

	users = get_all(
		"User Group Member", filters={"parent": USER_GROUP, "parenttype": "User Group"}, pluck="user"
	)

	involved_users = [user.account for user in doc.involved_users if user.account]

	for user in users:
		if user not in involved_users:
			doc.append("involved_users", {"account": user})


USER_GROUP = "Sales team"


def on_update(doc, method):
	"""Update last_response_time of parent document based frappe gmail thread"""
	try:
		parent = get_parent_doc(doc)
		if not parent:
			return

		if parent.doctype not in ["CRM Lead", "CRM Deal"]:
			return

		# check if a new email is added to the thread
		if not doc.emails:
			return

		if (
			doc.has_value_changed("status")
			or doc.has_value_changed("reference_name")
			or doc.has_value_changed("reference_doctype")
		):
			# Re-link / status flip: walk the full thread so first_responded_on
			# lands on the *earliest* historical sent email, not whichever
			# happened to be latest.
			return backfill_parent_from_thread(parent, doc)

		doc_before_save = doc.get_doc_before_save()
		if not doc_before_save:
			return

		if doc_before_save.emails:
			# check if the last email is already in the thread
			if doc.emails[-1].name == doc_before_save.emails[-1].name:
				return

		last_email = doc.emails[-1]
		if last_email.sent_or_received == "Sent":
			update_last_response_time(parent, doc, last_email)
		else:
			update_last_incoming_email_time(parent, last_email)
	except Exception:
		frappe.log_error(
			title="Error in on_update of Gmail Thread",
			message=frappe.get_traceback(),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)


def _email_ts(email):
	return get_datetime(email.date_and_time) if isinstance(email.date_and_time, str) else email.date_and_time


def backfill_parent_from_thread(parent, doc):
	"""Backfill the parent's SLA fields from the full thread history.

	Called when the thread is (re-)linked or its status flips, where we have a
	whole historical conversation to stamp at once. We pick:
	  - earliest Sent  → `first_responded_on`  (drives `first_response_time`)
	  - latest Sent    → `last_responded_on`   (drives rolling-response window)
	  - latest Received → `custom_last_incoming_email_time`
	  - latest email   → `communication_status` ("Replied" if Sent, else "Open")

	One `parent.save()` triggers `CRM Service Level Agreement.apply()`, which
	computes `first_response_time` / `last_response_time` and appends to
	`rolling_responses`.
	"""
	if not doc.emails:
		return
	if not parent.meta.has_field("last_response_time"):
		# Parent doesn't have SLA columns — bail (matches old behaviour).
		return

	sorted_emails = sorted(doc.emails, key=_email_ts)
	earliest_sent = next((e for e in sorted_emails if e.sent_or_received == "Sent"), None)
	latest_sent = next((e for e in reversed(sorted_emails) if e.sent_or_received == "Sent"), None)
	latest_received = next((e for e in reversed(sorted_emails) if e.sent_or_received == "Received"), None)
	latest_email = sorted_emails[-1]

	if earliest_sent and parent.meta.has_field("first_responded_on") and not parent.get("first_responded_on"):
		parent.first_responded_on = earliest_sent.date_and_time
	if latest_sent and parent.meta.has_field("last_responded_on") and not parent.get("last_responded_on"):
		parent.last_responded_on = latest_sent.date_and_time
	if latest_received and parent.meta.has_field("custom_last_incoming_email_time"):
		parent.custom_last_incoming_email_time = latest_received.date_and_time

	parent.communication_status = "Replied" if latest_email.sent_or_received == "Sent" else "Open"
	parent.save(ignore_permissions=True)


def update_last_response_time(parent, gmail_thread, email):
	"""A sales user replied. Pre-seed `first_responded_on` with the email's
	real send time (SLA's `set_first_responded_on` uses `value or
	now_datetime()`, so our value wins) and flip `communication_status` to a
	responded priority. `CRM Service Level Agreement.apply()` — invoked from
	CRM Lead/Deal `before_save` — fills `first_response_time`,
	`last_response_time`, `last_responded_on` and appends to
	`rolling_responses` from there.

	We deliberately don't write `last_responded_on` ourselves: on subsequent
	replies SLA's rolling-response branch overwrites it with `now()` anyway,
	and pre-seeding it would only confuse that calculation.
	"""
	if not parent.meta.has_field("last_response_time"):
		return

	if parent.meta.has_field("first_responded_on") and not parent.get("first_responded_on"):
		parent.first_responded_on = email.date_and_time
	parent.communication_status = "Replied"
	parent.save(ignore_permissions=True)

	# Fallback for deals/leads without an SLA attached (where SLA.apply() is a
	# no-op): emulate Frappe core's `update_first_response_time` so
	# `first_response_time` and `last_response_time` still fill from the email's
	# real send time. Mirrors what Frappe core does for normal Communication
	# docs, just driven from Single Email CT instead.
	_stamp_response_time_fallback(parent, email)


def _stamp_response_time_fallback(parent, email):
	"""Ensure response-time metrics and the rolling_responses table fill on
	every Sent email, independent of whether an SLA is attached or whether
	the SLA's Rolling Responses checkbox is on.

	  - `first_response_time` (stamped on the very first reply)
	  - `last_response_time` / `last_responded_on` (stamped per reply)
	  - one `rolling_responses` child row per reply

	Deduplication is anchor-based: if a rolling row already exists with a
	`responded_on` >= this email's send time (because SLA just appended one
	in the preceding `parent.save()`), `response_time` works out to <= 0 and
	we bail.
	"""
	if not parent.meta.has_field("first_response_time"):
		return

	from frappe.utils import time_diff_in_seconds

	email_dt = email.date_and_time

	# Anchor for this rolling response = previous rolling row's responded_on,
	# falling back to deal creation for the first reply ever.
	anchor = _last_rolling_responded_on(parent) or parent.creation
	response_time = round(time_diff_in_seconds(email_dt, anchor), 2)
	if response_time <= 0:
		# Either SLA already appended a row for this exact email (its row's
		# responded_on == email_dt, so anchor == email_dt → delta 0), or the
		# email predates the most recent rolling row (out-of-order / historical
		# sync). Either way, nothing to add.
		return

	# First-reply metric — only stamped if it's not already filled with a
	# positive value. A stale 0 (e.g. SLA computed 0 because the email
	# predated sla_creation) gets replaced with the real elapsed time.
	if not parent.get("first_response_time"):
		first_delta = round(time_diff_in_seconds(email_dt, parent.creation), 2)
		if first_delta > 0:
			parent.db_set("first_response_time", first_delta, update_modified=False)

	if parent.meta.has_field("last_response_time"):
		parent.db_set("last_response_time", response_time, update_modified=False)
	if parent.meta.has_field("last_responded_on"):
		parent.db_set("last_responded_on", email_dt, update_modified=False)

	if parent.meta.has_field("rolling_responses"):
		_append_rolling_response_row(parent, email_dt, response_time)


def _last_rolling_responded_on(parent):
	return frappe.db.get_value(
		"CRM Rolling Response Time",
		{
			"parent": parent.name,
			"parenttype": parent.doctype,
			"parentfield": "rolling_responses",
		},
		"responded_on",
		order_by="responded_on desc",
	)


def _append_rolling_response_row(parent, responded_on, response_time):
	next_idx = (
		frappe.db.count(
			"CRM Rolling Response Time",
			{
				"parent": parent.name,
				"parenttype": parent.doctype,
				"parentfield": "rolling_responses",
			},
		)
		+ 1
	)
	frappe.get_doc(
		{
			"doctype": "CRM Rolling Response Time",
			"parent": parent.name,
			"parenttype": parent.doctype,
			"parentfield": "rolling_responses",
			"idx": next_idx,
			"response_time": response_time,
			"responded_on": responded_on,
			"status": "Fulfilled",
		}
	).insert(ignore_permissions=True)


def update_last_incoming_email_time(parent, email):
	if parent.meta.has_field("custom_last_incoming_email_time"):
		parent.communication_status = "Open"
		parent.custom_last_incoming_email_time = email.date_and_time
		parent.save(ignore_permissions=True)
