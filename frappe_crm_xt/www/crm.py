"""
Override of crm.www.crm  (our app loads after `crm` in apps.txt).

Delegates context to FCRM's controller untouched, then:
  1. Reads FCRM's built crm.html from disk and splices in our <script> tags
     before </body> — so the hash-named Vite bundle stays owned by FCRM.
  2. Injects `crm_xt_features` into the boot window globals so the Vue
     extension bundle can branch on what is installed.
"""

import frappe
from crm.www.crm import get_context as _crm_get_context
from crm.www.crm import get_context_for_dev  # re-exported

no_cache = 1

EXTENSION_SCRIPTS = [
    "/assets/frappe_crm_xt/js/crm_xt_app.js",
]


def get_context():
    context = _crm_get_context()
    _inject_feature_flags(context)
    context.crm_xt_html = _render_fcrm_html_with_extensions(context)
    return context


def _inject_feature_flags(context):
    installed = frappe.get_installed_apps()
    features = {
        "frappe_search": "frappe_search" in installed,
        "bridge": "crm_erp_bridge" in installed,
        "gmail_thread": "frappe_gmail_thread" in installed,
    }
    # Inject as a window global — will be picked up by crm_xt_app.js
    # via window.crm_xt_features before the Vue app mounts.
    context.boot["crm_xt_features"] = features


def _render_fcrm_html_with_extensions(context) -> str:
    """Read FCRM's crm.html, render its Jinja (boot loop etc.), inject our scripts."""
    import os

    html_path = frappe.get_app_path("crm", "www", "crm.html")
    try:
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
    except OSError:
        return '<div id="app" class="h-full"></div>'

    rendered = frappe.render_template(html, context)

    extra = "\n".join(f'<script defer src="{src}"></script>' for src in EXTENSION_SCRIPTS)
    rendered = rendered.replace("</body>", f"{extra}\n</body>", 1) if "</body>" in rendered else rendered + extra

    return rendered


__all__ = ["get_context", "get_context_for_dev"]
