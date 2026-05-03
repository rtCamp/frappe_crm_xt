# Frappe CRM XT

Frappe CRM extensions:

- **Global search bar** — Cmd/Ctrl+K modal in the FCRM frontend, backed by [frappe_search](https://github.com/rtCamp/frappe_search).
- **ERPNext-aware activities** — when `crm_erp_bridge` is installed, gmail-thread activity entries on FCRM Lead/Deal records resolve to the bridged ERPNext `Lead` / `Opportunity`.

## Requirements

- `crm` (Frappe CRM)
- `frappe_search`
- `frappe_gmail_thread` (optional, only required for the activity feature)
- `crm_erp_bridge` (optional, gates the activity rewrite)

## License

mit
