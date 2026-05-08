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
import ExtListView from './ExtListView.vue'
import { getLucideIcon } from '../lucideIcons.js'

const showSearch = ref(false)
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
function csrf() {
  return window.csrf_token || window.boot?.csrf_token || ''
}

function apiGet(method) {
  return fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': csrf(),
      Accept: 'application/json',
    },
    body: JSON.stringify({}),
  })
    .then((r) => r.json())
    .then((d) => d.message)
}

// ── Load sidebar items from Python hook ─────────────────────────────────────
async function loadSidebarItems() {
  try {
    const items = await apiGet('frappe_crm_xt.api.sidebar.get_sidebar_items')
    sidebarItems.value = Array.isArray(items) ? items : []
    injectFCRMRoute()
    injectCustomSidebarBtns()
  } catch {
    /* silent */
  }
}

// ── Recursively search sidebar items for a doctype config ───────────────────
function findItemForDoctype(items, doctype) {
  for (const item of items) {
    if (item.doctype === doctype) return item
    if (item.type === 'group' && Array.isArray(item.items)) {
      const found = findItemForDoctype(item.items, doctype)
      if (found) return found
    }
  }
  return null
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
  render() {
    return h('div', { style: 'height:100%;overflow:hidden;' })
  },
  mounted() {
    this._mountApp(this.$route?.params?.doctype || '')
  },
  beforeUnmount() {
    this._app?.unmount()
    this._app = null
  },
  beforeRouteUpdate(to) {
    this._mountApp(to.params?.doctype || '')
  },
  methods: {
    _mountApp(doctype) {
      if (this._app) {
        this._app.unmount()
        this._app = null
      }
      if (!doctype) return
      // Look up hook config — search recursively inside groups too
      const itemCfg = findItemForDoctype(sidebarItems.value, doctype) || {}
      this._app = createApp(ExtListView, {
        doctype,
        defaultFilters: itemCfg.default_filters || {},
        hiddenFilters: itemCfg.hidden_filters || {},
        fields: itemCfg.fields || [],
        defaultSort: itemCfg.default_sort || {},
        searchField: itemCfg.search_field || '',
        rowUrl: itemCfg.row_url || '',
      })
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
  const router =
    document.querySelector('#app')?.__vue_app__?.config?.globalProperties
      ?.$router
  if (!router) {
    setTimeout(injectFCRMRoute, 200)
    return
  }

  const routes = router.getRoutes()
  if (routes.some((r) => r.path === '/xt/list/:doctype')) return

  try {
    router.addRoute({ path: '/xt/list/:doctype', component: _extShim })
    // If the page loaded directly on one of our routes, the router already
    // resolved to a 404/redirect before we registered the route.  Re-push
    // the current location so the newly-added route can match.
    const loc = window.location.pathname // e.g. /crm/xt/list/CRM%20Lead
    const base = '/crm'
    const routerPath = loc.startsWith(base) ? loc.slice(base.length) : loc
    if (/^\/xt\/list\//i.test(routerPath)) {
      router.replace(routerPath + window.location.search + window.location.hash)
    }
  } catch (e) {
    console.warn('[crm-xt] route injection failed', e)
  }
}

// ── Lucide icon renderer ─────────────────────────────────────────────────────
// getLucideIcon(name) returns a complete <svg>…</svg> string from lucide-static.
// We strip the outer <svg> tag and re-wrap with our own so we can control
// class, size, and stroke-width to match FCRM's sidebar icon style.
const _svgInnerCache = {}
function lucideIconInner(name) {
  if (_svgInnerCache[name]) return _svgInnerCache[name]
  const raw = getLucideIcon(name)
  // Extract everything between the first > and last </svg>
  const inner = raw
    .replace(/^[\s\S]*?<svg[^>]*>/, '')
    .replace(/<\/svg>\s*$/, '')
  _svgInnerCache[name] = inner
  return inner
}

// ── Build a sidebar nav button (shared by top-level and group children) ──────
function _makeSidebarBtn(item, callLogsBtn) {
  const btn = document.createElement('button')
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
          ${lucideIconInner(icon)}
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
  return btn
}

// ── Inject custom sidebar buttons below "Call Logs" ──────────────────────────
function injectCustomSidebarBtns() {
  if (!sidebarItems.value.length) return

  // Find "Call Logs" as the anchor
  const callLogsSpan = Array.from(document.querySelectorAll('span')).find(
    (s) => s.textContent.trim() === 'Call Logs' && s.closest('button'),
  )
  const callLogsBtn = callLogsSpan?.closest('button')
  if (!callLogsBtn) return

  let anchor = callLogsBtn

  sidebarItems.value.forEach((item, idx) => {
    // ── Separator ────────────────────────────────────────────────────────────
    if (item.type === 'separator') {
      const id = `crm-xt-sb-sep-${idx}`
      if (document.getElementById(id)) {
        anchor = document.getElementById(id)
        return
      }
      const hr = document.createElement('hr')
      hr.id = id
      hr.className = 'mx-2 my-1 border-outline-gray-1'
      anchor.insertAdjacentElement('afterend', hr)
      anchor = hr
      return
    }

    const id = `crm-xt-sb-${item.type}-${item.label.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`
    if (document.getElementById(id)) {
      anchor = document.getElementById(id)
      return
    }

    // ── Group (collapsible section) ──────────────────────────────────────────
    if (item.type === 'group') {
      const wrapper = document.createElement('div')
      wrapper.id = id
      wrapper.className = 'flex flex-col'

      // Header button
      const icon = item.icon || 'folder'
      const headerBtn = document.createElement('button')
      headerBtn.className = callLogsBtn.className
      headerBtn.setAttribute('aria-label', item.label)
      headerBtn.setAttribute('aria-expanded', 'false')
      headerBtn.innerHTML = `
        <div class="flex w-full items-center justify-between duration-300 ease-in-out px-2 py-[7px]">
          <div class="flex items-center truncate">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
              stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"
              class="flex items-center size-4 text-ink-gray-8">
              ${lucideIconInner(icon)}
            </svg>
            <span class="flex-1 flex-shrink-0 truncate text-sm duration-300 ease-in-out ml-2 w-auto opacity-100"
              data-state="closed">${item.label}</span>
          </div>
          <svg class="crm-xt-chevron size-4 text-ink-gray-5 transition-transform duration-200"
            viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </div>
      `

      // Children container (hidden by default)
      const childrenEl = document.createElement('div')
      childrenEl.className = 'flex-col pl-2'
      childrenEl.style.display = 'none'

      // Build child items
      ;(item.items || []).forEach((child, cidx) => {
        if (child.type === 'separator') {
          const hr = document.createElement('hr')
          hr.className = 'mx-2 my-1 border-outline-gray-1'
          childrenEl.appendChild(hr)
          return
        }
        const childBtn = _makeSidebarBtn(child, callLogsBtn)
        childrenEl.appendChild(childBtn)
      })

      // Toggle collapse
      headerBtn.addEventListener('click', () => {
        const expanded = headerBtn.getAttribute('aria-expanded') === 'true'
        headerBtn.setAttribute('aria-expanded', String(!expanded))
        const chevron = headerBtn.querySelector('.crm-xt-chevron')
        if (!expanded) {
          childrenEl.style.display = 'flex'
          if (chevron) chevron.style.transform = 'rotate(180deg)'
        } else {
          childrenEl.style.display = 'none'
          if (chevron) chevron.style.transform = ''
        }
      })

      wrapper.appendChild(headerBtn)
      wrapper.appendChild(childrenEl)
      anchor.insertAdjacentElement('afterend', wrapper)
      anchor = wrapper
      return
    }

    // ── list_view / route ────────────────────────────────────────────────────
    const btn = _makeSidebarBtn(item, callLogsBtn)
    btn.id = id
    anchor.insertAdjacentElement('afterend', btn)
    anchor = btn
  })
}

// ── Sidebar Search button injection (Notifications container) ────────────────
function injectSidebarBtn() {
  if (document.getElementById('crm-xt-search-btn')) return

  const notifBtn =
    document.getElementById('notifications-btn') ||
    Array.from(document.querySelectorAll('button')).find(
      (b) => b.querySelector('span')?.textContent?.trim() === 'Notifications',
    )
  const container = notifBtn?.closest('div.flex.flex-col')
  if (!container) return

  const isMac = /Mac|iPhone|iPad/i.test(
    navigator.platform || navigator.userAgent,
  )
  const modKey = isMac ? '⌘' : 'Ctrl'

  const btn = document.createElement('button')
  btn.id = 'crm-xt-search-btn'
  btn.className =
    'flex h-7.5 cursor-pointer items-center rounded text-ink-gray-8 duration-300 ease-in-out focus:outline-none focus:transition-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-outline-gray-3 hover:bg-surface-gray-2 relative mx-2 my-[1.5px]'
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
  btn.addEventListener('click', () => {
    showSearch.value = true
  })
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
    openSearch: () => {
      showSearch.value = true
    },
    closeSearch: () => {
      showSearch.value = false
    },
  }

  injectSidebarBtn()
  loadSidebarItems() // fetches items → injects custom buttons + FCRM route

  // Re-inject on navigation (FCRM rebuilds sidebar on route changes)
  window.addEventListener('popstate', () =>
    setTimeout(() => {
      injectSidebarBtn()
      injectCustomSidebarBtns()
    }, 120),
  )

  // MutationObserver: re-inject if FCRM Vue router rebuilds the sidebar
  const obs = new MutationObserver(() => {
    if (!document.getElementById('crm-xt-search-btn')) injectSidebarBtn()
    if (sidebarItems.value.length) {
      // Find first item with a label (separators have none)
      const firstLabeled = sidebarItems.value.find((i) => i.label)
      const firstId = firstLabeled
        ? `crm-xt-sb-${firstLabeled.type}-${firstLabeled.label.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`
        : 'crm-xt-sb-sep-0'
      if (!document.getElementById(firstId)) injectCustomSidebarBtns()
    }
  })
  obs.observe(document.body, { childList: true, subtree: true })
})
</script>
