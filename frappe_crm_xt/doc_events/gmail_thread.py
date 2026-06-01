from datetime import timedelta

import frappe
from frappe.core.utils import get_parent_doc
from frappe.utils import get_datetime

# Default response-deadline window used when no SLA is attached to compute
# `response_by` from priorities. Applies to incoming emails only.
DEFAULT_RESPONSE_WINDOW_HOURS = 24


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

	One `parent.save()` triggers `CRM Service Level Agreement.apply()`, then we
	walk the thread chronologically and ensure one rolling row per Sent email.
	"""
	if not doc.emails:
		return
	if not parent.meta.has_field("last_response_time"):
		# Parent doesn't have SLA columns — bail (matches old behaviour).
		return

	from frappe.utils import time_diff_in_seconds

	sorted_emails = sorted(doc.emails, key=_email_ts)
	sent_emails = [e for e in sorted_emails if e.sent_or_received == "Sent"]
	latest_received = next((e for e in reversed(sorted_emails) if e.sent_or_received == "Received"), None)
	latest_email = sorted_emails[-1]
	earliest_sent = sent_emails[0] if sent_emails else None
	latest_sent = sent_emails[-1] if sent_emails else None

	# ── 1. pre-seed parent fields based on full thread state ───────────────
	if earliest_sent and parent.meta.has_field("first_responded_on") and not parent.get("first_responded_on"):
		parent.first_responded_on = earliest_sent.date_and_time
	if latest_sent and parent.meta.has_field("last_responded_on") and not parent.get("last_responded_on"):
		parent.last_responded_on = latest_sent.date_and_time
	if latest_received and parent.meta.has_field("custom_last_incoming_email_time"):
		parent.custom_last_incoming_email_time = latest_received.date_and_time

	parent.communication_status = "Replied" if latest_email.sent_or_received == "Sent" else "Open"

	# ── 2. save — SLA may append one rolling row ───────────────────────────
	parent.save(ignore_permissions=True)

	if not sent_emails or not parent.meta.has_field("rolling_responses"):
		return

	# ── 3. ensure one rolling row per Sent email ───────────────────────────
	# Each Sent email's response_time = email_dt - (its prior Received email),
	# falling back to parent.creation when there's no prior Received (cold
	# outreach). This is the true "how long did the customer wait" semantic.
	existing_responded_on = set(
		frappe.get_all(
			"CRM Rolling Response Time",
			filters={
				"parent": parent.name,
				"parenttype": parent.doctype,
				"parentfield": "rolling_responses",
			},
			pluck="responded_on",
		)
	)

	last_response_seconds = None
	for sent in sent_emails:
		sent_dt = _email_ts(sent)
		prior_received = _find_prior_received(sent, sorted_emails)
		anchor = _email_ts(prior_received) if prior_received else get_datetime(parent.creation)
		response_time = round(time_diff_in_seconds(sent_dt, anchor), 2)
		if response_time <= 0:
			continue
		last_response_seconds = response_time
		if sent_dt in existing_responded_on:
			continue
		_append_rolling_response_row(parent, sent_dt, response_time)

	# ── 4. correct first_response_time / last_response_time / last_responded_on
	# first_response_time = time between earliest sent and its prior received
	# (or parent.creation). Overwrites any 0 SLA wrote when the email predated
	# sla_creation.
	first_anchor_email = _find_prior_received(earliest_sent, sorted_emails)
	first_anchor = _email_ts(first_anchor_email) if first_anchor_email else get_datetime(parent.creation)
	first_delta = round(time_diff_in_seconds(_email_ts(earliest_sent), first_anchor), 2)
	if first_delta > 0 and parent.meta.has_field("first_response_time"):
		parent.db_set("first_response_time", first_delta, update_modified=False)

	if last_response_seconds and parent.meta.has_field("last_response_time"):
		parent.db_set("last_response_time", last_response_seconds, update_modified=False)

	if parent.meta.has_field("last_responded_on"):
		parent.db_set("last_responded_on", latest_sent.date_and_time, update_modified=False)

	# ── 5. response_by deadline ────────────────────────────────────────────
	# If the thread currently ends with a customer email (Open), set the
	# expected response deadline to that email + default window. If we've
	# already responded (latest is Sent), leave response_by alone — the
	# deadline for any prior incoming was met when we replied.
	if parent.meta.has_field("response_by") and latest_email.sent_or_received == "Received":
		deadline = get_datetime(latest_email.date_and_time) + timedelta(hours=DEFAULT_RESPONSE_WINDOW_HOURS)
		parent.db_set("response_by", deadline, update_modified=False)


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

	# Fallback so the SLA tab fills regardless of whether an SLA is attached.
	# Mirrors Frappe core's update_first_response_time but driven by Single
	# Email CT, plus appends rolling rows using the customer's last incoming
	# email as the anchor — giving the true "how long did the customer wait"
	# semantic instead of save-time lag.
	_stamp_response_time_fallback(parent, email, gmail_thread)


def _stamp_response_time_fallback(parent, email, gmail_thread=None):
	"""Ensure response-time metrics and the rolling_responses table fill on
	every Sent email, with timings anchored on the customer's most recent
	incoming message — i.e. "how long did the customer wait for this reply".

	Falls back to `parent.creation` when no prior Received email exists on the
	thread (cold outreach: the first email of all is our Sent).

	Fields written:
	  - `first_response_time` (only when empty / stale 0)
	  - `last_response_time` / `last_responded_on` (per reply)
	  - one `rolling_responses` child row per reply
	"""
	if not parent.meta.has_field("first_response_time"):
		return

	from frappe.utils import time_diff_in_seconds

	email_dt = email.date_and_time

	# True response-time anchor: the customer's last incoming email before
	# this reply. Falls back to deal creation for cold outreach.
	prior_received = _find_prior_received(email, gmail_thread.emails) if gmail_thread else None
	anchor = _email_ts(prior_received) if prior_received else get_datetime(parent.creation)

	response_time = round(time_diff_in_seconds(email_dt, anchor), 2)
	if response_time <= 0:
		# Out-of-order / historical email older than its anchor — nothing
		# meaningful to write.
		return

	# Already represented in rolling_responses (e.g. SLA appended for this
	# exact email during the preceding parent.save()). Update parent metrics
	# but don't double-insert.
	already_logged = parent.meta.has_field("rolling_responses") and _rolling_row_exists(parent, email_dt)

	# first_response_time: stamp if empty or stale 0.
	if not parent.get("first_response_time"):
		parent.db_set("first_response_time", response_time, update_modified=False)

	if parent.meta.has_field("last_response_time"):
		parent.db_set("last_response_time", response_time, update_modified=False)
	if parent.meta.has_field("last_responded_on"):
		parent.db_set("last_responded_on", email_dt, update_modified=False)

	if parent.meta.has_field("rolling_responses") and not already_logged:
		_append_rolling_response_row(parent, email_dt, response_time)


def _find_prior_received(sent_email, all_emails):
	"""Return the most recent Received email whose date strictly precedes the
	given Sent email's date, or None."""
	sent_dt = _email_ts(sent_email)
	prior = None
	for e in sorted(all_emails, key=_email_ts):
		if _email_ts(e) >= sent_dt:
			break
		if e.sent_or_received == "Received":
			prior = e
	return prior


def _rolling_row_exists(parent, responded_on):
	return bool(
		frappe.db.exists(
			"CRM Rolling Response Time",
			{
				"parent": parent.name,
				"parenttype": parent.doctype,
				"parentfield": "rolling_responses",
				"responded_on": responded_on,
			},
		)
	)


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
	"""Customer wrote in. Mark the deal Open, remember when the email landed,
	and stamp a `response_by` deadline so the SLA tab shows when we owe a
	reply by — even on deals without a CRM Service Level Agreement attached.
	"""
	if not parent.meta.has_field("custom_last_incoming_email_time"):
		return

	parent.communication_status = "Open"
	parent.custom_last_incoming_email_time = email.date_and_time

	# Default deadline when no SLA is configured to compute it from priorities.
	# Skip if SLA is already in charge (sla field set) — SLA's set_response_by
	# will compute it from the priority's first_response_time goal.
	if parent.meta.has_field("response_by") and not parent.get("sla"):
		parent.response_by = get_datetime(email.date_and_time) + timedelta(
			hours=DEFAULT_RESPONSE_WINDOW_HOURS
		)

	parent.save(ignore_permissions=True)
