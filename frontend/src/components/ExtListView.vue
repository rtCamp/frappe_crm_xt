<template>
  <div class="flex h-full flex-col overflow-hidden bg-surface-white">

    <!-- ── Header ── matches FCRM AppHeader + LayoutHeader ─────────────────── -->
    <div class="flex border-b pr-5">
      <header class="flex h-10.5 flex-1 items-center justify-between py-[7px] sm:pl-5 pl-2">
        <!-- Left: breadcrumb -->
        <div class="flex items-center gap-2">
          <span class="px-0.5 py-1 text-lg font-medium text-ink-gray-5">
            {{ doctype }}
          </span>
          <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
          <span class="px-0.5 py-1 text-lg font-medium text-ink-gray-7">List</span>
        </div>
        <!-- Right: actions -->
        <div class="flex items-center gap-2">
          <Button variant="solid" icon-left="plus" label="New" @click="openNew" />
        </div>
      </header>
    </div>

    <!-- ── View Controls ── matches FCRM ViewControls (no quick-filter chips) ─ -->
    <div class="flex items-center justify-between gap-2 px-5 py-4">
      <!-- Left: empty flex spacer (quick filter chips area, unused here) -->
      <div class="flex flex-1 items-center overflow-x-auto -ml-1 h-9" />

      <!-- Divider -->
      <div class="-ml-2 h-[70%] border-l border-outline-gray-2" />

      <!-- Right: Refresh · Filter · Sort · Columns -->
      <div class="flex items-center gap-2">
        <!-- Refresh -->
        <Button :loading="loading" @click="reload">
          <template #icon>
            <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
          </template>
        </Button>

        <!-- Filter -->
        <ListFilterLocal
          v-model="activeFilters"
          :docfields="docfields"
          @update:modelValue="onFilterChange"
        />

        <!-- Sort -->
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
              <span class="text-xs text-ink-gray-5">{{ columnLabel(sortField) }}</span>
            </template>
          </Button>
        </Dropdown>

        <!-- Columns -->
        <Dropdown :options="columnDropdownOptions">
          <Button>
            <template #prefix>
              <!-- columns icon -->
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
                <line x1="9" y1="3" x2="9" y2="21"/>
                <line x1="15" y1="3" x2="15" y2="21"/>
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
      <ListRows />
      <ListEmptyState v-if="!loading && !rows.length" />
    </ListView>

    <!-- ── Footer ────────────────────────────────────────────────────────────── -->
    <div class="shrink-0 border-t border-outline-gray-2 px-5 py-2">
      <ListFooter
        v-model="pageLength"
        :options="{ rowCount: rows.length, totalCount: totalCount }"
        @loadMore="onLoadMore"
      />
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import {
  ListView, ListHeader, ListHeaderItem, ListRows, ListEmptyState, ListFooter,
  Button, FeatherIcon, Dropdown,
} from 'frappe-ui'
import ListFilterLocal from './ListFilterLocal.vue'

const props = defineProps({
  doctype:        { type: String,  required: true },
  // Optional hook overrides from crm_sidebar
  defaultFilters: { type: Object,  default: () => ({}) },  // { fieldname: [op, val] }
  fields:         { type: Array,   default: () => [] },     // ordered fieldname list for columns
  defaultSort:    { type: Object,  default: () => ({}) },   // { field, dir } e.g. {field:'status',dir:'asc'}
})

// ── State ─────────────────────────────────────────────────────────────────────
const rows        = ref([])
const docfields   = ref([])    // all filterable fields (for ListFilter)
const allColumns  = ref([])    // all available columns (label + key)
const hiddenKeys  = ref(new Set())  // columns the user has toggled off
const loading     = ref(false)
const pageLength  = ref(20)
const totalCount  = ref(0)
const activeFilters = ref({})  // { fieldname: [operator, value] }
const sortField   = ref('modified')
const sortDir     = ref('desc')
let   offset      = 0

// ── CSRF ──────────────────────────────────────────────────────────────────────
function csrf() { return window.csrf_token || window.boot?.csrf_token || '' }

async function call(method, args) {
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST', credentials: 'same-origin',
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
  const s = Math.floor(diff / 1000), m = Math.floor(s / 60),
        h = Math.floor(m / 60), d = Math.floor(h / 24),
        w = Math.floor(d / 7), mo = Math.floor(d / 30), y = Math.floor(d / 365)
  if (y > 0)  return y  === 1 ? '1 year ago'   : `${y} years ago`
  if (mo > 0) return mo === 1 ? '1 month ago'  : `${mo} months ago`
  if (w > 0)  return w  === 1 ? '1 week ago'   : `${w} weeks ago`
  if (d > 0)  return d  === 1 ? '1 day ago'    : `${d} days ago`
  if (h > 0)  return h  === 1 ? '1 hour ago'   : `${h} hours ago`
  if (m > 0)  return m  === 1 ? '1 min ago'    : `${m} mins ago`
  return 'just now'
}

function columnLabel(key) {
  return allColumns.value.find(c => c.key === key)?.label || key
}

// ── Column setup ──────────────────────────────────────────────────────────────
const ALLOWED      = new Set(['Data','Link','Select','Date','Datetime','Int','Float','Currency','Small Text','Check','Text'])
const SYSTEM_SKIP  = new Set(['name','owner','creation','modified','modified_by','docstatus','idx','amended_from'])

