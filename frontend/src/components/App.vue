<template>
  <SearchDialog
    :show="showSearch"
    @close="showSearch = false"
    @navigate="onNavigate"
  />
</template>

<script setup>
import { ref, onMounted, h, createApp } from 'vue'
import SearchDialog from './SearchDialog.vue'
import ExtListView  from './ExtListView.vue'

const showSearch  = ref(false)
const sidebarItems = ref([])

// ── SPA navigation helper ───────────────────────────────────────────────────
function onNavigate(route) {
  showSearch.value = false
  try {
    window.history.pushState({}, '', route.path)
    window.dispatchEvent(new PopStateEvent('popstate'))
  } catch {
    window.location.href = route.path
  }
}

// ── Generic fetch helper ────────────────────────────────────────────────────
function csrf() { return window.csrf_token || window.boot?.csrf_token || '' }

function apiGet(method) {
  return fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf(), Accept: 'application/json' },
    body: JSON.stringify({}),
  }).then(r => r.json()).then(d => d.message)
}

// ── Load sidebar items from Python hook ─────────────────────────────────────
async function loadSidebarItems() {
  try {
    const items = await apiGet('frappe_crm_xt.api.sidebar.get_sidebar_items')
    sidebarItems.value = Array.isArray(items) ? items : []
    injectFCRMRoute()
    injectCustomSidebarBtns()
  } catch { /* silent */ }
}

// ── Shim component injected into FCRM's router ──────────────────────────────
// Problem: our bundle ships its own Vue copy.  If we register ExtListView
// directly, FCRM's renderer runs the component but the reactive refs it
// creates belong to our Vue instance — FCRM's renderer never subscribed to
// them so updates are invisible and the view stays blank.
//
// Solution: register a thin "shim" component (plain options-API object)
// that FCRM's Vue renders as a bare div.  In mounted() we create our own
// Vue app (our Vue instance) and mount ExtListView inside that div.
// Vue 3 VNodes are interoperable (they're plain objects keyed on
// __v_isVNode), so our h() output renders fine inside FCRM's Vue renderer.
const _extShim = {
  name: 'CrmXtListView',
  render() { return h('div', { style: 'height:100%;overflow:hidden;' }) },
  mounted()  { this._mountApp(this.$route?.params?.doctype || '') },
  beforeUnmount() { this._app?.unmount(); this._app = null },
  beforeRouteUpdate(to) { this._mountApp(to.params?.doctype || '') },
  methods: {
    _mountApp(doctype) {
      if (this._app) { this._app.unmount(); this._app = null }
      if (!doctype) return
      this._app = createApp(ExtListView, { doctype })
      this._app.mount(this.$el)
    },
  },
}

// ── Inject our list-view route into FCRM's Vue Router ───────────────────────
// FCRM's router is configured with base="/crm", so all route paths are
// relative to that base (e.g. "/leads" not "/crm/leads").
let _routeAttempts = 0
function injectFCRMRoute() {
  if (_routeAttempts++ > 30) return
  const router = document.querySelector('#app')?.__vue_app__?.config?.globalProperties?.$router
  if (!router) { setTimeout(injectFCRMRoute, 200); return }

  const routes = router.getRoutes()
  if (routes.some(r => r.path === '/xt/list/:doctype')) return

  try {
    router.addRoute({ path: '/xt/list/:doctype', component: _extShim })
    // If the page loaded directly on one of our routes, the router already
    // resolved to a 404/redirect before we registered the route.  Re-push
    // the current location so the newly-added route can match.
    const loc = window.location.pathname          // e.g. /crm/xt/list/CRM%20Lead
    const base = '/crm'
    const routerPath = loc.startsWith(base) ? loc.slice(base.length) : loc
    if (/^\/xt\/list\//i.test(routerPath)) {
      router.replace(routerPath + window.location.search + window.location.hash)
    }
  } catch (e) {
    console.warn('[crm-xt] route injection failed', e)
  }
}

// ── Feather icon path lookup ─────────────────────────────────────────────────
const ICON_PATHS = {
  'list':       '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
  'file-text':  '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>',
  'users':      '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  'briefcase':  '<rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
  'grid':       '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>',
  'external-link': '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
  'link':       '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
}
function iconPaths(name) { return ICON_PATHS[name] || ICON_PATHS['list'] }

