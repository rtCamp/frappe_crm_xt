"""
Override of crm.api.activities.get_activities.

Chains the upstream handlers then merges frappe_gmail_thread entries when the
app is installed. With crm_erp_bridge, the gmail-thread reference doctype/name
is rewritten from CRM Lead → Lead (erpnext_lead) and CRM Deal → Opportunity
(erpnext_opportunity) so that activity links resolve to the ERPNext records.

Response shape expected by FCRM's Activities.vue:
    (activities, calls, notes, tasks, attachments)   ← 5-tuple
"""

from __future__ import annotations

import frappe

# FCRM doctype → (ERPNext counterpart, bridge field on CRM doc pointing to ERPNext name)
BRIDGE_MAP: dict[str, tuple[str, str]] = {
    "CRM Lead": ("Lead", "erpnext_lead"),
    "CRM Deal": ("Opportunity", "erpnext_opportunity"),
}


@frappe.whitelist()
def get_activities(name: str):
    activities, calls, notes, tasks, attachments = _call_upstream(name)

    if "frappe_gmail_thread" in frappe.get_installed_apps():
        gmail_activities = _fetch_gmail_activities(name)
        if gmail_activities:
            activities = list(activities) + gmail_activities
            activities.sort(key=lambda x: x.get("creation", ""), reverse=True)

    return activities, calls, notes, tasks, attachments


# ─── upstream dispatch ────────────────────────────────────────────────────────


def _call_upstream(name: str):
    if "crm_erp_bridge" in frappe.get_installed_apps():
        from crm_erp_bridge.api.activities_proxy import get_activities as _upstream
    else:
        from crm.api.activities import get_activities as _upstream
    return _upstream(name)


# ─── gmail thread integration ─────────────────────────────────────────────────


def _fetch_gmail_activities(name: str) -> list[dict]:
    """
    Fetch Gmail Threads linked to this record and convert each email to an
    activity entry shaped like FCRM's `communication` type.

    When crm_erp_bridge is installed the name is an ERPNext Lead/Opportunity
    name, so we resolve back to the CRM Lead/CRM Deal name first.
    """
    bridge_installed = "crm_erp_bridge" in frappe.get_installed_apps()

    crm_doctype, crm_name = _resolve_crm_doc(name, bridge_installed)
    if not crm_name:
        return []

    try:
        from frappe_gmail_thread.api.activity import get_attachments_data
    except ImportError:
        return []

    threads = frappe.get_all(
        "Gmail Thread",
        filters={"reference_doctype": crm_doctype, "reference_name": crm_name},
        pluck="name",
    )

    activities = []
    for thread_name in threads:
        try:
            thread = frappe.get_doc("Gmail Thread", thread_name)
        except Exception:
            continue

        for email in thread.emails:
            ref_doctype, ref_name = _bridge_rewrite(
                crm_doctype, crm_name, bridge_installed
            )
            activities.append(
                {
                    "activity_type": "communication",
                    "communication_type": "Gmail Thread",
                    "communication_date": email.creation,
                    "creation": str(email.creation),
                    "owner": email.sender,
                    "data": {
                        "subject": email.subject,
                        "content": email.content,
                        "sender_full_name": email.sender_full_name,
                        "sender": email.sender,
                        "recipients": email.recipients,
                        "cc": email.cc,
                        "bcc": email.bcc,
                        "attachments": _safe_attachments(email, get_attachments_data),
                        "read_by_recipient": email.read_by_recipient,
                        "delivery_status": (
                            "Sent" if email.sent_or_received == "Sent" else "Received"
                        ),
                        # Extra metadata the Activities.vue EmailArea can optionally render
                        "gmail_thread": thread_name,
                        "reference_doctype": ref_doctype,
                        "reference_name": ref_name,
                    },
                    "is_lead": crm_doctype == "CRM Lead",
                    "source": "gmail_thread",
                }
            )

    return activities


def _resolve_crm_doc(name: str, bridge_installed: bool) -> tuple[str, str]:
    """
    Given the `name` that `get_activities` was called with, return the
    (CRM doctype, CRM name) pair where Gmail Threads are actually stored.

    Without bridge: name IS the CRM Lead / CRM Deal name.
    With bridge:    name is an ERPNext Lead / Opportunity name; we look up
                    the `crm_lead` / `crm_deal` back-reference field.
    """
    if not bridge_installed:
        if frappe.db.exists("CRM Lead", name):
            return "CRM Lead", name
        if frappe.db.exists("CRM Deal", name):
            return "CRM Deal", name
        return "", ""

    # Bridge installed — name is an ERPNext doc
    if frappe.db.exists("Lead", name):
        crm_name = frappe.db.get_value("Lead", name, "crm_lead")
        if crm_name:
            return "CRM Lead", crm_name
    if frappe.db.exists("Opportunity", name):
        crm_name = frappe.db.get_value("Opportunity", name, "crm_deal")
        if crm_name:
            return "CRM Deal", crm_name
    return "", ""


def _bridge_rewrite(crm_doctype: str, crm_name: str, bridge_installed: bool) -> tuple[str, str]:
    """
    Return the reference (doctype, name) to embed in the activity entry.
    With bridge, rewrite to the ERPNext counterpart so timeline links open
    the correct record.
    """
    if not bridge_installed:
        return crm_doctype, crm_name

    mapping = BRIDGE_MAP.get(crm_doctype)
    if not mapping:
        return crm_doctype, crm_name

    target_dt, id_field = mapping
    try:
        target_name = frappe.db.get_value(crm_doctype, crm_name, id_field)
    except Exception:
        return crm_doctype, crm_name

    return (target_dt, target_name) if target_name else (crm_doctype, crm_name)


def _safe_attachments(email, get_attachments_data):
    try:
        return get_attachments_data(email)
    except Exception:
        return []
