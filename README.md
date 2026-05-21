# Frappe CRM XT

Extensions for [Frappe CRM](https://github.com/frappe/crm) that add features without forking the core app.

- **Global search bar** — Cmd/Ctrl+K modal backed by [frappe_search](https://github.com/rtCamp/frappe_search) *(optional)*.
- **Extensible sidebar** — any installed Frappe app can inject list views, routes, groups, or separators into the CRM sidebar via the `crm_sidebar` hook.
- **Events tab** — calendar events tab injected into every Lead and Deal page; create, edit, and delete Frappe `Event` records linked to the record.
- **Event notifications** — scheduler sends in-browser realtime alerts and optional emails to event owners and participants before their events.
- **Gmail thread activities** — activity entries on Lead/Deal records resolve Gmail threads via [frappe_gmail_thread](https://github.com/rtCamp/frappe_gmail_thread) *(optional)*.
- **Address management (Deal only)** — add, create, link, and unlink `Address` records directly from Deal forms via an inline HTML panel. Not enabled on CRM Lead.
- **Project creation on Won** — when a Deal is marked Won, dialogs guide the user through updating MSA & Insurance details on the linked Customer and creating an ERPNext `Project` pre-filled from the deal.


---

## Features

### Global Search Bar

Press **Cmd+K** (macOS) or **Ctrl+K** (Linux/Windows) anywhere in Frappe CRM to open a full-screen search modal.

Two search backends are supported (tried in order):

| Priority | Backend | Notes |
|----------|---------|-------|
| 1 | [`frappe_search`](https://github.com/rtCamp/frappe_search) | Full-text search with `<mark>` highlighting. Used when installed. |
| 2 | Frappe built-in global search | `frappe.utils.global_search` — always available, no extra install needed. |

---

### Events Tab

Every Lead and Deal page gains an **Events** tab (injected at the right end of the tab bar). The tab overlays the active panel without modifying Frappe CRM's source.

**Capabilities:**

- Timeline feed of all `Event` records linked to the current Lead/Deal via `Event Participants`.
- **Create** a new event — title, date/time or all-day, color, attendees (email tags), visibility, location, description.
- **Edit** an existing event — all fields editable; changes saved via `frappe.client.save`.
- **Delete** an event (with confirmation).
- **Duplicate** an event.
- Color-coded accent bar per event card; color picker shows the active selection with an outline ring.
- Participant avatar stack displayed on each card (up to 3 + overflow count).

Events are stored as standard Frappe `Event` documents and also appear in the Frappe Desk Calendar (`/app/event`).

**Permissions note:** The tab fetches events via the server-side whitelist method `frappe_crm_xt.api.event.get_doc_events`, which bypasses the child-doctype read permission issue that prevents direct `frappe.client.get_list` calls on `Event Participants`.

---

### Event Notifications

Scheduler tasks fire at every interval (all / hourly / daily / weekly) and send notifications to event owners and participants ahead of their events.

Per-event notification rules can be configured in the `Event Notifications` child table on each Event record. If no per-event rules exist, the global defaults from **FCRM Settings** are applied.

| Setting | Description |
|---------|-------------|
| `event_notifications` | Rules for timed events |
| `all_day_event_notifications` | Rules for all-day events |

Each rule specifies: `type` (Notification / Email), `before` (number), `interval` (minutes / hours / days / weeks), and optionally `time` (for all-day events).

---

### Address Management

Every CRM Deal form gains a custom **Addresses** HTML panel (CRM Lead is intentionally excluded). It renders all `Address` records linked to the current Deal via `Dynamic Link`.

**Capabilities:**

- **List** all linked addresses with collapsible full-address detail.
- **Create** a new address (title, type, lines, city, state, pincode, country) and automatically link it to the record.
- **Link** an existing `Address` record by searching and selecting it.
- **Unlink** an address from the record (removes the Dynamic Link entry; does not delete the Address document).
- **Edit** — each card has a direct link to the address's Frappe Desk form.

---

### Project Creation on Won Deal

When a CRM Deal's status is set to **Won**, two sequential dialogs are shown automatically:

1. **MSA & Insurance Details** — pre-filled from the linked ERPNext `Customer`; saves MSA start/end date, document link, insurance requested flag, insurance start/end date, and insurance document link back to the Customer.
2. **Create Project** — collects Project Manager, Territory, Billing Type, Customer, Currency, Estimated Hours, Service Type, Opportunity Amount, and Project Type; creates an ERPNext `Project` with the deal name embedded and opens it in a new tab.

If a project matching the deal already exists, the creation dialog is skipped and an **Open Project** action is added to the Deal's action menu instead.

**Customer custom fields required** (shipped as fixtures in `custom_field.json`):

| Field | Type | Description |
|-------|------|-------------|
| `custom_msa_start_date` | Date | MSA start date |
| `custom_msa_end_date` | Date | MSA end date |
| `custom_msa_document_link` | Data | Link or path to MSA document |
| `custom_insurance_requested` | Check | Whether insurance was requested |
| `custom_insurance_start_date` | Date | Insurance start date |
| `custom_insurance_end_date` | Date | Insurance end date |
| `custom_insurance_document_link` | Data | Link or path to insurance document |

---

### Extensible Sidebar (`crm_sidebar` hook)

Any installed Frappe app can add items to the CRM sidebar by defining a `crm_sidebar` list in its `hooks.py`. Items appear below the built-in "Call Logs" entry.

Four item types are supported:

| `type`        | Description |
|---------------|-------------|
| `"list_view"` | Opens a built-in list view at `/xt/list/<doctype>`. |
| `"route"`     | Navigates to an arbitrary URL (internal or external). |
| `"separator"` | Renders a horizontal divider line. No other keys needed. |
| `"group"`     | Collapsible section. Child items live in the `"items"` key. Groups do not nest. |

#### Full Hook Reference

```python
# hooks.py  (in any installed Frappe app)

crm_sidebar = [
    {
        # ── Required ──────────────────────────────────────────────────────────
        "label": "Purchase Orders",         # Sidebar display label
        "type": "list_view",                # "list_view" | "route" | "separator" | "group"

        # ── Required for type == "list_view" ──────────────────────────────────
        "doctype": "Purchase Order",        # Frappe DocType name

        # ── Required for type == "route" ──────────────────────────────────────
        # "url": "/app/purchase-order",     # Internal or external URL

        # ── Optional ──────────────────────────────────────────────────────────
        "icon": "shopping-cart",            # Lucide icon name (lucide.dev/icons)

        # Filters shown in the filter UI — users can see and remove them
        "default_filters": {
            "status": ["=", "To Receive and Bill"],
        },

        # Filters always applied to every query — never shown in the filter UI
        "hidden_filters": {
            "company": ["=", "My Company"],
        },

        # Columns to display (overrides DocType's in_list_view fields)
        "fields": ["supplier", "transaction_date", "status", "grand_total"],

        # Initial sort direction
        "default_sort": {"field": "transaction_date", "dir": "desc"},

        # Fieldname for the toolbar quick-search input
        # Type-aware: Link → autocomplete, Select/Check → dropdown,
        #             Date/Datetime → date picker, everything else → text
        "search_field": "supplier",

        # URL template opened on row click; {name} is replaced with the record name
        # Defaults to /app/<doctype-slug>/<name>  (standard Frappe form view)
        "row_url": "/desk/query-report/{name}",
    },
    {"type": "separator"},
    {
        "label": "Procurement",
        "type": "group",
        "icon": "package",
        "items": [
            {
                "label": "Suppliers",
                "type": "list_view",
                "doctype": "Supplier",
                "icon": "building",
            },
            {
                "label": "Support Portal",
                "type": "route",
                "url": "https://support.example.com",
                "icon": "external-link",
            },
        ],
    },
]
```

#### Option Reference

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `label` | `str` | ✅ | Sidebar display text |
| `type` | `str` | ✅ | `"list_view"`, `"route"`, `"separator"`, or `"group"` |
| `doctype` | `str` | `list_view` only | Frappe DocType to display |
| `url` | `str` | `route` only | Destination URL |
| `icon` | `str` | — | [Lucide](https://lucide.dev/icons/) icon name (default: `"list"`) |
| `default_filters` | `dict` | — | Pre-applied filters; users can see and clear them |
| `hidden_filters` | `dict` | — | Always-applied filters; never shown in the UI |
| `fields` | `list[str]` | — | Column order override; title and Modified are always included |
| `default_sort` | `dict` | — | `{"field": "<fieldname>", "dir": "asc"\|"desc"}` |
| `search_field` | `str` | — | Fieldname for the toolbar quick-search input |
| `row_url` | `str` | — | Row-click URL template; `{name}` is replaced with the record name |
| `items` | `list` | `group` only | Child items (same schema, one level deep) |

---

### List View (`/xt/list/<doctype>`)

The built-in list view rendered for every `"list_view"` sidebar item includes:

- **Column picker** — toggle any field from the DocType on or off; selection is persisted per-doctype in `localStorage`.
- **Filter panel** — add, edit, and remove ad-hoc filters across any filterable field (Data, Link, Select, Check, Number types).
- **Hidden filters** — `hidden_filters` from the hook are silently merged into every query; they do not appear in the filter panel.
- **Type-aware quick search** — a toolbar input whose component matches the `search_field` type:
  - `Link` → autocomplete (loads options from the linked DocType)
  - `Select` / `Check` → dropdown
  - `Date` / `Datetime` → date picker
  - Everything else → text input (`like %value%`)
- **Sort** — click any column header to toggle ascending/descending sort.
- **Load More** — incremental pagination; loads 20 rows at a time.
- **Custom row URL** — `row_url` template determines where a row click navigates; defaults to the standard Frappe form view.

---

## Requirements

| Package | Required |
|---------|----------|
| `crm` (Frappe CRM) | ✅ |
| `frappe_search` | Optional — enables the Cmd/Ctrl+K global search bar |
| `frappe_gmail_thread` | Optional — enables Gmail thread activity entries on Lead/Deal records |
| `erpnext` | Optional — required for Project creation on Won Deal and Customer MSA/Insurance fields |

## Installation

```bash
bench get-app frappe_crm_xt
bench --site <your-site> install-app frappe_crm_xt
bench build --app frappe_crm_xt
bench --site <your-site> restart
```

## Development

```bash
# Install pre-commit hooks (runs ruff, oxlint, prettier, eslint on commit)
pre-commit install

# Frontend watch build
cd frontend && pnpm run dev

# Run linter
cd frontend && pnpm run lint
```

## Architecture Notes

- The Events tab and sidebar items are injected into the Frappe CRM SPA via a `MutationObserver` in `App.vue` — no FCRM source files are modified.
- The injected Events tab button deliberately does **not** carry `role="tab"` to avoid Reka UI intercepting the click and collapsing all panels.
- `get_doc_events` uses `ignore_permissions=True` only on the `Event Participants` child-table queries (which have no standalone doctype-level permission); the parent `Event` records respect normal read permissions.

## License

[GNU Affero General Public License v3.0](license.txt)
