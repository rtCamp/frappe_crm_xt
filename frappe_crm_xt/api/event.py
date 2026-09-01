"""
Event notification scheduler for frappe_crm_xt.

Ported from crm.api.event (PR #1501 — "feat: Event Notifications and more").
Runs as scheduled tasks; sends in-browser realtime notifications (and optionally
emails) to event owners and participants ahead of their events.
"""

from datetime import datetime, timedelta

import frappe
from frappe.utils import add_to_date, now_datetime
from pypika import Order


@frappe.whitelist()
def search_emails(txt: str = ""):
	"""Search contacts by name or email — own copy so we don't depend on crm."""
	doctype = "Contact"
	meta = frappe.get_meta(doctype)
	filters = [["Contact", "email_id", "is", "set"]]
	if meta.get("fields", {"fieldname": "enabled", "fieldtype": "Check"}):
		filters.append([doctype, "enabled", "=", 1])
	if meta.get("fields", {"fieldname": "disabled", "fieldtype": "Check"}):
		filters.append([doctype, "disabled", "!=", 1])
	or_filters = []
	if txt:
		for field in ["full_name", "email_id", "name"]:
			or_filters.append([doctype, field, "like", f"%{txt}%"])
	return frappe.get_list(
		doctype,
		filters=filters,
		fields=["full_name", "email_id", "name"],
		or_filters=or_filters or None,
		limit=20,
		order_by="email_id, full_name, name",
		ignore_permissions=False,
		as_list=True,
		strict=False,
	)


@frappe.whitelist()
def get_doc_events(doctype: str, docname: str | int):
	"""Fetch events linked to a document with their participants and notifications."""

	if doctype not in ["CRM Deal", "CRM Lead"]:
		return []

	frappe.has_permission(doctype, "read", doc=docname, throw=True)

	event = frappe.qb.DocType("Event")
	event_participant = frappe.qb.DocType("Event Participants")

	events = (
		frappe.qb.from_(event)
		.left_join(event_participant)
		.on(event_participant.parent == event.name)
		.select(
			event.name,
			event.subject,
			event.description,
			event.starts_on,
			event.ends_on,
			event.all_day,
			event.event_type,
			event.location,
			event.color,
			event.owner,
			event.creation,
		)
		.where(
			((event.reference_doctype == doctype) & (event.reference_docname == docname))
			| (
				(event_participant.reference_doctype == doctype)
				& (event_participant.reference_docname == docname)
			)
		)
		.distinct()
		.orderby(event.creation, order=Order.desc)
		.limit(50)
	).run(as_dict=True)

	if not events:
		return []

	event_names = [e.name for e in events]

	# TODO: NEED TO CHECK HOW IT WORKS
	participants = frappe.get_all(
		"Event Participants",
		filters={"parent": ["in", event_names], "parenttype": "Event"},
		fields=["parent", "email", "reference_doctype", "reference_docname"],
		ignore_permissions=True,
	)

	notifications = frappe.get_all(
		"Event Notifications",
		filters={"parent": ["in", event_names], "parenttype": "Event"},
		fields=["parent", "type", "before", "interval", "time"],
		ignore_permissions=True,
	)

	parts_by_event = {}
	for p in participants:
		parts_by_event.setdefault(p.parent, []).append(p)

	notifs_by_event = {}
	for n in notifications:
		notifs_by_event.setdefault(n.parent, []).append(n)

	for event in events:
		event.event_participants = parts_by_event.get(event.name, [])
		event.notifications = notifs_by_event.get(event.name, [])

	return events


def trigger_offset_event_notifications():
	"""Trigger event notifications for offset-based intervals (minutes)."""
	_process_event_notifications_by_interval("minutes")
	_process_event_notifications_by_interval("hours")


def trigger_hourly_event_notifications():
	"""Trigger event notifications for hourly intervals."""
	_process_event_notifications_by_interval("hours")


def trigger_daily_event_notifications():
	"""Trigger event notifications for daily intervals."""
	_process_event_notifications_by_interval("days")


def trigger_weekly_event_notifications():
	"""Trigger event notifications for weekly intervals."""
	_process_event_notifications_by_interval("weeks")


