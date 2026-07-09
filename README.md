# Frappe CRM XT

Extensions for [Frappe CRM](https://github.com/frappe/crm) that add features without forking the core app.

- **[Global search bar](#global-search-bar)** — Cmd/Ctrl+K modal backed by [`rtcamp/frappe_search`](https://github.com/rtCamp/frappe_search) *(optional)*.
- **[Extensible sidebar](#extensible-sidebar-crm_sidebar-hook)** — any installed Frappe app can inject list views, routes, groups, or separators into the CRM sidebar via the `crm_sidebar` hook.
- **[Events tab](#events-tab)** — calendar events tab injected into every Lead and Deal page; create, edit, duplicate, and delete Frappe `Event` records linked to the record.
- **[Event notifications](#event-notifications)** — scheduler sends in-browser realtime alerts and optional emails to event owners and participants before their events.
- **[Deal inactivity Slack digest](#deal-inactivity-slack-digest)** — daily scheduler posts a single Slack digest of CRM Deals with no activity (email, note, task, comment, or field edit) for exactly *N* days; entirely authored from a desk-editable `Notification`.
- **Gmail thread activities** — activity entries on Lead/Deal records resolve Gmail threads via [`rtcamp/frappe_gmail_thread`](https://github.com/rtCamp/frappe_gmail_thread) *(optional)*.
- **[Address management (Deal only)](#address-management)** — add, create, link, and unlink `Address` records directly from Deal forms via an inline HTML panel.
- **[Follow button (eye icon)](#follow-button)** — injected into the Lead/Deal header icon row. Toggles `Document Follow` for the current user; filled eye = following, outline eye = not following.
- **Quotation auto-items** — opening a `Quotation` from a CRM Deal's "Create Quotation" link auto-populates items, customer, currency, and missing values from the source Deal.
- **Public Lead intake API** — guest-allowed `POST` endpoints for creating CRM Leads and uploading files against them; intended for website / external form integrations.
- **Gmail Add-on backend** — whitelisted endpoints powering the Gmail sidebar Add-on (contact lookup by email, linked Leads / Deals, latest activity).
- **Bundled fixtures** — Lead & Deal field layouts, Property Setters, Custom Fields, CRM Form Scripts, and a curated set of CRM View Settings ship as fixtures and install automatically. (Optional)
- **[Project creation on Won](#project-creation-on-won-deal)** — when a Deal is marked Won, dialogs guide the user through updating MSA & Insurance details on the linked Customer and creating an ERPNext `Project` pre-filled from the deal.

---

## Architecture

Frappe CRM XT ships a **Vite-built Vue 3 IIFE bundle** (`crm_xt_app.js`) that is loaded into the Frappe CRM SPA alongside the standard Frappe assets. The bundle:

- mounts a minimal `App.vue` root component on a `#crm-xt-app` div injected into the page
- uses `MutationObserver` to watch the CRM SPA's DOM and inject the sidebar, custom routes, and the Events tab without touching any FCRM source files
- ships its own copy of Vue 3 and [frappe-ui](https://github.com/frappe/frappe-ui), so all components use the same design tokens and Tailwind classes as native CRM views

### Frontend components

| Component | Purpose |
|-----------|---------|
| `App.vue` | Root — sidebar injection, route registration, Events tab injection, global search trigger |
| `ExtListView.vue` | Full-featured list view (frappe-ui `ListView`, filters, sort, column picker, pagination) |
| `InjectedEventsTab.vue` | Events tab timeline and empty state |
| `InjectedEventModal.vue` | Create / edit / delete / duplicate Event dialog |
| `SearchDialog.vue` | Cmd/Ctrl+K global search modal |
| `EventNotifications.vue` | Per-event notification rules editor |
| `ListFilterLocal.vue` | Ad-hoc filter panel used inside `ExtListView` |
| `Attendee.vue` | Email-tag input for event attendees |
| `UserAvatar.vue` | Resolved user avatar with fallback initials |

### Backend modules

| Module | Purpose |
|--------|---------|
| `api/activity.py` | Overrides `crm.api.activities.get_activities`; appends Gmail thread entries |
| `api/event.py` | `get_doc_events`, create/save/delete helpers, notification scheduler tasks |
| `api/follow.py` | Document Follow toggle endpoint |
| `api/contact.py` | Gmail Add-on contact lookup endpoints |
| `api/quotation.py` | Quotation auto-populate helper |
| `api/search.py` | Global search backend (frappe_search or built-in fallback) |
| `api/sidebar.py` | Reads `crm_sidebar` hooks from all installed apps and returns merged item list |
| `api/deal_inactivity.py` | Daily "deal gone quiet" Slack digest scheduler |

---

## Features

### Global Search Bar

Press **Cmd+K** (macOS) or **Ctrl+K** (Linux/Windows) anywhere in Frappe CRM to open a full-screen search modal.

Two backends are tried in order:

| Priority | Backend | Notes |
|----------|---------|-------|
| 1 | [`rtcamp/frappe_search`](https://github.com/rtCamp/frappe_search) | Full-text search with `<mark>` highlighting. Used when installed. |
| 2 | Frappe built-in global search | `frappe.utils.global_search` — always available, no extra install. |

---

### Events Tab

Every Lead and Deal page gains an **Events** tab injected at the right end of the tab bar.

**Capabilities:**

- Timeline feed of all `Event` records linked to the current Lead/Deal via `Event Participants`
- **Create** a new event — title, date/time or all-day, color, attendees (email tags), visibility, location, description
- **Edit** an existing event — all fields editable; changes saved via `frappe.client.save`
- **Delete** an event (with confirmation)
- **Duplicate** an event
- Color-coded accent bar per event card; color picker shows the active selection
- Participant avatar stack on each card (up to 3 + overflow count)

Events are stored as standard Frappe `Event` documents and also appear in the Frappe Desk Calendar (`/app/event`).

**Permissions note:** Events are fetched via `frappe_crm_xt.api.event.get_doc_events`, which bypasses the child-doctype read permission issue that prevents direct `frappe.client.get_list` calls on `Event Participants`.

---

### Event Notifications

Scheduler tasks fire at every interval and send notifications to event owners and participants ahead of their events.

Per-event rules can be configured in the `Event Notifications` child table on each Event record. If no per-event rules exist, global defaults from **FCRM Settings** are applied.

| Setting | Description |
|---------|-------------|
| `event_notifications` | Rules for timed events |
| `all_day_event_notifications` | Rules for all-day events |

Each rule specifies: `type` (Notification / Email), `before` (number), `interval` (minutes / hours / days / weeks), and optionally `time` (for all-day events).

---

### Deal Inactivity Slack Digest

A daily scheduler (`cron` 09:00, site time zone) posts a **single Slack digest** listing every CRM Deal that has had **no activity for exactly `INACTIVE_DAYS` (7) days** — one nudge per streak, on the day the gap crosses the threshold. Won/Lost deals are excluded.

"Activity" is the most recent of **all** of the following — a note/task/comment does *not* bump `deal.modified`, so each is checked directly:

| Source | Field / record |
|--------|----------------|
| Status / any deal field edit | `deal.modified` |
| Incoming email | `deal.custom_last_incoming_email_time` |
| Outgoing email / reply | `deal.last_responded_on` (Gmail-synced) and/or `deal.custom_last_responded_on` (migrated) |
| Notes | `FCRM Note` |
| Tasks | `CRM Task` |
| Comments | `Comment` |

Everything about the alert is authored from a desk-editable **Notification** (`CRM Slack — CRM Deal Inactivity (7 days)`) — no code change is needed to restyle or re-scope it:

| Notification field | Role in the digest |
|--------------------|--------------------|
| `enabled` | Feature on/off switch (the scheduler no-ops when disabled) |
| `subject` | Digest **header** — rendered with `{{ count }}` and `{{ days }}` |
| `message` | Per-deal **block** — rendered with `{{ doc }}` (the deal) |
| Condition / Filters | Extra per-deal scoping, honored before sending |
| Slack Webhook URL | Target Slack channel |

**Dividers via Markdown comments:** any `<!-- ... -->` comment in the message is stripped from the Slack output (like a Markdown comment); the inner text of the first comment becomes the **divider between deal blocks** (`\n` is interpreted as a newline). No comment → blocks are separated by a blank line.

**Scales to large datasets:** instead of scanning every stale deal, the job fetches only deals *touched on the target day* across all activity sources, so cost stays flat even with 100k+ deals.

The Notification is seeded (disabled) by the `create_crm_slack_notifications` patch, alongside two event-driven CRM → Slack notifications:

| Notification | Trigger |
|--------------|---------|
| CRM Slack — CRM Deal Inactivity (7 days) | Daily scheduler (this feature) |
| CRM Slack — CRM Deal Note Added | New `FCRM Note` on a Deal |
| CRM Slack — CRM Deal Updates | Deal saved (title / status / value / owner / stage change) |

All three ship **disabled**. Point each at a `Slack Webhook URL` (core Frappe integration) and toggle **Enabled** from the desk to activate — the webhook holds a secret, so it is never shipped in the app.

---

### Address Management

Every CRM Deal form gains a custom **Addresses** HTML panel (not shown on CRM Lead). It renders all `Address` records linked to the Deal via `Dynamic Link`.

**Capabilities:**

- **List** all linked addresses with collapsible full-address detail
- **Create** a new address and automatically link it to the record
- **Link** an existing `Address` record by searching and selecting it
- **Unlink** an address (removes the Dynamic Link entry; does not delete the Address document)
- **Edit** — each card has a direct link to the address's Frappe Desk form

---

### Follow Button

An eye icon is injected into the Lead/Deal header icon row:

- **Filled eye** — you are currently following this record
- **Outline eye** — you are not following this record

Clicking the button calls the `frappe_crm_xt.api.follow.toggle_follow` endpoint and auto-enables `track_changes` on the doctype if needed.

---

### Project Creation on Won Deal

When a CRM Deal's status is set to **Won**, two sequential dialogs are shown automatically:

1. **MSA & Insurance Details** — pre-filled from the linked ERPNext `Customer`; saves MSA start/end date, document link, insurance requested flag, insurance start/end date, and insurance document link back to the Customer.
2. **Create Project** — collects Project Manager, Territory, Billing Type, Customer, Currency, Estimated Hours, Service Type, Opportunity Amount, and Project Type; creates an ERPNext `Project` and opens it in a new tab.

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

| `type` | Description |
|--------|-------------|
| `"list_view"` | Opens the built-in list view at `/xt/list/<doctype>` |
| `"route"` | Navigates to an arbitrary URL (internal or external) |
| `"separator"` | Renders a horizontal divider line |
| `"group"` | Collapsible section; child items live in the `"items"` key (one level deep) |

#### Full Hook Reference

```python
# hooks.py  (in any installed Frappe app)

crm_sidebar = [
    {
        # ── Required ──────────────────────────────────────────────────
        "label": "Purchase Orders",         # Sidebar display label
        "type": "list_view",                # "list_view" | "route" | "separator" | "group"

        # ── Required for type == "list_view" ──────────────────────────
        "doctype": "Purchase Order",

        # ── Required for type == "route" ──────────────────────────────
        # "url": "/app/purchase-order",

        # ── Optional ──────────────────────────────────────────────────
        "icon": "shopping-cart",            # Lucide icon name (lucide.dev/icons)

        # Filters shown in the filter UI — users can see and remove them
        "default_filters": {
            "status": ["=", "To Receive and Bill"],
        },

        # Filters always applied but never shown in the filter UI
        "hidden_filters": {
            "company": ["=", "My Company"],
        },

        # Columns to display (overrides DocType's in_list_view fields)
        "fields": ["supplier", "transaction_date", "status", "grand_total"],

        # Initial sort
        "default_sort": {"field": "transaction_date", "dir": "desc"},

        # Fieldname for the toolbar quick-search input
        # Type-aware: Link → autocomplete, Select/Check → dropdown,
        #             Date/Datetime → date picker, everything else → text
        "search_field": "supplier",

        # URL template opened on row click; {name} is replaced with the record name
        # Defaults to /app/<doctype-slug>/<name>
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

- **Column picker** — toggle any field from the DocType on or off; selection persisted per-doctype in `localStorage`
- **Filter panel** — add, edit, and remove ad-hoc filters across any filterable field
- **Hidden filters** — `hidden_filters` from the hook are silently merged into every query; they do not appear in the filter panel
- **Type-aware quick search** — toolbar input whose component matches the `search_field` type:
  - `Link` → autocomplete (loads options from the linked DocType)
  - `Select` / `Check` → dropdown
  - `Date` / `Datetime` → date picker
  - Everything else → text input (`like %value%`)
- **Sort** — click any column header to toggle ascending/descending sort
- **Load More** — incremental pagination (20 rows per page)
- **Custom row URL** — `row_url` template determines row-click destination; defaults to the standard Frappe form view
- **Permission-safe** — if the user lacks read permission for the doctype, the list shows an empty state instead of crashing

---

## Requirements

| Package | Required |
|---------|----------|
| `crm` (Frappe CRM) | ✅ |
| `rtcamp/frappe_search` | Optional — enables Cmd/Ctrl+K global search |
| `rtcamp/frappe_gmail_thread` | Optional — enables Gmail thread activity entries on Lead/Deal |
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

# Frontend watch build (Vite IIFE bundle)
cd frontend && yarn dev

# Production build
cd frontend && yarn build

# Run linter
cd frontend && yarn lint
```

The Vite build outputs `frappe_crm_xt/public/js/crm_xt_app.js` (IIFE, ~1.5 MB) and `frappe_crm_xt/public/js/frappe-crm-xt-frontend.css`. Run `bench build --app frappe_crm_xt` afterwards to have Frappe copy the assets to the site's `public/` directory.

## Architecture Notes

- The Events tab and sidebar items are injected into the Frappe CRM SPA via a `MutationObserver` in `App.vue` — no FCRM source files are modified.
- The injected Events tab button deliberately does **not** carry `role="tab"` to avoid Reka UI intercepting the click and collapsing all panels.
- `get_doc_events` uses `ignore_permissions=True` only on the `Event Participants` child-table queries (which have no standalone doctype-level permission); parent `Event` records respect normal read permissions.
- The `crm_sidebar` hook is collected from all installed apps via `frappe.get_hooks('crm_sidebar')` in `api/sidebar.py` and returned as a single merged list to the frontend.
- `frappe_crm_xt` must be listed **after** `crm` in `apps.txt` so the `override_whitelisted_methods` entry for `crm.api.activities.get_activities` takes precedence correctly.

## License

[GNU Affero General Public License v3.0](license.txt)
