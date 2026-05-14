"""Patch: Import CRM Form Script fixtures from JSON into the database.

This patch looks for JSON files in the same patch folder (e.g.
`CRM Form Script.json`) which contain an array of `CRM Form Script`
records. Each record is inserted or updated (upsert) into the
database.
"""

import json
import os

import frappe


def _upsert_script(record):
	try:
		name = record.get("name")
		if not name:
			frappe.log_error(message="Missing 'name' in CRM Form Script record", title="add_crm_form_scripts")
			return

		if frappe.db.exists("CRM Form Script", name):
			# Update fields we care about
			fields_to_update = {
				k: v for k, v in record.items() if k in ("script", "enabled", "view", "dt", "is_standard")
			}
			for fieldname, value in fields_to_update.items():
				frappe.db.set_value("CRM Form Script", name, fieldname, value)
		else:
			doc = frappe.get_doc(record)
			doc.insert(ignore_permissions=True)
	except Exception as exc:  # pragma: no cover - defensive
		frappe.log_error(f"Failed to upsert CRM Form Script {record.get('name')}: {exc}")


def execute():
	app_path = os.path.dirname(__file__)
	# Look for any .json files in this patches folder
	json_files = [f for f in os.listdir(app_path) if f.lower().endswith(".json")]

	if not json_files:
		frappe.msgprint("No JSON patch files found; skipping CRM Form Script import")
		return

	for jf in json_files:
		path = os.path.join(app_path, jf)
		try:
			with open(path, encoding="utf-8") as fh:
				data = json.load(fh)

			if not isinstance(data, list):
				frappe.log_error(f"Expected list in {path}", "add_crm_form_scripts")
				continue

			for record in data:
				if not isinstance(record, dict):
					continue
				# Ensure the record is targeted at CRM Form Script doctype
				if record.get("doctype") != "CRM Form Script":
					# skip unrelated fixtures
					continue
				_upsert_script(record)
		except Exception as e:  # pragma: no cover - surface errors
			frappe.log_error(f"Failed to load CRM Form Script JSON {path}: {e}")
