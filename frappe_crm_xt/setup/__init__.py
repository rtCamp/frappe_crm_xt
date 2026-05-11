"""Setup helpers for frappe_crm_xt — runs on install / migrate.

The Custom Fields that mirror rtcamp's ERPNext-side customisations onto
the Frappe CRM target doctypes (CRM Lead / CRM Deal / CRM Organization)
are stored in `custom_fields.json` as a compact `{doctype: [field, ...]}`
dict and installed via `create_custom_fields`. This is preferred over
fixtures because:

  - the JSON only carries non-default values (~13 KB vs ~117 KB for
    the equivalent fixture file)
  - `create_custom_fields(..., update=True)` is idempotent — re-running
    on `bench --site X migrate` updates existing fields without
    duplicating
  - no Fixtures import quirks (e.g. stale `name` / `modified`)
"""

import json
from pathlib import Path

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def install_custom_fields():
	"""Install / refresh CRM-side custom fields from custom_fields.json."""
	data_file = Path(__file__).parent / "custom_fields.json"
	custom_fields = json.loads(data_file.read_text())
	create_custom_fields(custom_fields, update=True)