def _process_event_notifications_by_interval(interval):
	"""
	Process event notifications for a specific interval.

	Args:
		interval (str): The interval type ('minutes', 'hours', 'days', 'weeks')
	"""

	if frappe.flags.in_import or frappe.flags.in_patch:
		return

	current_time = now_datetime()
	current_user = frappe.session.user
	all_events_data = frappe.db.sql(
		"""
		SELECT
			e.name as event_name,
			e.subject,
			e.starts_on,
			e.ends_on,
			e.owner,
			e.description,
			e.all_day as all_day_event,
			en.type as notification_type,
			en.before as before_value,
			en.time as time_of_day,
			en.interval as notification_interval,
			ep.email as participant_email,
			ep_all.participant_emails_csv,
			CASE WHEN en.parent IS NULL THEN 0 ELSE 1 END as has_custom_notifications
		FROM `tabEvent` e
		LEFT JOIN `tabEvent Notifications` en ON e.name = en.parent AND en.interval = %s
		LEFT JOIN `tabEvent Participants` ep ON e.name = ep.parent AND ep.email = %s
		LEFT JOIN (
			SELECT parent, GROUP_CONCAT(email) AS participant_emails_csv
			FROM `tabEvent Participants`
			GROUP BY parent
		) AS ep_all ON ep_all.parent = e.name
		WHERE (e.starts_on >= %s OR (%s >= e.starts_on AND %s < e.ends_on))
		AND (e.owner = %s OR ep.email = %s)
		AND e.status != 'Cancelled'
		ORDER BY e.starts_on, e.name
	""",
		(interval, current_user, current_time, current_time, current_time, current_user, current_user),
		as_dict=True,
	)

	for event_data in all_events_data:
		participant_emails_csv = event_data.pop("participant_emails_csv", None)
		event_data["event_participants"] = _split_participant_emails(participant_emails_csv)

	notifications = _process_unified_event_data(all_events_data, interval)

	for notification in notifications:
		try:
			event_start = notification.get("starts_on")
			event_end = notification.get("ends_on")
			before_value = notification.get("before_value", 1)

			trigger_datetime = _calculate_trigger_datetime(
				event_start,
				before_value,
				interval,
				notification.get("all_day_event"),
				notification.get("time_of_day"),
			)

			event_is_in_progress = event_start <= current_time < event_end
			trigger_time_passed = current_time > trigger_datetime

			if event_is_in_progress and trigger_time_passed:
				trigger_window_start = trigger_datetime
				trigger_window_end = event_end
			else:
				window_duration = _get_trigger_window_duration(interval)
				trigger_window_start = add_to_date(
					trigger_datetime, **{k: -v for k, v in window_duration.items()}
				)
				trigger_window_end = add_to_date(trigger_datetime, **window_duration)

			if not (trigger_window_start <= current_time <= trigger_window_end):
				continue

			if notification.get("notification_type") == "Email":
				_send_email_notification(notification, event_start, before_value, interval)
			elif notification.get("notification_type") == "Notification":
				_send_system_notification(notification)

		except Exception as e:
			frappe.log_error(
				f"Error processing {interval} notification for event {notification.get('event_name', 'Unknown')}: {e!s}"
			)
			continue


def _process_unified_event_data(all_events_data, interval):
	"""
	Process unified event data that includes both events with and without custom notifications.

	Args:
		all_events_data (list): List of event data from the unified query
		interval (str): The interval type ('minutes', 'hours', 'days', 'weeks')

	Returns:
		list: List of processed notifications ready for sending
	"""
	notifications = []
	events_without_notifications = []

	for event_data in all_events_data:
		if event_data.get("has_custom_notifications") == 1:
			notifications.append(event_data)
		else:
			event_key = event_data.get("event_name")
			if not any(e.get("event_name") == event_key for e in events_without_notifications):
				events_without_notifications.append(event_data)
	if events_without_notifications:
		global_notifications = _apply_global_notifications_to_events(events_without_notifications, interval)
		notifications.extend(global_notifications)

	return notifications


def _apply_global_notifications_to_events(events_without_notifications, interval):
	"""
	Apply global CRM Settings notifications to events that don't have custom notifications.

	Args:
		events_without_notifications (list): List of events without custom notifications
		interval (str): The interval type ('minutes', 'hours', 'days', 'weeks')

	Returns:
		list: List of notification dictionaries using global settings
	"""

	fcrm_settings = frappe.get_single("FCRM Settings")
	global_notifications = []
	if hasattr(fcrm_settings, "event_notifications"):
		for notification in fcrm_settings.event_notifications:
			if notification.interval == interval:
				notification._table_type = "regular"
				global_notifications.append(notification)

	if hasattr(fcrm_settings, "all_day_event_notifications"):
		for notification in fcrm_settings.all_day_event_notifications:
			if notification.interval == interval:
				notification._table_type = "all_day"
				global_notifications.append(notification)

	if not global_notifications:
		return []
	notifications = []
	for event in events_without_notifications:
		for global_notification in global_notifications:
			if (global_notification._table_type == "all_day" and not event.all_day_event) or (
				global_notification._table_type == "regular" and event.all_day_event
			):
				continue

			notification = {
				"event_name": event.event_name,
				"notification_type": global_notification.type,
				"before_value": global_notification.before,
				"time_of_day": global_notification.time,
				"subject": event.subject,
				"starts_on": event.starts_on,
				"ends_on": event.ends_on,
				"owner": event.owner,
				"description": event.description,
				"all_day_event": event.all_day_event,
				"event_participants": event.get("event_participants", []),
			}
			notifications.append(notification)

	return notifications


