import json
from pathlib import Path

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def install():
	"""Apply all rtcamp-side CRM customisations."""
	install_custom_fields()
	install_property_setters()


def install_custom_fields():
	"""Install / refresh custom fields from custom_fields.json."""
	data_file = Path(__file__).parent / "custom_fields.json"
	create_custom_fields(json.loads(data_file.read_text()), update=True)


def install_property_setters():
	"""Install / refresh property setters from property_setters.json."""
	data_file = Path(__file__).parent / "property_setters.json"
	for ps in json.loads(data_file.read_text()):
		make_property_setter(
			doctype=ps["doctype"],
			fieldname=ps.get("fieldname"),
			property=ps["property"],
			value=ps["value"],
			property_type=ps["property_type"],
			validate_fields_for_doctype=False,
			for_doctype=ps.get("for_doctype", False),
		)
