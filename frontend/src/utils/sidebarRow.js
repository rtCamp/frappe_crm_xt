import { getLucideIcon } from '../lucideIcons.js'

const ROW_TEMPLATE_LABEL = 'Call Logs'

const _svgInnerCache = {}

export function lucideIconInner(name) {
  if (_svgInnerCache[name]) return _svgInnerCache[name]
  const inner = getLucideIcon(name)
    .replace(/^[\s\S]*?<svg[^>]*>/, '')
    .replace(/<\/svg>\s*$/, '')
  _svgInnerCache[name] = inner
  return inner
}

export function findSidebarEl(doc = document) {
  return (
    doc.querySelector('[data-slot="sidebar"]') ||
    doc.querySelector(
      'div.h-full.flex-col.justify-between.transition-all.duration-300',
    )
  )
}

function selfAndDescendants(root, selector) {
  const found = Array.from(root.querySelectorAll(selector))
  return root.matches?.(selector) ? [root, ...found] : found
}

function interactiveEl(root) {
  return root.matches?.('a, button') ? root : root.querySelector('a, button')
}

function isOurs(el) {
  return el.classList.contains('crm-xt') || !!el.closest('.crm-xt')
}

export function findNativeRow(doc = document, labelText = ROW_TEMPLATE_LABEL) {
  const label = Array.from(doc.querySelectorAll('span')).find(
    (s) => s.textContent.trim() === labelText && !isOurs(s),
  )
  const row =
    label &&
    (label.closest('[data-slot="sidebar-item"]') ||
      label.closest('button') ||
      label.closest('a'))
  if (row && !isOurs(row)) return row
  const sidebar = findSidebarEl(doc)
  const modern = Array.from(
    (sidebar || doc).querySelectorAll('[data-slot="sidebar-item"]'),
  ).filter((el) => !isOurs(el) && el.querySelector('a, button'))
  if (modern.length) return modern[modern.length - 1]
  if (!sidebar) return null
  const legacy = Array.from(sidebar.querySelectorAll('nav button')).filter(
    (el) => !isOurs(el) && el.querySelector('span'),
  )
  return legacy.length ? legacy[legacy.length - 1] : null
}
export function findNativeSectionLabel(doc = document) {
  const scope = findSidebarEl(doc) || doc
  return (
    Array.from(scope.querySelectorAll('[data-slot="sidebar-label"]')).find(
      (el) => !isOurs(el),
    ) || null
  )
}

function rowLabelParts(row) {
  const wrapper = row.querySelector('.ml-2, .ml-0, .w-auto, .w-0') || null
  const scope = wrapper || row
  const textEl =
    Array.from(scope.querySelectorAll('*')).find(
      (el) => !el.children.length && el.textContent.trim(),
    ) || (scope.children.length ? null : scope)
  return { wrapper: wrapper || textEl, textEl }
}

function buildIconSvg(doc, icon, className) {
  const svg = doc.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.setAttribute('viewBox', '0 0 24 24')
  svg.setAttribute('fill', 'none')
  svg.setAttribute('stroke', 'currentColor')
  svg.setAttribute('stroke-width', '1.5')
  svg.setAttribute('stroke-linecap', 'round')
  svg.setAttribute('stroke-linejoin', 'round')
  svg.setAttribute('class', className)
  svg.innerHTML = lucideIconInner(icon)
  return svg
}

function swapRowIcon(row, icon) {
  const doc = row.ownerDocument
  const lucideSpan = Array.from(row.querySelectorAll('span')).find((s) =>
    Array.from(s.classList).some((c) => c.startsWith('lucide-')),
  )
  if (lucideSpan) {
    Array.from(lucideSpan.classList)
      .filter((c) => c.startsWith('lucide-'))
      .forEach((c) => lucideSpan.classList.remove(c))
    lucideSpan.textContent = ''
    lucideSpan.appendChild(buildIconSvg(doc, icon, 'size-4'))
    return true
  }
  const svg = row.querySelector('svg')
  if (!svg) return false
  svg.replaceWith(
    buildIconSvg(doc, icon, svg.getAttribute('class') || 'size-4'),
  )
  return true
}

function normaliseToExpanded(root, labelWrapper) {
  if (labelWrapper) {
    const animatesMargin =
      labelWrapper.classList.contains('ml-2') ||
      labelWrapper.classList.contains('ml-0')
    labelWrapper.classList.remove('w-0', 'overflow-hidden', 'opacity-0', 'ml-0')
    labelWrapper.classList.add('w-auto', 'opacity-100')
    if (animatesMargin) labelWrapper.classList.add('ml-2')
  }
  const clickable = interactiveEl(root)
  if (clickable?.classList.contains('justify-center')) {
    clickable.classList.remove('justify-center')
    clickable.classList.add('pl-2')
  }
  root.querySelector('span.grid')?.classList.remove('size-7')
}

