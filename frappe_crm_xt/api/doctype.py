import frappe

from frappe_crm_xt.api.auth import verify_request

DOCTYPE_LIST = ["CRM Lead"]


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep
@verify_request
def get_doctype_list():
	return {"doctype_list": DOCTYPE_LIST}


@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep
@verify_request
def get_doctype_fields(doctype):
	if not doctype:
		frappe.throw(
			frappe._("Please provide doctype"),
			exc=frappe.ValidationError,
		)

	if doctype not in DOCTYPE_LIST:
		frappe.throw(
			frappe._("Please pass the correct doctype name"),
			exc=frappe.DoesNotExistError,
		)

	doctype_fields = get_filter_doctype_fields(doctype)
	other_fields = [{"label": "Attachments", "fieldname": "attachments", "fieldtype": "Data", "options": "", "reqd": 0}]

	return {"fields": [*doctype_fields, *other_fields]}


def get_filter_doctype_fields(doctype_name):
	doctype_dict = frappe.get_doc({"doctype": doctype_name}).as_dict()

	data = []

	for field_name in doctype_dict:
		try:
			if field_name in ["naming_series"]:
				continue

			doctype_field = []

			if field_name.startswith("custom"):
				doctype_field = frappe.get_all(
					"Custom Field",
					filters={"name": f"{doctype_name}-{field_name}"},
					fields=["label", "fieldname", "fieldtype", "options", "reqd"],
				)
			else:
				doctype_field = frappe.get_all(
					"DocField",
					filters={"parent": doctype_name, "fieldname": field_name, "fieldtype": ["!=", "Table"]},
					fields=["label", "fieldname", "fieldtype", "options", "reqd"],
				)

			if len(doctype_field) == 0:
				continue

			data.append(doctype_field[0])

		except Exception:
			pass
	return data
