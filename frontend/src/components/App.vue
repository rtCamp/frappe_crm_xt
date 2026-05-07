<template>
  <SearchDialog
    :show="showSearch"
    @close="showSearch = false"
    @navigate="onNavigate"
  />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import SearchDialog from './SearchDialog.vue'

const showSearch = ref(false)

function onNavigate(route) {
  showSearch.value = false
  try {
    window.history.pushState({}, '', route.path)
    window.dispatchEvent(new PopStateEvent('popstate'))
  } catch {
    window.location.href = route.path
  }
}

onMounted(() => {
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault()
      showSearch.value = !showSearch.value
    }
  })

  // Expose globally so external callers (e.g. a toolbar button) can open it
  window.crmXt = {
    openSearch: () => { showSearch.value = true },
    closeSearch: () => { showSearch.value = false },
  }

  // Inject the sidebar Search button
  injectSidebarBtn()
  // Re-inject after route changes (FCRM's Vue router may rebuild the sidebar)
  window.addEventListener('popstate', () => setTimeout(injectSidebarBtn, 120))
  // MutationObserver to catch sidebar rebuilds
  const sidebarObserver = new MutationObserver(() => {
    if (!document.getElementById('crm-xt-search-btn')) injectSidebarBtn()
  })
  sidebarObserver.observe(document.body, { childList: true, subtree: true })
})

function injectSidebarBtn() {
  if (document.getElementById('crm-xt-search-btn')) return

  // Find the Notifications button and get its wrapping div.flex.flex-col container
  const notifBtn = document.getElementById('notifications-btn')
    || Array.from(document.querySelectorAll('button')).find(
        (b) => b.querySelector('span')?.textContent?.trim() === 'Notifications',
      )
  const container = notifBtn?.closest('div.flex.flex-col')
  if (!container) return

  const isMac = /Mac|iPhone|iPad/i.test(navigator.platform || navigator.userAgent)
  const modKey = isMac ? '⌘' : 'Ctrl'

  const btn = document.createElement('button')
  btn.id = 'crm-xt-search-btn'
  // Same classes as the Notifications button
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
  // Insert after the Notifications button
  container.insertBefore(btn, notifBtn.nextSibling)
}
</script>
