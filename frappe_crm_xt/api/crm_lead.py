import frappe
from frappe.handler import upload_file

from frappe_crm_xt.api.auth import verify_request


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep
@verify_request
def create():
	try:
		lead = frappe.get_doc({"doctype": "CRM Lead", "status": "New", "lead_owner": "", **frappe.form_dict})

		frappe.set_user("Administrator")  # nosemgrep
		lead.save(ignore_permissions=True)

		if "attachments" in frappe.form_dict:
			attachments = frappe.form_dict.get("attachments").split(",")

			for attachment_url in attachments:
				attachment_url = attachment_url.strip()
				if not attachment_url:
					continue
				frappe.get_doc(
					{
						"doctype": "File",
						"attached_to_doctype": "CRM Lead",
						"attached_to_name": lead.name,
						"is_private": 1,
						"file_url": attachment_url,
					}
				).insert(ignore_permissions=True)
		return {
			"status": "success",
			"message": "Lead created successfully",
		}
	except Exception as e:
		frappe.log_error(title="Lead Creation Failed")
		return {
			"status": "error",
			"message": str(e),
		}


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep
@verify_request
def upload_lead_file():
	frappe.form_dict.is_private = 1
	data = upload_file()

	return {
		"file_name": data.get("file_name"),
		"file_url": data.get("file_url"),
	}
