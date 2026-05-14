<template>
  <div class="flex h-full flex-col overflow-hidden bg-surface-white">
    <!-- ── Header ── matches FCRM AppHeader + LayoutHeader ─────────────────── -->
    <div class="flex border-b pr-5">
      <header
        class="flex h-10.5 flex-1 items-center justify-between py-[7px] sm:pl-5 pl-2"
      >
        <div class="flex items-center gap-2">
          <span class="px-0.5 py-1 text-lg font-medium text-ink-gray-5">{{
            doctype
          }}</span>
          <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true"
            >/</span
          >
          <span class="px-0.5 py-1 text-lg font-medium text-ink-gray-7"
            >List</span
          >
        </div>
        <div class="flex items-center gap-2">
          <Button
            variant="solid"
            icon-left="plus"
            label="New"
            @click="openNew"
          />
        </div>
      </header>
    </div>

    <!-- ── View Controls ─────────────────────────────────────────────────────── -->
    <div class="flex items-center justify-between gap-2 px-5 py-4">
      <!-- Left: quick search (type-aware) -->
      <div class="flex flex-1 items-center h-9">
        <!-- Link field → Autocomplete -->
        <Autocomplete
          v-if="searchFieldType === 'Link'"
          :value="quickSearch"
          :options="searchLinkOptions"
          :placeholder="`Search ${searchFieldLabel}…`"
          class="w-52"
          @change="
            (opt) => {
              quickSearch = opt?.value ?? ''
              reload()
            }
          "
          @update:query="fetchSearchLinkOptions"
        />

        <!-- Select / Check → dropdown -->
        <FormControl
          v-else-if="
            searchFieldType === 'Select' || searchFieldType === 'Check'
          "
          type="select"
          :options="searchSelectOptions"
          :modelValue="quickSearch"
          class="w-52"
          @update:modelValue="
            (v) => {
              quickSearch = v?.value ?? v ?? ''
              reload()
            }
          "
        />

        <!-- Date / Datetime → date picker -->
        <FormControl
          v-else-if="
            searchFieldType === 'Date' || searchFieldType === 'Datetime'
          "
          :type="searchFieldType === 'Datetime' ? 'datetime-local' : 'date'"
          :modelValue="quickSearch"
          class="w-44"
          @update:modelValue="
            (v) => {
              quickSearch = v ?? ''
              reload()
            }
          "
        />

        <!-- Default: text search -->
        <FormControl
          v-else
          type="text"
          :modelValue="quickSearch"
          :placeholder="`Search ${searchFieldLabel}…`"
          class="w-52"
          @update:modelValue="
            (v) => {
              quickSearch = v ?? ''
              onQuickSearch()
            }
          "
        />
      </div>

      <!-- Divider -->
      <div class="-ml-2 h-[70%] border-l border-outline-gray-2" />

      <!-- Right: Refresh · Filter · Sort · Columns -->
      <div class="flex items-center gap-2">
        <Button :loading="loading" @click="reload">
          <template #icon>
            <svg
              class="h-4 w-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path
                d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"
              />
            </svg>
          </template>
        </Button>

        <ListFilterLocal
          v-model="activeFilters"
          :doctype="props.doctype"
          :docfields="docfields"
          @update:modelValue="onFilterChange"
        />

        <Dropdown :options="sortDropdownOptions">
          <Button>
            <template #prefix>
              <FeatherIcon
                :name="sortDir === 'asc' ? 'arrow-up' : 'arrow-down'"
                class="h-4 w-4"
              />
            </template>
            <span>Sort</span>
            <template v-if="sortField !== 'modified'" #suffix>
              <span class="text-xs text-ink-gray-5">{{
                columnLabel(sortField)
              }}</span>
            </template>
          </Button>
        </Dropdown>

        <Dropdown :options="columnDropdownOptions">
          <Button>
            <template #prefix>
              <svg
                class="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
                <line x1="15" y1="3" x2="15" y2="21" />
              </svg>
            </template>
            Columns
          </Button>
        </Dropdown>
      </div>
    </div>

    <!-- ── ListView ──────────────────────────────────────────────────────────── -->
    <ListView
      class="flex-1 overflow-hidden"
      :columns="visibleColumns"
      :rows="rows"
      :options="{
        selectable: true,
        showTooltip: false,
        resizeColumn: true,
        getRowRoute: null,
        onRowClick: (row) => openRecord(row.name),
        emptyState: {
          title: loading ? 'Loading…' : 'No records found',
          description: '',
        },
      }"
      row-key="name"
    >
      <ListHeader class="sm:mx-5 mx-3">
        <ListHeaderItem
          v-for="col in visibleColumns"
          :key="col.key"
          :item="col"
          class="cursor-pointer select-none"
          @click="applySort(col.key)"
        >
          <template #suffix>
            <FeatherIcon
              v-if="sortField === col.key"
              :name="sortDir === 'asc' ? 'chevron-up' : 'chevron-down'"
              class="h-3 w-3 text-ink-gray-7"
            />
          </template>
        </ListHeaderItem>
      </ListHeader>
      <ListRows class="mx-3 sm:mx-5" />
      <ListEmptyState v-if="!loading && !rows.length" />
    </ListView>

    <!-- ── Footer ────────────────────────────────────────────────────────────── -->
    <ListFooter
      v-if="pageLengthCount"
      v-model="pageLengthCount"
      class="border-t sm:px-5 px-3 py-2"
      :options="{
        rowCount: rows.length,
        totalCount: totalCount,
      }"
      @loadMore="onLoadMore"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  ListView,
  ListHeader,
  ListHeaderItem,
  ListRows,
  ListEmptyState,
  ListFooter,
  Button,
  FeatherIcon,
  Dropdown,
  FormControl,
  Autocomplete,
} from 'frappe-ui'
import ListFilterLocal from './ListFilterLocal.vue'

