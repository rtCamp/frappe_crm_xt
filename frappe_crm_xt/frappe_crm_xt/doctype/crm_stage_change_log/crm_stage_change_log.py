# Copyright (c) 2025, rtCamp and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime


class CRMStageChangeLog(Document):
	pass


def add_stage_change_log(doc):
	"""Append a `custom_stage_change_log` row when `sales_stage` changes.

	Works on any parent that mirrors the (sales_stage scalar +
	custom_stage_change_log Table → CRM Stage Change Log) shape — e.g.
	`CRM Deal` (this app) or `Opportunity` (next_crm). Caller invokes it
	from `validate` / `before_save` after detecting that sales_stage
	actually changed; this helper just builds the row.

	Previous-time falls back to the doc's `modified` when no prior log
	entry exists, so the first transition gets a defensible `from_date`.
	"""
	if doc.is_new():
		return

	previous_doc = doc.get_doc_before_save()
	if not previous_doc:
		return

	if previous_doc.get("custom_stage_change_log"):
		last = previous_doc.custom_stage_change_log[-1]
		previous_stage = last.to
		previous_time = last.to_date
	else:
		previous_stage = previous_doc.sales_stage
		previous_time = previous_doc.modified

	now = get_datetime()
	doc.append(
		"custom_stage_change_log",
		{
			"from": previous_stage,
			"to": doc.sales_stage,
			"from_date": previous_time,
			"to_date": now,
			"log_owner": frappe.session.user,
			"duration": _seconds_between(previous_time, now),
		},
	)


def _seconds_between(start, end) -> float:
	if not isinstance(start, datetime):
		start = get_datetime(start)
	if not isinstance(end, datetime):
		end = get_datetime(end)
	return (end - start).total_seconds()