export function cloneNativeRow(template, { label, icon, onClick, suffix }) {
  const row = template.cloneNode(true)
  row.removeAttribute('id')
  row.classList.add('crm-xt')
  row
    .querySelectorAll('[accesskey]')
    .forEach((el) => el.removeAttribute('accesskey'))
  row.removeAttribute('accesskey')
  row.setAttribute('data-state', 'inactive')
  row.classList.remove('bg-surface-elevation-3', 'shadow-sm', 'text-ink-gray-8')
  selfAndDescendants(row, '[aria-current]').forEach((el) =>
    el.removeAttribute('aria-current'),
  )
  selfAndDescendants(row, 'a').forEach((a) => {
    a.removeAttribute('href')
    a.removeAttribute('target')
    a.setAttribute('role', 'button')
  })
  row
    .querySelectorAll('[aria-label]')
    .forEach((el) => el.setAttribute('aria-label', label))

  const { wrapper: labelWrapper, textEl } = rowLabelParts(row)
  if (textEl) textEl.textContent = label
  if (labelWrapper) {
    normaliseToExpanded(row, labelWrapper)
    tagCollapsibleLabel(labelWrapper)
  }
  if (icon) swapRowIcon(row, icon)
  row.setAttribute('aria-label', label)
  const clickableEl = interactiveEl(row)
  if (clickableEl) clickableEl.setAttribute('data-xt-link', '')
  const iconHolder = row.querySelector('span.grid')
  if (iconHolder) iconHolder.setAttribute('data-xt-icon', '')
  if (suffix) {
    const clickable = row.querySelector('[role="button"], button') || row
    clickable.insertAdjacentHTML('beforeend', suffix)
  }
  if (onClick) {
    row.addEventListener('click', (event) => {
      event.preventDefault()
      onClick()
    })
  }
  return row
}

export function isModernSidebar(doc = document) {
  return !!doc.querySelector('[data-slot="sidebar"]')
}

// crm only renders a SidebarLabel for its Public/Pinned Views sections, both of
// which are conditional on the async views store — so on a modern host there may
// be no template to clone, permanently for a user with neither. Building the same
// markup keeps the header identical either way instead of dropping to the legacy
// icon row whenever the clone source happens to be missing.
export function createSectionLabel(label, doc = document) {
  const header = doc.createElement('div')
  header.setAttribute('data-slot', 'sidebar-label')
  header.className = 'relative flex h-7 items-center pl-2'
  header.innerHTML = `
    <h3 class="text-base text-ink-gray-5 transition-all duration-300 ease-in-out w-auto opacity-100">
      <span class="flex items-center gap-1.5">
        <span class="lucide-chevron-right -ml-0.5 size-4 shrink-0 text-ink-gray-9 transition-transform duration-300 ease-in-out"></span>
        <span class="truncate"></span>
      </span>
    </h3>
  `
  header.querySelector('span.truncate').textContent = label
  return finishSectionLabel(header, label)
}

export function cloneNativeSectionLabel(template, { label }) {
  const header = template.cloneNode(true)
  header.removeAttribute('id')
  return finishSectionLabel(header, label)
}

function finishSectionLabel(header, label) {
  header.classList.add('crm-xt', 'cursor-pointer', 'select-none')
  header.setAttribute('aria-label', label)
  header.setAttribute('aria-expanded', 'false')

  const textEl = Array.from(header.querySelectorAll('*')).find(
    (el) => !el.children.length && el.textContent.trim(),
  )
  if (textEl) {
    textEl.textContent = label
    let wrapper = textEl
    while (
      wrapper &&
      wrapper !== header &&
      !wrapper.classList.contains('w-auto') &&
      !wrapper.classList.contains('w-0')
    ) {
      wrapper = wrapper.parentElement
    }
    const labelWrapper = wrapper && wrapper !== header ? wrapper : textEl
    normaliseToExpanded(header, labelWrapper)
    tagCollapsibleLabel(labelWrapper)
  }
  const chevron = Array.from(header.querySelectorAll('span')).find((s) =>
    Array.from(s.classList).some((c) => c.startsWith('lucide-chevron')),
  )
  if (chevron) {
    chevron.classList.add('crm-xt-chevron')
    chevron.classList.remove('rotate-90')
    chevron.style.transform = ''
  }
  const clonedDivider = header.querySelector('div:has(> hr), div > hr')
  if (clonedDivider) {
    const el =
      clonedDivider.tagName === 'HR'
        ? clonedDivider.parentElement
        : clonedDivider
    el.setAttribute('data-xt-divider', '')
    el.style.display = 'none'
  }
  if (!header.querySelector('[data-xt-divider]')) {
    const divider = header.ownerDocument.createElement('div')
    divider.setAttribute('data-xt-divider', '')
    divider.className = 'absolute inset-0 flex items-center'
    divider.style.display = 'none'
    divider.innerHTML = '<hr class="w-full border-t border-ink-gray-3">'
    header.appendChild(divider)
  }
  return header
}

function tagCollapsibleLabel(el) {
  el.setAttribute(
    'data-xt-label',
    el.classList.contains('ml-2') ? 'margin' : '',
  )
}

export function setLabelCollapsed(el, collapsed) {
  const animatesMargin = el.getAttribute('data-xt-label') === 'margin'
  if (collapsed) {
    if (animatesMargin) el.classList.replace('ml-2', 'ml-0')
    el.classList.remove('w-auto', 'opacity-100')
    el.classList.add('w-0', 'overflow-hidden', 'opacity-0')
  } else {
    if (animatesMargin) el.classList.replace('ml-0', 'ml-2')
    el.classList.remove('w-0', 'overflow-hidden', 'opacity-0')
    el.classList.add('w-auto', 'opacity-100')
  }
}

export function isSidebarCollapsed(el) {
  if (!el) return false
  if (el.classList.contains('w-12')) return true
  const inline = el.style?.width
  if (inline) {
    const value = parseFloat(inline)
    if (!Number.isNaN(value)) {
      const px = /rem$/.test(inline) ? value * 16 : value
      return px < 100
    }
  }
  const width = el.getBoundingClientRect().width
  if (!width) return false
  return width < 100
}