const props = defineProps({
  doctype: { type: String, required: true },
  // Shown in the filter UI, pre-applied on load
  defaultFilters: { type: Object, default: () => ({}) },
  // Always applied to every query, never shown in the filter UI
  hiddenFilters: { type: Object, default: () => ({}) },
  // Ordered column fieldnames (overrides in_list_view auto-detect)
  fields: { type: Array, default: () => [] },
  // Initial sort: { field, dir }
  defaultSort: { type: Object, default: () => ({}) },
  // Fieldname to use for the quick-search input in the toolbar.
  // Defaults to the doctype's title field. The input component is
  // automatically chosen based on the field's type.
  searchField: { type: String, default: '' },
  // URL template for row clicks. {name} is replaced with the record name.
  // Defaults to /app/{doctype-slug}/{name} (standard Frappe form view).
  // Example: "/desk/query-report/{name}"  →  ERPNext report runner
  rowUrl: { type: String, default: '' },
})

// ── State ─────────────────────────────────────────────────────────────────────
const rows = ref([])
const docfields = ref([])
const allAvailableColumns = ref([])
const activeColumnKeys = ref(new Set())
const loading = ref(false)
const pageLength = ref(20)
const pageLengthCount = ref(20)
const totalCount = ref(0)
const activeFilters = ref({})
const sortField = ref('modified')
const sortDir = ref('desc')
const quickSearch = ref('')
const titleKey = ref('name')
const searchFieldMeta = ref(null) // field meta for the quick-search input
const searchLinkOptions = ref([]) // options for Link-type search
let offset = 0

// ── CSRF / fetch ──────────────────────────────────────────────────────────────
function csrf() {
  return window.csrf_token || window.boot?.csrf_token || ''
}

async function call(method, args) {
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': csrf(),
      Accept: 'application/json',
    },
    body: JSON.stringify(args),
  })
  const data = await res.json()
  if (data.exc) throw new Error(data.exc)
  return data.message
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr)
  const s = Math.floor(diff / 1000),
    m = Math.floor(s / 60),
    h = Math.floor(m / 60),
    d = Math.floor(h / 24),
    w = Math.floor(d / 7),
    mo = Math.floor(d / 30),
    y = Math.floor(d / 365)
  if (y > 0) return y === 1 ? '1 year ago' : `${y} years ago`
  if (mo > 0) return mo === 1 ? '1 month ago' : `${mo} months ago`
  if (w > 0) return w === 1 ? '1 week ago' : `${w} weeks ago`
  if (d > 0) return d === 1 ? '1 day ago' : `${d} days ago`
  if (h > 0) return h === 1 ? '1 hour ago' : `${h} hours ago`
  if (m > 0) return m === 1 ? '1 min ago' : `${m} mins ago`
  return 'just now'
}

