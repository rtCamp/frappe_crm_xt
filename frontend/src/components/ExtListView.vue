<template>
  <div class="flex h-full flex-col overflow-hidden bg-surface-white">

    <!-- ── Header ── -->
    <div class="flex h-[52px] shrink-0 items-center justify-between border-b border-outline-gray-2 px-5">
      <h1 class="text-base font-semibold text-ink-gray-9">{{ doctype }}</h1>
      <button
        class="inline-flex h-7 items-center gap-1.5 rounded bg-gray-900 px-3 text-xs font-medium text-white hover:bg-gray-800 focus:outline-none"
        @click="openNew"
      >
        <svg viewBox="0 0 24 24" class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" stroke-width="2.5">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        New
      </button>
    </div>

    <!-- ── Column headers ── -->
    <div class="flex shrink-0 items-center border-b border-outline-gray-2 bg-surface-gray-1 px-5">
      <div
        v-for="col in columns" :key="col.key"
        class="flex-1 truncate py-2 pr-4 text-xs font-medium uppercase tracking-wide text-ink-gray-5"
      >
        {{ col.label }}
      </div>
    </div>

    <!-- ── Rows ── -->
    <div class="flex-1 divide-y divide-outline-gray-1 overflow-y-auto">
      <div v-if="loading" class="flex h-24 items-center justify-center text-sm text-ink-gray-5">
        Loading…
      </div>
      <template v-else-if="rows.length">
        <div
          v-for="row in rows" :key="row.name"
          class="flex cursor-pointer items-center px-5 hover:bg-surface-gray-1"
          @click="openRecord(row.name)"
        >
          <div
            v-for="col in columns" :key="col.key"
            class="flex-1 truncate py-2.5 pr-4 text-sm text-ink-gray-8"
          >
            {{ row[col.key] ?? '—' }}
          </div>
        </div>
      </template>
      <div v-else class="flex h-32 items-center justify-center text-sm text-ink-gray-5">
        No records found
      </div>
    </div>

    <!-- ── Footer / Pagination ── -->
    <div class="flex shrink-0 items-center justify-between border-t border-outline-gray-2 px-5 py-2">
      <span class="text-xs text-ink-gray-5">
        {{ rows.length ? `${offset + 1}–${offset + rows.length}` : '0 records' }}
      </span>
      <div class="flex gap-2">
        <button
          v-if="offset > 0"
          class="inline-flex h-7 items-center rounded border border-outline-gray-3 px-3 text-xs text-ink-gray-7 hover:bg-surface-gray-2"
          @click="prevPage"
        >← Prev</button>
        <button
          v-if="hasMore"
          class="inline-flex h-7 items-center rounded border border-outline-gray-3 px-3 text-xs text-ink-gray-7 hover:bg-surface-gray-2"
          @click="nextPage"
        >Next →</button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ doctype: { type: String, required: true } })

const rows      = ref([])
const columns   = ref([])
const loading   = ref(false)
const offset    = ref(0)
const hasMore   = ref(false)
const PAGE_SIZE = 20

// ── API helper ──────────────────────────────────────────────────────────────
function csrf() { return window.csrf_token || window.boot?.csrf_token || '' }

async function call(method, args) {
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf(), Accept: 'application/json' },
    body: JSON.stringify(args),
  })
  const data = await res.json()
  if (data.exc) throw new Error(data.exc)
  return data.message
}

// ── Columns from doctype meta ───────────────────────────────────────────────
async function loadColumns() {
  try {
    const meta = await call('frappe.client.get', { doctype: 'DocType', name: props.doctype })
    const ALLOWED = new Set(['Data', 'Link', 'Select', 'Date', 'Datetime', 'Int', 'Float', 'Currency', 'Small Text'])
    const listFields = (meta?.fields || [])
      .filter(f => f.in_list_view && !f.hidden && ALLOWED.has(f.fieldtype))
      .slice(0, 5)
    columns.value = [
      { label: 'Name', key: 'name' },
      ...listFields.map(f => ({ label: f.label, key: f.fieldname })),
    ]
  } catch {
    columns.value = [{ label: 'Name', key: 'name' }]
  }
}

// ── Row data ────────────────────────────────────────────────────────────────
async function loadRows() {
  if (!props.doctype) return
  loading.value = true
  try {
    const fields = JSON.stringify(columns.value.map(c => c.key))
    const data = await call('frappe.client.get_list', {
      doctype: props.doctype,
      fields,
      limit: PAGE_SIZE + 1,
      start: offset.value,
      order_by: 'modified desc',
    })
    hasMore.value = data.length > PAGE_SIZE
    rows.value    = data.slice(0, PAGE_SIZE)
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

function nextPage() { offset.value += PAGE_SIZE;                             loadRows() }
function prevPage() { offset.value = Math.max(0, offset.value - PAGE_SIZE); loadRows() }

function deslug(dt) { return (dt || '').toLowerCase().replace(/\s+/g, '-') }
function openRecord(name) { window.open(`/app/${deslug(props.doctype)}/${encodeURIComponent(name)}`, '_blank') }
function openNew()        { window.open(`/app/${deslug(props.doctype)}/new-${deslug(props.doctype)}-1`, '_blank') }

// ── Reload when doctype changes ─────────────────────────────────────────────
watch(() => props.doctype, async () => {
  if (!props.doctype) return
  offset.value = 0
  await loadColumns()
  await loadRows()
}, { immediate: true })
</script>
