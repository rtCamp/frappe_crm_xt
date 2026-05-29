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
			last_relevant_received_email = get_last_relevant_received_email(doc)
			if last_relevant_received_email:
				return update_last_incoming_email_time(parent, last_relevant_received_email)
			last_sent_email = get_last_sent_email(doc)
			if last_sent_email:
				return update_last_response_time(parent, doc, last_sent_email)

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


def get_last_relevant_received_email(doc):
	"""
	Get the last received email that follows a sent email from the document.

	If the last email is sent, it will return None.
	If there are only received emails, it will return the first one.

	Args:
		doc: The document containing emails.

	Returns:
		The last received email that follows a sent email, or None if not found.
	"""
	last_emails = sorted(
		doc.emails,
		key=lambda email: (
			get_datetime(email.date_and_time) if isinstance(email.date_and_time, str) else email.date_and_time
		),
		reverse=True,
	)
	last_recieved_email = None
	for email in last_emails:
		if email.sent_or_received == "Received":
			last_recieved_email = email
		else:
			break
	return last_recieved_email


def get_last_sent_email(doc):
	"""
	Get the last sent email from the document.

	Args:
		doc: The document containing emails.

	Returns:
		The last sent email, or None if not found.
	"""
	last_emails = sorted(
		doc.emails,
		key=lambda email: (
			get_datetime(email.date_and_time) if isinstance(email.date_and_time, str) else email.date_and_time
		),
		reverse=True,
	)
	for email in last_emails:
		if email.sent_or_received == "Sent":
			return email
	return None


def update_last_response_time(parent, gmail_thread, email):
	"""A sales user replied. Pre-seed core SLA timestamps with the email's real
	send time (SLA's `set_first_responded_on` uses `value or now_datetime()`,
	so our value wins), then flip `communication_status` to a responded
	priority. `CRM Service Level Agreement.apply()` — invoked from CRM
	Lead/Deal `before_save` — computes `first_response_time`,
	`last_response_time` and appends to `rolling_responses` from there.
	"""
	if not parent.meta.has_field("last_response_time"):
		return

	last_responded_on = email.date_and_time

	if parent.meta.has_field("first_responded_on") and not parent.get("first_responded_on"):
		parent.first_responded_on = last_responded_on
	if parent.meta.has_field("last_responded_on"):
		parent.last_responded_on = last_responded_on
	parent.communication_status = "Replied"
	parent.save(ignore_permissions=True)


def update_last_incoming_email_time(parent, email):
	if parent.meta.has_field("custom_last_incoming_email_time"):
		parent.communication_status = "Open"
		parent.custom_last_incoming_email_time = email.date_and_time
		parent.save(ignore_permissions=True)