function columnLabel(key) {
  return allAvailableColumns.value.find((c) => c.key === key)?.label || key
}

// ── Search field helpers ──────────────────────────────────────────────────────
const TEXT_TYPES = new Set([
  'Data',
  'Small Text',
  'Text',
  'Long Text',
  'Code',
  'JSON',
  'Text Editor',
])

const searchFieldType = computed(
  () => searchFieldMeta.value?.fieldtype || 'Data',
)
const searchFieldLabel = computed(
  () => searchFieldMeta.value?.label || 'by name',
)

const searchSelectOptions = computed(() => {
  const ft = searchFieldType.value
  const base = [{ label: `All`, value: '' }]
  if (ft === 'Check')
    return [
      ...base,
      { label: 'Yes', value: 'Yes' },
      { label: 'No', value: 'No' },
    ]
  const raw = (searchFieldMeta.value?.options || '').split('\n').filter(Boolean)
  return [...base, ...raw.map((v) => ({ label: v, value: v }))]
})

// Fetch autocomplete options for Link-type search field
async function fetchSearchLinkOptions(query) {
  const linkedDt = searchFieldMeta.value?.options
  if (!linkedDt) return
  try {
    const data = await call('frappe.client.get_list', {
      doctype: linkedDt,
      fields: JSON.stringify(['name']),
      filters: JSON.stringify([[linkedDt, 'name', 'like', `%${query || ''}%`]]),
      limit_page_length: 20,
      limit_start: 0,
    })
    searchLinkOptions.value = (data || []).map((r) => ({
      label: r.name,
      value: r.name,
    }))
  } catch {
    searchLinkOptions.value = []
  }
}

// ── Column setup ──────────────────────────────────────────────────────────────
const ALLOWED = new Set([
  'Data',
  'Link',
  'Select',
  'Date',
  'Datetime',
  'Int',
  'Float',
  'Currency',
  'Small Text',
  'Check',
  'Text',
])
const SYSTEM_SKIP = new Set([
  'name',
  'owner',
  'creation',
  'modified',
  'modified_by',
  'docstatus',
  'idx',
  'amended_from',
])

