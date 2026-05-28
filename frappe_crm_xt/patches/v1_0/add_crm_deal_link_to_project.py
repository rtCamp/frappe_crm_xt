"""Backfill Project.custom_deal from the legacy Project.custom_opportunity
field (and any earlier ad-hoc `crm_deal` column from a previous iteration
of the deal→project hook).

Safe to run multiple times. Missing source columns are tolerated so the
patch works on sites that never had the legacy rtcamp_opportunities app.
"""

import frappe


def execute():
	if not frappe.db.has_column("Project", "custom_deal"):
		# Custom field hasn't been synced yet — bail; will run on the next migrate.
		return

	# Copy legacy custom_opportunity (and any prior `crm_deal` column) into
	# custom_deal where the target is empty and the source points at a real
	# CRM Deal.
	for source in ("custom_opportunity", "crm_deal"):
		if not frappe.db.has_column("Project", source):
			continue
		frappe.db.sql(
			f"""
			UPDATE `tabProject`
			SET `custom_deal` = `{source}`
			WHERE COALESCE(`custom_deal`, '') = ''
			  AND COALESCE(`{source}`, '') != ''
			  AND EXISTS (
			      SELECT 1 FROM `tabCRM Deal` d WHERE d.name = `tabProject`.`{source}`
			  )
			"""
		)

	frappe.db.commit()
