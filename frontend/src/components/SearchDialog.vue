<template>
  <!-- Backdrop -->
  <Transition name="crm-xt-fade">
    <div v-if="show" class="crm-xt-overlay" @mousedown.self="close">
      <div class="crm-xt-modal" role="dialog" aria-label="CRM Search">
        <!-- Input row -->
        <div class="crm-xt-input-row">
          <svg class="crm-xt-search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref="inputRef"
            v-model="query"
            type="text"
            class="crm-xt-input"
            placeholder="CRM Search"
            autocomplete="off"
            @keydown="handleKeyDown"
            @input="onInput"
          />
          <span class="crm-xt-esc-badge">esc</span>
        </div>

        <hr class="crm-xt-divider" />

        <!-- Results -->
        <div v-if="results.length" class="crm-xt-results">
          <ul>
            <li
              v-for="(result, i) in results"
              :key="result.value + i"
              class="crm-xt-row"
              :class="{ 'crm-xt-row--active': activeIdx === i }"
              @click="selectResult(result)"
              @mouseenter="activeIdx = i"
            >
              <div class="crm-xt-row-label">{{ result.label }}</div>
              <div class="crm-xt-row-value" v-html="result.value"></div>
            </li>
          </ul>
        </div>

        <div v-else-if="query.length > 0 && !loading" class="crm-xt-empty">
          No results for <strong>{{ query }}</strong>
        </div>

        <div v-else-if="loading" class="crm-xt-empty">Searching…</div>

        <div v-else class="crm-xt-empty">Type to search leads, deals, contacts…</div>

        <hr v-if="results.length" class="crm-xt-divider" />

        <div v-if="results.length" class="crm-xt-footer">
          <span class="crm-xt-count"><b>{{ results.length }}</b> results found</span>
          <button v-if="hasMore" class="crm-xt-load-more" @click="loadMore">Load more</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  show: Boolean,
  features: {
    type: Object,
    default: () => ({
      frappe_search: false,
      bridge: false,
    }),
  },
})

const emit = defineEmits(['close', 'navigate'])

const query = ref('')
const results = ref([])
const loading = ref(false)
const hasMore = ref(false)
const activeIdx = ref(0)
const inputRef = ref(null)

let offset = 0
let debounceTimer = null
let inflight = null

// Doctype sets — bridge-aware
const BRIDGE_DOCTYPES = ['Lead', 'Opportunity', 'Customer', 'Contact', 'Address', 'Prospect']
const FCRM_DOCTYPES = ['CRM Lead', 'CRM Deal', 'Contact', 'CRM Task', 'FCRM Note']

// Route builders — bridge-aware
const BRIDGE_ROUTES = {
  Lead: (n) => ({ path: `/crm/leads/${encodeURIComponent(n)}` }),
  Opportunity: (n) => ({ path: `/crm/deals/${encodeURIComponent(n)}` }),
  Customer: (n) => ({ path: `/crm/contacts/${encodeURIComponent(n)}` }),
  Contact: (n) => ({ path: `/crm/contacts/${encodeURIComponent(n)}` }),
}
const FCRM_ROUTES = {
  'CRM Lead': (n) => ({ path: `/crm/leads/${encodeURIComponent(n)}` }),
  'CRM Deal': (n) => ({ path: `/crm/deals/${encodeURIComponent(n)}` }),
  Contact: (n) => ({ path: `/crm/contacts/${encodeURIComponent(n)}` }),
}

function allowedDoctypes() {
  return props.features.bridge ? BRIDGE_DOCTYPES : FCRM_DOCTYPES
}

function routeFor(doctype, name) {
  const map = props.features.bridge ? BRIDGE_ROUTES : FCRM_ROUTES
  return map[doctype]?.(name) || null
}

watch(
  () => props.show,
  (val) => {
    if (val) {
      query.value = ''
      results.value = []
      hasMore.value = false
      activeIdx.value = 0
      nextTick(() => inputRef.value?.focus())
    }
  },
)

function close() {
  emit('close')
}