async function loadMeta() {
  try {
    const meta = await call('frappe.client.get', {
      doctype: 'DocType',
      name: props.doctype,
    })
    const metaFields = meta?.fields || []

    docfields.value = metaFields.filter(
      (f) =>
        !f.hidden &&
        (ALLOWED.has(f.fieldtype) ||
          ['Date', 'Datetime', 'Link', 'Select'].includes(f.fieldtype)),
    )

    const fieldMap = Object.fromEntries(metaFields.map((f) => [f.fieldname, f]))
    titleKey.value = meta?.title_field || 'name'
    const titleMeta = fieldMap[titleKey.value]

    // Resolve search field meta (default to title field)
    const sfName = props.searchField || titleKey.value
    searchFieldMeta.value = metaFields.find((f) => f.fieldname === sfName) || {
      fieldname: sfName,
      fieldtype: 'Data',
      label: titleMeta?.label || 'Name',
      options: '',
    }

    // Pre-load options for Link fields
    if (searchFieldMeta.value.fieldtype === 'Link') {
      fetchSearchLinkOptions('')
    }

    const primary = {
      label: titleMeta?.label || 'Name',
      key: titleKey.value,
      width: 2,
    }
    const modifiedCol = {
      label: 'Modified',
      key: 'modified',
      width: 1,
      getLabel: ({ row }) => timeAgo(row.modified),
    }

    // ALL valid fields for the column picker
    allAvailableColumns.value = [
      primary,
      ...metaFields
        .filter(
          (f) =>
            !f.hidden &&
            ALLOWED.has(f.fieldtype) &&
            f.fieldname !== titleKey.value &&
            !SYSTEM_SKIP.has(f.fieldname),
        )
        .map((f) => ({ label: f.label, key: f.fieldname, width: 1 })),
      modifiedCol,
    ]

    // Default visible columns (hook fields override or in_list_view)
    let defaultKeys
    if (props.fields.length) {
      defaultKeys = [
        titleKey.value,
        ...props.fields.filter(
          (fn) => fn !== titleKey.value && fn !== 'modified' && fieldMap[fn],
        ),
        'modified',
      ]
    } else {
      let listFields = metaFields
        .filter(
          (f) =>
            f.in_list_view &&
            !f.hidden &&
            ALLOWED.has(f.fieldtype) &&
            f.fieldname !== titleKey.value &&
            !SYSTEM_SKIP.has(f.fieldname),
        )
        .slice(0, 4)

      if (listFields.length < 2) {
        const already = new Set([
          titleKey.value,
          ...listFields.map((f) => f.fieldname),
        ])
        const extra = metaFields
          .filter(
            (f) =>
              !f.hidden &&
              ALLOWED.has(f.fieldtype) &&
              !SYSTEM_SKIP.has(f.fieldname) &&
              !already.has(f.fieldname),
          )
          .slice(0, 4 - listFields.length)
        listFields = [...listFields, ...extra]
      }
      defaultKeys = [
        titleKey.value,
        ...listFields.map((f) => f.fieldname),
        'modified',
      ]
    }

    // Restore saved column selection
    try {
      const saved = JSON.parse(
        localStorage.getItem(`xt_cols_${props.doctype}`) || 'null',
      )
      const validKeys = new Set(allAvailableColumns.value.map((c) => c.key))
      if (
        Array.isArray(saved) &&
        saved.length &&
        saved.every((k) => validKeys.has(k))
      ) {
        activeColumnKeys.value = new Set(saved)
      } else {
        activeColumnKeys.value = new Set(defaultKeys)
      }
    } catch {
      activeColumnKeys.value = new Set(defaultKeys)
    }
  } catch {
    titleKey.value = 'name'
    searchFieldMeta.value = {
      fieldname: 'name',
      fieldtype: 'Data',
      label: 'Name',
      options: '',
    }
    allAvailableColumns.value = [
      { label: 'Name', key: 'name', width: 2 },
      {
        label: 'Modified',
        key: 'modified',
        width: 1,
        getLabel: ({ row }) => timeAgo(row.modified),
      },
    ]
    activeColumnKeys.value = new Set(['name', 'modified'])
  }
}

// ── Computed columns / dropdowns ──────────────────────────────────────────────
const visibleColumns = computed(() =>
  allAvailableColumns.value.filter((c) => activeColumnKeys.value.has(c.key)),
)

const sortDropdownOptions = computed(() =>
  allAvailableColumns.value.flatMap((c) => [
    {
      label: `${c.label} ↑`,
      onClick: () => {
        sortField.value = c.key
        sortDir.value = 'asc'
        reload()
      },
    },
    {
      label: `${c.label} ↓`,
      onClick: () => {
        sortField.value = c.key
        sortDir.value = 'desc'
        reload()
      },
    },
  ]),
)

const columnDropdownOptions = computed(() =>
  allAvailableColumns.value.map((c) => ({
    label: c.label,
    icon: activeColumnKeys.value.has(c.key) ? 'check' : '',
    onClick: () => {
      const next = new Set(activeColumnKeys.value)
      if (next.has(c.key)) next.delete(c.key)
      else next.add(c.key)
      if (next.size === 0) return
      activeColumnKeys.value = next
      localStorage.setItem(
        `xt_cols_${props.doctype}`,
        JSON.stringify([...next]),
      )
    },
  })),
)

function applySort(key) {
  if (sortField.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = key
    sortDir.value = 'asc'
  }
  reload()
}

