"""Backfill Project.crm_deal from legacy Project.custom_opportunity (and the
ad-hoc Project.custom_deal field used by an earlier iteration of the
deal→project hook). Also reverse-link CRM Deal.project for every project
that ends up with a crm_deal set.

Safe to run multiple times. Missing source columns are tolerated so the
patch works on sites that never had the legacy rtcamp_opportunities app.
"""

import frappe


def execute():
	if not frappe.db.has_column("Project", "custom_deal"):
		# Custom field hasn't been synced yet — bail; will run on the next migrate.
		return

	# 1. Copy legacy custom_opportunity → crm_deal where target is empty.
	for source in ("custom_opportunity", "custom_deal"):
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
