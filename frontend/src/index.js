/**
 * frappe_crm_xt — IIFE frontend bundle
 *
 * Injected via <script defer> into the FCRM SPA page. Reads feature flags
 * from window.crm_xt_features (set by our www/crm.py via boot) and:
 *   1. Mounts a Vue search dialog on a dedicated DOM node.
 *   2. Registers Cmd/Ctrl+K to open the dialog.
 */
import { createApp, ref } from 'vue'
import SearchDialog from './components/SearchDialog.vue'

const STYLES = `
.crm-xt-overlay {
  position: fixed; inset: 0; z-index: 9999;
  background: rgba(15,23,42,.45);
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 12vh;
}
.crm-xt-modal {
  width: min(600px, 92vw);
  background: #fff; border-radius: 10px;
  box-shadow: 0 20px 60px rgba(0,0,0,.22);
  overflow: hidden;
  font: 14px/1.4 system-ui, sans-serif;
}
.crm-xt-input-row {
  display: flex; align-items: center;
  padding: 10px 14px; gap: 8px;
}
.crm-xt-search-icon { width: 18px; height: 18px; color: #94a3b8; flex-shrink: 0; }
.crm-xt-input {
  flex: 1; border: 0; outline: 0; background: transparent;
  font-size: 15px; color: #0f172a;
}
.crm-xt-esc-badge {
  font-size: 11px; color: #94a3b8;
  border: 1px solid #e2e8f0; border-radius: 4px;
  padding: 1px 5px;
}
.crm-xt-divider { border: none; border-top: 1px solid #f1f5f9; margin: 0; }
.crm-xt-results { max-height: 55vh; overflow-y: auto; }
.crm-xt-results ul { list-style: none; margin: 0; padding: 0; }
.crm-xt-row {
  padding: 10px 14px; cursor: pointer;
  border-bottom: 1px solid #f8fafc;
}
.crm-xt-row--active, .crm-xt-row:hover { background: #f8fafc; }
.crm-xt-row-label { color: #0f172a; font-weight: 500; font-size: 14px; }
.crm-xt-row-value { color: #475569; font-size: 12px; margin-top: 2px; }
.crm-xt-empty { padding: 18px 14px; color: #64748b; text-align: center; }
.crm-xt-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; height: 40px;
}
.crm-xt-count { font-size: 12px; color: #64748b; }
.crm-xt-load-more {
  font-size: 12px; color: #3b82f6; background: none; border: none;
  cursor: pointer; padding: 4px 8px;
}
.crm-xt-load-more:hover { text-decoration: underline; }
.crm-xt-fade-enter-active, .crm-xt-fade-leave-active { transition: opacity .15s; }
.crm-xt-fade-enter-from, .crm-xt-fade-leave-to { opacity: 0; }
`

function injectStyles() {
  if (document.getElementById('crm-xt-styles')) return
  const s = document.createElement('style')
  s.id = 'crm-xt-styles'
  s.textContent = STYLES
  document.head.appendChild(s)
}

function getFeatures() {
  const f = window.crm_xt_features || {}
  return {
    frappe_search: !!f.frappe_search,
    bridge: !!f.bridge,
  }
}

function init() {
  injectStyles()

  const mountEl = document.createElement('div')
  mountEl.id = 'crm-xt-app'
  document.body.appendChild(mountEl)

  const showSearch = ref(false)
  const features = getFeatures()

  const app = createApp({
    setup() {
      function openSearch() { showSearch.value = true }
      function closeSearch() { showSearch.value = false }

      function onNavigate(route) {
        // FCRM is a Vue Router SPA — push via history API and fire popstate
        // so the router picks it up without a full reload.
        try {
          window.history.pushState({}, '', route.path)
          window.dispatchEvent(new PopStateEvent('popstate'))
        } catch {
          window.location.href = route.path
        }
      }

      document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
          e.preventDefault()
          showSearch.value = !showSearch.value
        }
      })

      window.crmXt = { openSearch, closeSearch }

      return { showSearch, features, closeSearch, onNavigate }
    },
    template: `
      <SearchDialog
        :show="showSearch"
        :features="features"
        @close="closeSearch"
        @navigate="onNavigate"
      />
    `,
  })

  app.component('SearchDialog', SearchDialog)
  app.mount(mountEl)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init)
} else {
  init()
}
