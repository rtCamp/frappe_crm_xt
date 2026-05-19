from functools import wraps

import frappe


def get_api_auth_token():
	return frappe.conf.WordPress_site_conf.get("api_secret")


def verify_request(func):
	"""Function to verify the WordPress request"""

	@wraps(func)
	def wrapper(*args, **kwargs):
		auth_key = frappe.local.request.headers.get("Authorization")
		og_auth_key = get_api_auth_token()
		if not og_auth_key:
			frappe.throw(frappe._("Please set the authorization key"), frappe.DoesNotExistError)
		if auth_key == og_auth_key:
			return func(*args, **kwargs)
		else:
			frappe.throw(frappe._("Invalid Auth Key"), frappe.PermissionError)

	return wrapper