def _calculate_trigger_datetime(event_start, before_value, interval, all_day_event, time_of_day):
	"""
	Calculate when the notification should be triggered based on event start time and interval.

	Args:
		event_start (datetime): Event start datetime
		before_value (int): How many units before the event
		interval (str): The interval type ('minutes', 'hours', 'days', 'weeks')
		all_day_event (bool): Whether this is an all-day event
		time_of_day (time): Specific time to send notification for all-day events

	Returns:
		datetime: When the notification should be triggered
	"""

	if all_day_event and time_of_day and interval in ["days", "weeks"]:
		if interval == "days":
			trigger_date = event_start.date() - timedelta(days=before_value)
		elif interval == "weeks":
			trigger_date = event_start.date() - timedelta(weeks=before_value)

		trigger_datetime = datetime.combine(trigger_date, time_of_day)
	else:
		interval_kwargs = _get_interval_kwargs(interval, before_value)
		trigger_datetime = add_to_date(event_start, **interval_kwargs)

	return trigger_datetime


def _get_interval_kwargs(interval, before_value):
	"""
	Get the appropriate keyword arguments for add_to_date based on interval type.

	Args:
		interval (str): The interval type ('minutes', 'hours', 'days', 'weeks')
		before_value (int): How many units before the event

	Returns:
		dict: Keyword arguments for add_to_date with negative values
	"""
	interval_mapping = {
		"minutes": {"minutes": -before_value},
		"hours": {"hours": -before_value},
		"days": {"days": -before_value},
		"weeks": {"weeks": -before_value},
	}

	return interval_mapping.get(interval, {"hours": -before_value})


def _get_trigger_window_duration(interval):
	"""
	Get the trigger window duration based on interval type.

	Args:
		interval (str): The interval type ('minutes', 'hours', 'days', 'weeks')

	Returns:
		dict: Window duration to be used symmetrically around the trigger time
	"""
	window_mapping = {
		"minutes": {"minutes": 5},
		"hours": {"hours": 1},
		"days": {"hours": 8},
		"weeks": {"days": 4},
	}

	return window_mapping.get(interval, {"hours": 1})


def _split_participant_emails(participant_emails_csv):
	"""Return a clean list of participant emails from a comma-separated string."""

	if not participant_emails_csv:
		return []

	return [email.strip() for email in participant_emails_csv.split(",") if email and email.strip()]


def _send_email_notification(notification, event_start, before_value, interval):
	"""Send email notification for an event"""

	try:
		recipients = set()
		subject = f"Event Reminder: {notification.subject}"

		if notification.owner and notification.owner != "Administrator":
			recipients.add(notification.owner)

		participant_emails = notification.get("event_participants") or []
		if participant_emails:
			recipients.update(participant_emails)
		else:
			event_doc = frappe.get_doc("Event", notification.event_name)
			for participant in event_doc.get("event_participants", []):
				email = getattr(participant, "email", None)
				if email:
					recipients.add(email)

		recipients = [email for email in recipients if email]

		if not recipients:
			return
		time_remaining_text = _format_time_remaining(before_value, interval)

		message = f"""
		<div style="font-family: Arial, sans-serif; max-width: 600px;">
			<h2 style="color: #333;">Event Reminder</h2>
			<p>This is a reminder for your upcoming event:</p>
			<div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
				<h3 style="margin: 0; color: #007bff;">{notification.subject}</h3>
				{f'<p style="margin: 10px 0; color: #666;">{notification.description}</p>' if notification.description else ""}
				<p style="margin: 5px 0;"><strong>Start Time:</strong> {event_start.strftime("%Y-%m-%d %H:%M:%S")}</p>
				<p style="margin: 5px 0;"><strong>Time Remaining:</strong> {time_remaining_text}</p>
			</div>
			<p style="color: #666; font-size: 12px;">This is an automated reminder from your calendar system.</p>
		</div>
		"""

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype="Event",
			reference_name=notification.event_name,
			now=True,
		)

	except Exception as e:
		frappe.log_error(f"Failed to send email for event {notification.event_name}: {e!s}")


def _format_time_remaining(before_value, interval):
	"""
	Format the time remaining message based on the interval and before value.

	Args:
		before_value (int): The number of units before the event
		interval (str): The interval type ('minutes', 'hours', 'days', 'weeks')

	Returns:
		str: Formatted time remaining message
	"""
	interval_labels = {"minutes": "minute(s)", "hours": "hour(s)", "days": "day(s)", "weeks": "week(s)"}

	interval_label = interval_labels.get(interval, "unit(s)")
	return f"{before_value} {interval_label}"


def _send_system_notification(notification):
	"""Send system notification for an event"""
	frappe.publish_realtime("event_notification", notification)