// ── Data loading ──────────────────────────────────────────────────────────────
async function loadRows(append = false) {
  if (!props.doctype) return
  loading.value = true
  try {
    const visibleKeys = visibleColumns.value.map((c) => c.key)
    const fieldSet = new Set([...visibleKeys, 'name', 'modified'])
    const fields = JSON.stringify([...fieldSet])

    // Merge: UI filters  +  hidden hook filters  +  quick-search
    const filterList = []

    // UI filters: { fieldname: [operator, value] }
    for (const [k, v] of Object.entries(activeFilters.value)) {
      if (Array.isArray(v) && v.length >= 2) {
        filterList.push([k, v[0], v[1]])
      } else {
        filterList.push([k, '=', v])
      }
    }

    // Hidden filters: { fieldname: value } or { fieldname: [op, value] }
    for (const [k, v] of Object.entries(props.hiddenFilters)) {
      if (Array.isArray(v) && v.length >= 2) {
        filterList.push([k, v[0], v[1]])
      } else {
        filterList.push([k, '=', v])
      }
    }
    if (quickSearch.value.trim()) {
      const sfMeta = searchFieldMeta.value
      const sfName = sfMeta?.fieldname || titleKey.value
      const sfType = sfMeta?.fieldtype || 'Data'
      const isText = TEXT_TYPES.has(sfType)
      const op = isText ? 'like' : '='
      const val = isText
        ? `%${quickSearch.value.trim()}%`
        : quickSearch.value.trim()
      filterList.push([sfName, op, val])
    }

    const filters = JSON.stringify(filterList)
    const orderBy = `${sortField.value} ${sortDir.value}`

    // NOTE: use limit_start / limit_page_length — the frappe.client.get_list proxy
    // maps its function params by these names; sending `start`/`limit` would be silently
    // ignored (the proxy default of limit_page_length=20, limit_start=None takes over).
    const [data, count] = await Promise.all([
      call('frappe.client.get_list', {
        doctype: props.doctype,
        fields,
        filters,
        limit_page_length: pageLength.value,
        limit_start: offset,
        order_by: orderBy,
      }),
      append
        ? Promise.resolve(totalCount.value)
        : call('frappe.client.get_count', { doctype: props.doctype, filters }),
    ])

    if (!append) totalCount.value = typeof count === 'number' ? count : 0
    rows.value = append ? [...rows.value, ...data] : data
  } catch {
    if (!append) rows.value = []
  } finally {
    loading.value = false
  }
}

function reload() {
  offset = 0
  rows.value = []
  loadRows(false)
}
function onLoadMore() {
  offset += pageLength.value
  loadRows(true)
}
function onFilterChange() {
  try {
    localStorage.setItem(
      `xt_filters_${props.doctype}`,
      JSON.stringify(activeFilters.value),
    )
  } catch {
    /* ignore */
  }
  reload()
}

// Debounce for free-text search
let _searchTimer = null
function onQuickSearch() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(reload, 300)
}

watch(pageLengthCount, (val) => {
  pageLength.value = val
  reload()
})

watch(
  () => props.doctype,
  async () => {
    if (!props.doctype) return
    offset = 0
    rows.value = []
    allAvailableColumns.value = []
    quickSearch.value = ''
    searchFieldMeta.value = null
    searchLinkOptions.value = []
    // Restore saved filters or use defaults
    try {
      const savedFilters = JSON.parse(
        localStorage.getItem(`xt_filters_${props.doctype}`) || 'null',
      )
      activeFilters.value =
        savedFilters && typeof savedFilters === 'object'
          ? savedFilters
          : { ...props.defaultFilters }
    } catch {
      activeFilters.value = { ...props.defaultFilters }
    }
    sortField.value = props.defaultSort?.field || 'modified'
    sortDir.value = props.defaultSort?.dir || 'desc'
    await loadMeta()
    await loadRows(false)
  },
  { immediate: true },
)

// ── Navigation ────────────────────────────────────────────────────────────────
function deslug(dt) {
  return (dt || '').toLowerCase().replace(/\s+/g, '-')
}
function openRecord(name) {
  const url = props.rowUrl
    ? props.rowUrl.replace('{name}', encodeURIComponent(name))
    : `/app/${deslug(props.doctype)}/${encodeURIComponent(name)}`
  window.open(url, '_blank')
}
function openNew() {
  window.open(
    `/app/${deslug(props.doctype)}/new-${deslug(props.doctype)}-1`,
    '_blank',
  )
}
</script>

<style>
/* Make Sort / Columns dropdown bodies scrollable (portal renders to body) */
[data-slot='content'] {
  max-height: 60vh;
  overflow-y: auto;
}
</style>
