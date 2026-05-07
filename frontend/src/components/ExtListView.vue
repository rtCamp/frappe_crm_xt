<template>
  <div class="flex h-full flex-col overflow-hidden bg-surface-white">

    <!-- ── Header ── -->
    <div class="flex h-[52px] shrink-0 items-center justify-between border-b border-outline-gray-2 px-5">
      <h1 class="text-base font-semibold text-ink-gray-9">{{ doctype }}</h1>
      <Button variant="solid" size="sm" @click="openNew">
        <template #prefix>
          <FeatherIcon name="plus" class="h-3.5 w-3.5" />
        </template>
        New
      </Button>
    </div>

    <!-- ── frappe-ui ListView ── -->
    <ListView
      class="flex-1 overflow-hidden"
      :columns="columns"
      :rows="rows"
      :options="{
        selectable: false,
        showTooltip: true,
        resizeColumn: false,
        getRowRoute: null,
        onRowClick: (row) => openRecord(row.name),
        emptyState: {
          title: loading ? 'Loading…' : 'No records found',
          description: '',
        },
      }"
      row-key="name"
    >
      <ListHeader class="sm:mx-5 mx-3" />
      <ListRows />
      <ListEmptyState v-if="!loading && !rows.length" />
    </ListView>

    <!-- ── Footer ── -->
    <div class="shrink-0 border-t border-outline-gray-2 px-5 py-2">
      <ListFooter
        v-model="pageLength"
        :options="{
          rowCount: rows.length,
          totalCount: totalCount,
        }"
        @loadMore="onLoadMore"
      />
    </div>

  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import {
  ListView,
  ListHeader,
  ListRows,
  ListEmptyState,
  ListFooter,
  Button,
  FeatherIcon,
} from 'frappe-ui'

const props = defineProps({ doctype: { type: String, required: true } })

const rows       = ref([])
const columns    = ref([])
const loading    = ref(false)
const pageLength = ref(20)
const totalCount = ref(0)
let   offset     = 0

// ── API helper ──────────────────────────────────────────────────────────────
function csrf() { return window.csrf_token || window.boot?.csrf_token || '' }

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

// ── Column discovery from DocType meta ─────────────────────────────────────
async function loadColumns() {
  try {
    const meta = await call('frappe.client.get', {
      doctype: 'DocType',
      name: props.doctype,
    })
    const ALLOWED = new Set([
      'Data', 'Link', 'Select', 'Date', 'Datetime',
      'Int', 'Float', 'Currency', 'Small Text',
    ])
    const listFields = (meta?.fields || [])
      .filter(f => f.in_list_view && !f.hidden && ALLOWED.has(f.fieldtype))
      .slice(0, 5)
    columns.value = [
      { label: 'Name', key: 'name', width: 2 },
      ...listFields.map(f => ({ label: f.label, key: f.fieldname, width: 1 })),
    ]
  } catch {
    columns.value = [{ label: 'Name', key: 'name', width: 1 }]
  }
}

// ── Row data ─────────────────────────────────────────────────────────────────
async function loadRows(append = false) {
  if (!props.doctype) return
  loading.value = true
  try {
    const fields = columns.value.map(c => c.key)
    const [data, count] = await Promise.all([
      call('frappe.client.get_list', {
        doctype: props.doctype,
        fields: JSON.stringify(fields),
        limit: pageLength.value,
        start: offset,
        order_by: 'modified desc',
      }),
      append
        ? Promise.resolve(totalCount.value)
        : call('frappe.client.get_count', {
            doctype: props.doctype,
            filters: '[]',
          }),
    ])
    if (!append) totalCount.value = typeof count === 'number' ? count : 0
    rows.value = append ? [...rows.value, ...data] : data
  } catch {
    if (!append) rows.value = []
  } finally {
    loading.value = false
  }
}

function onLoadMore() {
  offset += pageLength.value
  loadRows(true)
}

// ── Re-fetch when page length changes ───────────────────────────────────────
watch(pageLength, () => {
  offset = 0
  rows.value = []
  loadRows(false)
})

// ── Reload when doctype changes ─────────────────────────────────────────────
watch(
  () => props.doctype,
  async () => {
    if (!props.doctype) return
    offset = 0
    rows.value = []
    columns.value = []
    await loadColumns()
    await loadRows(false)
  },
  { immediate: true },
)

// ── Navigation helpers ───────────────────────────────────────────────────────
function deslug(dt) { return (dt || '').toLowerCase().replace(/\s+/g, '-') }
function openRecord(name) {
  window.open(`/app/${deslug(props.doctype)}/${encodeURIComponent(name)}`, '_blank')
}
function openNew() {
  window.open(`/app/${deslug(props.doctype)}/new-${deslug(props.doctype)}-1`, '_blank')
}
</script>