async function loadMeta() {
  try {
    const meta   = await call('frappe.client.get', { doctype: 'DocType', name: props.doctype })
    const metaFields = meta?.fields || []

    // Expose all filterable fields to ListFilter
    docfields.value = metaFields.filter(f =>
      !f.hidden && (ALLOWED.has(f.fieldtype) || ['Date','Datetime','Link','Select'].includes(f.fieldtype))
    )

    const fieldMap  = Object.fromEntries(metaFields.map(f => [f.fieldname, f]))
    const titleKey  = meta?.title_field || 'name'
    const titleMeta = fieldMap[titleKey]

    // Primary column (always first)
    const primary = { label: titleMeta?.label || 'Name', key: titleKey, width: 2 }

    // Modified column (always last)
    const modifiedCol = {
      label: 'Modified', key: 'modified', width: 1,
      getLabel: ({ row }) => timeAgo(row.modified),
    }

    let listFields
    if (props.fields.length) {
      // ── Hook override: use the explicit fieldname list ─────────────────────
      listFields = props.fields
        .filter(fn => fn !== titleKey && fn !== 'modified' && fieldMap[fn])
        .map(fn => fieldMap[fn])
    } else {
      // ── Auto-detect: in_list_view fields (up to 4, skip primary & system) ─
      listFields = metaFields.filter(f =>
        f.in_list_view && !f.hidden && ALLOWED.has(f.fieldtype) &&
        f.fieldname !== titleKey && !SYSTEM_SKIP.has(f.fieldname)
      ).slice(0, 4)

      // Fallback if sparse
      if (listFields.length < 2) {
        const already = new Set([titleKey, ...listFields.map(f => f.fieldname)])
        const extra = metaFields.filter(f =>
          !f.hidden && ALLOWED.has(f.fieldtype) &&
          !SYSTEM_SKIP.has(f.fieldname) && !already.has(f.fieldname)
        ).slice(0, 4 - listFields.length)
        listFields = [...listFields, ...extra]
      }
    }

    allColumns.value = [
      primary,
      ...listFields.map(f => ({ label: f.label, key: f.fieldname, width: 1 })),
      modifiedCol,
    ]

    // Restore saved hidden columns for this doctype
    try {
      const saved = JSON.parse(localStorage.getItem(`xt_hidden_${props.doctype}`) || '[]')
      hiddenKeys.value = new Set(saved)
    } catch { hiddenKeys.value = new Set() }

  } catch {
    allColumns.value = [
      { label: 'Name', key: 'name', width: 2 },
      { label: 'Modified', key: 'modified', width: 1, getLabel: ({ row }) => timeAgo(row.modified) },
    ]
  }
}

// ── Computed columns / dropdowns ──────────────────────────────────────────────
const visibleColumns = computed(() =>
  allColumns.value.filter(c => !hiddenKeys.value.has(c.key))
)

const sortDropdownOptions = computed(() =>
  allColumns.value.flatMap(c => [
    {
      label: `${c.label} ↑`,
      onClick: () => { sortField.value = c.key; sortDir.value = 'asc'; reload() },
    },
    {
      label: `${c.label} ↓`,
      onClick: () => { sortField.value = c.key; sortDir.value = 'desc'; reload() },
    },
  ])
)

const columnDropdownOptions = computed(() =>
  allColumns.value.map(c => ({
    label: c.label,
    icon: hiddenKeys.value.has(c.key) ? '' : 'check',
    onClick: () => {
      const next = new Set(hiddenKeys.value)
      next.has(c.key) ? next.delete(c.key) : next.add(c.key)
      // Always keep at least one column visible
      if (allColumns.value.every(col => next.has(col.key))) return
      hiddenKeys.value = next
      localStorage.setItem(`xt_hidden_${props.doctype}`, JSON.stringify([...next]))
    },
  }))
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
    // Always fetch name + modified even if not visible
    const visibleKeys  = visibleColumns.value.map(c => c.key)
    const fieldSet     = new Set([...visibleKeys, 'name', 'modified'])
    const fields       = JSON.stringify([...fieldSet])

    // Convert filters: { fieldname: [op, val] } → [[fieldname, op, val], ...]
    const filterList = Object.entries(activeFilters.value).map(([k, [op, v]]) => [k, op, v])
    const filters    = JSON.stringify(filterList)

    const orderBy = `${sortField.value} ${sortDir.value}`

    const [data, count] = await Promise.all([
      call('frappe.client.get_list', {
        doctype: props.doctype,
        fields,
        filters,
        limit: pageLength.value,
        start: offset,
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

function reload() { offset = 0; rows.value = []; loadRows(false) }
function onLoadMore() { offset += pageLength.value; loadRows(true) }
function onFilterChange() { reload() }

watch(pageLength, () => { reload() })

watch(
  () => props.doctype,
  async () => {
    if (!props.doctype) return
    offset = 0
    rows.value = []
    allColumns.value = []
    // Apply hook-provided defaults (fall back to sane defaults if not set)
    activeFilters.value = { ...props.defaultFilters }
    sortField.value = props.defaultSort?.field || 'modified'
    sortDir.value   = props.defaultSort?.dir   || 'desc'
    await loadMeta()
    await loadRows(false)
  },
  { immediate: true },
)

// ── Navigation ────────────────────────────────────────────────────────────────
function deslug(dt) { return (dt || '').toLowerCase().replace(/\s+/g, '-') }
function openRecord(name) {
  window.open(`/app/${deslug(props.doctype)}/${encodeURIComponent(name)}`, '_blank')
}
function openNew() {
  window.open(`/app/${deslug(props.doctype)}/new-${deslug(props.doctype)}-1`, '_blank')
}
</script>