function handleKeyDown(e) {
  if (e.key === 'Escape') { e.preventDefault(); close(); return }
  if (e.key === 'Enter') {
    e.preventDefault()
    if (results.value[activeIdx.value]) selectResult(results.value[activeIdx.value])
    else if (query.value) search(false)
    return
  }
  if (e.key === 'ArrowDown') { e.preventDefault(); activeIdx.value = Math.min(activeIdx.value + 1, results.value.length - 1); return }
  if (e.key === 'ArrowUp') { e.preventDefault(); activeIdx.value = Math.max(activeIdx.value - 1, 0); return }
}

function onInput() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => search(false), 250)
}

function loadMore() {
  search(true)
}

function search(append) {
  if (!query.value) { results.value = []; hasMore.value = false; return }
  if (!append) { offset = 0 }

  if (inflight) { inflight.abort(); inflight = null }
  loading.value = true

  if (props.features.frappe_search) {
    searchViaFrappeSearch(append)
  } else {
    searchViaFrappeClient(append)
  }
}

function getCsrfToken() {
  return window.csrf_token || window.boot?.csrf_token || ''
}

function searchViaFrappeSearch(append) {
  const ctrl = new AbortController()
  inflight = ctrl

  const doctypes = allowedDoctypes()
  const params = new URLSearchParams({ text: query.value, start: String(offset), limit: '50' })
  doctypes.forEach((d) => params.append('allowed_doctypes', d))

  fetch('/api/method/frappe_search.api.search.get_global_search_results', {
    method: 'POST',
    credentials: 'same-origin',
    signal: ctrl.signal,
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-Frappe-CSRF-Token': getCsrfToken(),
      Accept: 'application/json',
    },
    body: params.toString(),
  })
    .then((r) => r.json())
    .then((data) => {
      if (ctrl.signal.aborted) return
      const raw = data?.message
      const list = Array.isArray(raw) ? raw[0] || raw : []
      hasMore.value = !!(Array.isArray(raw) ? raw[1] : false)
      const mapped = mapResults(list)
      results.value = append ? [...results.value, ...mapped] : mapped
      activeIdx.value = 0
      offset += 50
    })
    .catch((err) => { if (err.name !== 'AbortError') results.value = [] })
    .finally(() => { loading.value = false })
}

function searchViaFrappeClient(append) {
  const ctrl = new AbortController()
  inflight = ctrl

  const q = query.value
  const doctypes = allowedDoctypes()

  // Fall back: `frappe.client.get_list` for each doctype in parallel
  const fetches = doctypes.slice(0, 4).map((dt) =>
    fetch('/api/method/frappe.client.get_list', {
      method: 'POST',
      credentials: 'same-origin',
      signal: ctrl.signal,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-Frappe-CSRF-Token': getCsrfToken(),
        Accept: 'application/json',
      },
      body: new URLSearchParams({
        doctype: dt,
        filters: JSON.stringify([['name', 'like', `%${q}%`]]),
        fields: JSON.stringify(['name']),
        limit: '10',
      }).toString(),
    })
      .then((r) => r.json())
      .then((d) =>
        (d?.message || []).map((row) => ({
          doctype: dt,
          name: row.name,
          marked_string: row.name,
        })),
      )
      .catch(() => []),
  )

  Promise.all(fetches)
    .then((groups) => {
      if (ctrl.signal.aborted) return
      const flat = groups.flat()
      const mapped = mapResults(flat)
      results.value = append ? [...results.value, ...mapped] : mapped
      hasMore.value = false
      activeIdx.value = 0
    })
    .finally(() => { loading.value = false })
}

function mapResults(list) {
  const seen = new Set()
  return list
    .map((r) => ({
      label: r.doctype ? `${prettyDoctype(r.doctype)}: ${r.name}` : r.name,
      value: r.marked_string || r.name,
      doctype: r.doctype,
      name: r.name,
    }))
    .filter((r) => {
      const key = `${r.doctype}::${r.name}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
}

function prettyDoctype(dt) {
  return dt?.startsWith('CRM ') ? dt.slice(4) : dt
}

function selectResult(result) {
  const route = routeFor(result.doctype, result.name)
  close()
  if (route) emit('navigate', route)
  else window.open(`/app/${result.doctype.toLowerCase().replace(/\s+/g, '-')}/${encodeURIComponent(result.name)}`, '_blank')
}
</script>
