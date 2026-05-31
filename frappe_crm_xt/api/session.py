from __future__ import annotations

import frappe
from crm.api.session import CRM_ALLOWED_ROLES, get_session_role_flags

USER_FIELDS = [
	"name",
	"email",
	"enabled",
	"user_image",
	"first_name",
	"last_name",
	"full_name",
	"user_type",
	"language",
]


@frappe.whitelist()
def get_users(include_all: bool = False):
	"""Return (users, crm_users); SQL-filtered to CRM users unless include_all and System Manager."""
	session_roles = get_session_role_flags()

	if isinstance(include_all, str):
		include_all = include_all.lower() in ("1", "true", "yes")
	if not session_roles["is_system_manager"]:
		include_all = False

	crm_user_names = set(
		frappe.get_all(
			"Has Role",
			filters={"parenttype": "User", "role": ["in", CRM_ALLOWED_ROLES]},
			pluck="parent",
			distinct=True,
		)
	)
	crm_user_names.add("Administrator")

	user_filters = {"enabled": 1}
	if not include_all:
		user_filters["name"] = ["in", list(crm_user_names)]

	users = frappe.qb.get_query(
		"User",
		fields=USER_FIELDS,
		order_by="full_name asc",
		filters=user_filters,
	).run(as_dict=1)

	if not users:
		return [], []

	system_language = frappe.db.get_single_value("System Settings", "language")
	session_user = frappe.session.user

	if include_all:
		role_filters = {"parenttype": "User"}
	else:
		role_filters = {"parenttype": "User", "parent": ["in", list(crm_user_names)]}
	role_rows = frappe.get_all("Has Role", filters=role_filters, fields=["parent", "role"])
	roles_by_user = {}
	for row in role_rows:
		roles_by_user.setdefault(row.parent, []).append(row.role)

	telephony_agents = set(frappe.get_all("CRM Telephony Agent", pluck="user"))

	role_priority = ("System Manager", "Sales Manager", "Sales User", "Guest")
	crm_users = []

	for user in users:
		if session_user == user.name:
			user.session_user = True

		# Administrator gets every role implicitly via frappe.get_roles() but its
		# Has Role child table is not guaranteed to contain System Manager — special-case
		# to avoid locking the admin out.
		if user.name == "Administrator":
			user.roles = ["System Manager", "All"]
			user.role = "System Manager"
		else:
			user.roles = [*roles_by_user.get(user.name, []), "All", "Guest"]
			user.role = ""
			for role in role_priority:
				if role in user.roles:
					user.role = role
					break

		user.is_telephony_agent = user.name in telephony_agents
		user.language = user.language or system_language

		if user.role in CRM_ALLOWED_ROLES:
			crm_users.append(user)

	if not include_all:
		return crm_users, crm_users

	return users, crm_users