// ── Inject custom sidebar buttons below "Call Logs" ──────────────────────────
function injectCustomSidebarBtns() {
  if (!sidebarItems.value.length) return

  // Find "Call Logs" as the anchor
  const callLogsSpan = Array.from(document.querySelectorAll('span'))
    .find(s => s.textContent.trim() === 'Call Logs' && s.closest('button'))
  const callLogsBtn = callLogsSpan?.closest('button')
  if (!callLogsBtn) return

  let anchor = callLogsBtn
  for (const item of sidebarItems.value) {
    const id = `crm-xt-sb-item-${item.label.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`
    if (document.getElementById(id)) {
      anchor = document.getElementById(id)
      continue
    }

    const btn = document.createElement('button')
    btn.id = id
    // Exact same classes as the existing nav buttons (copied from Call Logs)
    btn.className = callLogsBtn.className
    btn.setAttribute('aria-label', item.label)

    const isRoute = item.type === 'route'
    const icon = item.icon || (isRoute ? 'external-link' : 'list')

    btn.innerHTML = `
      <div class="flex w-full items-center justify-between duration-300 ease-in-out px-2 py-[7px]">
        <div class="flex items-center truncate">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
            stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
            class="flex items-center size-4 text-ink-gray-8">
            ${iconPaths(icon)}
          </svg>
          <span class="flex-1 flex-shrink-0 truncate text-sm duration-300 ease-in-out ml-2 w-auto opacity-100"
            data-state="closed">${item.label}</span>
        </div>
      </div>
    `

    btn.addEventListener('click', () => {
      if (item.type === 'list_view' && item.doctype) {
        const path = `/crm/xt/list/${encodeURIComponent(item.doctype)}`
        window.history.pushState({}, '', path)
        window.dispatchEvent(new PopStateEvent('popstate'))
      } else {
        const url = item.url || item.route || ''
        if (url.startsWith('http')) window.open(url, '_blank')
        else window.location.href = url
      }
    })

    anchor.insertAdjacentElement('afterend', btn)
    anchor = btn
  }
}

// ── Sidebar Search button injection (Notifications container) ────────────────
function injectSidebarBtn() {
  if (document.getElementById('crm-xt-search-btn')) return

  const notifBtn = document.getElementById('notifications-btn')
    || Array.from(document.querySelectorAll('button'))
        .find(b => b.querySelector('span')?.textContent?.trim() === 'Notifications')
  const container = notifBtn?.closest('div.flex.flex-col')
  if (!container) return

  const isMac  = /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent)
  const modKey = isMac ? '⌘' : 'Ctrl'

  const btn = document.createElement('button')
  btn.id        = 'crm-xt-search-btn'
  btn.className = 'flex h-7.5 cursor-pointer items-center rounded text-ink-gray-8 duration-300 ease-in-out focus:outline-none focus:transition-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-outline-gray-3 hover:bg-surface-gray-2 relative mx-2 my-[1.5px]'
  btn.setAttribute('aria-label', 'Search')
  btn.innerHTML = `
    <div class="flex w-full items-center justify-between duration-300 ease-in-out px-2 py-[7px]">
      <div class="flex items-center truncate">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
          class="flex items-center size-4 text-ink-gray-8">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        <span class="flex-1 flex-shrink-0 truncate text-sm duration-300 ease-in-out ml-2 w-auto opacity-100">Search</span>
      </div>
      <span class="flex gap-1 items-center">
        <kbd class="text-[0.65rem] text-ink-gray-5">${modKey}</kbd>
        <kbd class="text-xs text-ink-gray-5">K</kbd>
      </span>
    </div>
  `
  btn.addEventListener('click', () => { showSearch.value = true })
  container.insertBefore(btn, notifBtn.nextSibling)
}

// ── Mount ───────────────────────────────────────────────────────────────────
onMounted(() => {
  // Keyboard shortcut
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault()
      showSearch.value = !showSearch.value
    }
  })

  // Global API
  window.crmXt = {
    openSearch:  () => { showSearch.value = true  },
    closeSearch: () => { showSearch.value = false },
  }

  injectSidebarBtn()
  loadSidebarItems()  // fetches items → injects custom buttons + FCRM route

  // Re-inject on navigation (FCRM rebuilds sidebar on route changes)
  window.addEventListener('popstate', () => setTimeout(() => {
    injectSidebarBtn()
    injectCustomSidebarBtns()
  }, 120))

  // MutationObserver: re-inject if FCRM Vue router rebuilds the sidebar
  const obs = new MutationObserver(() => {
    if (!document.getElementById('crm-xt-search-btn')) injectSidebarBtn()
    if (sidebarItems.value.length) {
      const firstId = `crm-xt-sb-item-${sidebarItems.value[0].label.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`
      if (!document.getElementById(firstId)) injectCustomSidebarBtns()
    }
  })
  obs.observe(document.body, { childList: true, subtree: true })
})
</script>
