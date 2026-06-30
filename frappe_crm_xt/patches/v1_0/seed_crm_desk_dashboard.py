"""Seed the 'CRM' Desk Dashboard with Report-backed charts/cards.

Idempotent: install_desk_dashboard() skips anything that already exists, so this
runs safely once on existing installs (fresh installs seed via after_install).
"""

from frappe_crm_xt.setup import install_desk_dashboard


def execute():
	install_desk_dashboard()
