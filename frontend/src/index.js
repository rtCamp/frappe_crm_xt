/**
 * frappe_crm_xt — IIFE frontend bundle
 *
 * Injected into the FCRM SPA page via <script defer>.  Mounts a Vue 3 app
 * on a portal div, providing:
 *   1. Cmd/Ctrl+K global search dialog (backed by frappe_search or fallback).
 */
import { createApp } from 'vue'
import App from './components/App.vue'

const STYLES = `
/* Dialog fade transition */
.crm-xt-fade-enter-active, .crm-xt-fade-leave-active { transition: opacity .15s ease; }
.crm-xt-fade-enter-from, .crm-xt-fade-leave-to { opacity: 0; }

/* frappe-ui Dialog overlay color (defined in CRM theme but needed by our secondary app) */
.bg-black-overlay-200 { background-color: #00000045; }
.dark:bg-black-overlay-700 { background-color: #000000b8; }

/* mark highlight in search excerpts */
#crm-xt-app mark {
  background: #fef08a; color: inherit; border-radius: 2px; padding: 0 1px;
}

/* Sidebar search button — collapsed sidebar hides text */
.w-\\[52px\\] #crm-xt-search-btn span:not(.grid) { display: none; }
`

function injectStyles() {
  if (document.getElementById('crm-xt-styles')) return
  const s = document.createElement('style')
  s.id = 'crm-xt-styles'
  s.textContent = STYLES
  document.head.appendChild(s)
}

function mount() {
  injectStyles()
  const el = document.createElement('div')
  el.id = 'crm-xt-app'
  document.body.appendChild(el)
  createApp(App).mount(el)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mount)
} else {
  mount()
}
