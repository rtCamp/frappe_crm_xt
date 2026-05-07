# Frappe CRM XT

Extensions for [Frappe CRM](https://github.com/frappe/crm):

- **Global search bar** — Cmd/Ctrl+K modal backed by [frappe_search](https://github.com/rtCamp/frappe_search) *(optional)*.
- **Extensible sidebar** — any installed Frappe app can inject list views or external links into the CRM sidebar via the `crm_sidebar` hook.
- **Gmail thread activities** — activity entries on Lead/Deal records resolve gmail threads via [frappe_gmail_thread](https://github.com/rtCamp/frappe_gmail_thread) *(optional)*.

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

### Extensible Sidebar (`crm_sidebar` hook)

Any installed Frappe app can add items to the CRM sidebar by defining a `crm_sidebar` list in its `hooks.py`. Items appear below the built-in "Call Logs" entry.

Two item types are supported:

| `type`        | Description |
|---------------|-------------|
| `"list_view"` | Opens a built-in list view at `/xt/list/<doctype>`. |
| `"route"`     | Navigates to an arbitrary URL (internal or external). |

#### Full Hook Reference

```python
# hooks.py  (in any installed Frappe app)

crm_sidebar = [
    {
        # ── Required ──────────────────────────────────────────────────────────
        "label": "Purchase Orders",         # Sidebar display label
        "type": "list_view",                # "list_view" | "route"

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
    {
        "label": "Support Portal",
        "type": "route",
        "url": "https://support.example.com",
        "icon": "external-link",
    },
]
```

#### Option Reference

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `label` | `str` | ✅ | Sidebar display text |
| `type` | `str` | ✅ | `"list_view"` or `"route"` |
| `doctype` | `str` | `list_view` only | Frappe DocType to display |
| `url` | `str` | `route` only | Destination URL |
| `icon` | `str` | — | [Lucide](https://lucide.dev/icons/) icon name (default: `"list"`) |
| `default_filters` | `dict` | — | Pre-applied filters; users can see and clear them |
| `hidden_filters` | `dict` | — | Always-applied filters; never shown in the UI |
| `fields` | `list[str]` | — | Column order override; title and Modified are always included |
| `default_sort` | `dict` | — | `{"field": "<fieldname>", "dir": "asc"\|"desc"}` |
| `search_field` | `str` | — | Fieldname for the toolbar quick-search input |
| `row_url` | `str` | — | Row-click URL template; `{name}` is replaced with the record name |

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
| `frappe_gmail_thread` | Optional — enables gmail thread activity entries on Lead/Deal records |

## Installation

```bash
bench get-app frappe_crm_xt
bench --site <your-site> install-app frappe_crm_xt
bench build --app frappe_crm_xt
```

## Development

```bash
# Install pre-commit hooks (runs ruff, oxlint, prettier, eslint on commit)
pre-commit install

# Frontend watch build
cd frontend && npm run dev
```

## License

[GNU Affero General Public License v3.0](license.txt)
