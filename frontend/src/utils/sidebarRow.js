/**
 * Sidebar row cloning — how we inject nav rows into the CRM's sidebar.
 *
 * These rows used to be hand-written markup that copied FCRM's utility classes,
 * which silently breaks whenever the CRM restyles its sidebar. crm 1.81 rebuilt it
 * on frappe-ui's Sidebar/SidebarItem components, where a row is a
 * `div[data-slot="sidebar-item"]` (h-7) wrapping a link whose icon sits in a
 * `span.grid` — nothing like the `button > div.px-2.py-[7px]` of crm <= 1.74. Our
 * rows then rendered at the wrong height with mis-sized icons, and the anchor
 * lookup (which required a `<button>`) found nothing at all, so no custom items
 * appeared on 1.81.
 *
 * Instead we clone a real row out of the CRM's own sidebar and swap its icon and
 * label: padding, height, hover, focus ring, dark mode and collapse behaviour all
 * come from the host, with no per-version markup to maintain.
 *
 * Kept in its own module so the DOM logic is unit-testable without a browser.
 */

import { getLucideIcon } from '../lucideIcons.js'

// The native row we clone from. "Call Logs" exists in every CRM version we target
// and is never the active row on a Lead/Deal page.
export const ROW_TEMPLATE_LABEL = 'Call Logs'

const _svgInnerCache = {}

/** Inner markup of a lucide icon (everything between the <svg> tags). */
export function lucideIconInner(name) {
  if (_svgInnerCache[name]) return _svgInnerCache[name]
  const inner = getLucideIcon(name)
    .replace(/^[\s\S]*?<svg[^>]*>/, '')
    .replace(/<\/svg>\s*$/, '')
  _svgInnerCache[name] = inner
  return inner
}

/** The CRM's own row element for `labelText`, whatever tag this version uses. */
export function findNativeRow(doc = document, labelText = ROW_TEMPLATE_LABEL) {
  const label = Array.from(doc.querySelectorAll('span')).find(
    (s) => s.textContent.trim() === labelText,
  )
  const row =
    label &&
    (label.closest('[data-slot="sidebar-item"]') ||
      label.closest('button') ||
      label.closest('a'))
  if (row) return row
  // The CRM renders labels through `__()`, so on a non-English site "Call Logs"
  // never matches and we would inject nothing at all. Fall back to the CRM's last
  // own sidebar row: still a valid template, and a sensible anchor to append after.
  const rows = Array.from(
    doc.querySelectorAll('[data-slot="sidebar-item"]'),
  ).filter(
    (el) => !el.classList.contains('crm-xt') && el.querySelector('a, button'),
  )
  return rows.length ? rows[rows.length - 1] : null
}

/**
 * The row's label wrapper — the element the host animates on collapse — and the
 * deepest node inside it that actually carries the text. Found structurally (by
 * those collapse classes, in either state) rather than by matching the template's
 * text, which differs whenever the label is translated or a fallback template is
 * used.
 */
function rowLabelParts(row) {
  const wrapper = row.querySelector('.ml-2, .ml-0, .w-auto, .w-0') || null
  const scope = wrapper || row
  const textEl =
    Array.from(scope.querySelectorAll('*')).find(
      (el) => !el.children.length && el.textContent.trim(),
    ) || (scope.children.length ? null : scope)
  return { wrapper: wrapper || textEl, textEl }
}

/**
 * Swap the row's icon. It is either a lucide CSS class on a <span>
 * (frappe-ui >= 1.x) or an inline <svg> (frappe-ui 0.1.x and crm's own icon
 * components).
 */
export function swapRowIcon(row, icon) {
  const lucideSpan = Array.from(row.querySelectorAll('span')).find((s) =>
    Array.from(s.classList).some((c) => c.startsWith('lucide-')),
  )
  if (lucideSpan) {
    Array.from(lucideSpan.classList)
      .filter((c) => c.startsWith('lucide-'))
      .forEach((c) => lucideSpan.classList.remove(c))
    lucideSpan.classList.add(`lucide-${icon}`)
    return true
  }
  const svg = row.querySelector('svg')
  if (!svg) return false
  // Keep the host's sizing/colour classes, replace only the drawing.
  const doc = row.ownerDocument
  const replacement = doc.createElementNS('http://www.w3.org/2000/svg', 'svg')
  replacement.setAttribute('viewBox', '0 0 24 24')
  replacement.setAttribute('fill', 'none')
  replacement.setAttribute('stroke', 'currentColor')
  replacement.setAttribute('stroke-width', '1.5')
  replacement.setAttribute('stroke-linecap', 'round')
  replacement.setAttribute('stroke-linejoin', 'round')
  replacement.setAttribute('class', svg.getAttribute('class') || 'size-4')
  replacement.innerHTML = lucideIconInner(icon)
  svg.replaceWith(replacement)
  return true
}

/**
 * Normalise a clone to the *expanded* look, whatever state the template was in.
 *
 * The sidebar's collapsed state is persisted, so on a reload-while-collapsed the
 * rows we clone are already in rail form — label wrapper `ml-0 w-0 overflow-hidden
 * opacity-0`, link `justify-center`, icon holder `size-7`. Cloning that verbatim
 * left nothing for syncCollapse() to restore, so expanding the sidebar showed our
 * icons with no labels. Clone → normalise to expanded → let syncCollapse() apply
 * the rail treatment, and both directions work from either starting state.
 */
function normaliseToExpanded(root, labelWrapper) {
  if (labelWrapper) {
    // `ml-0` marks a row whose label slides; a section label has neither.
    const animatesMargin =
      labelWrapper.classList.contains('ml-2') ||
      labelWrapper.classList.contains('ml-0')
    labelWrapper.classList.remove('w-0', 'overflow-hidden', 'opacity-0', 'ml-0')
    labelWrapper.classList.add('w-auto', 'opacity-100')
    if (animatesMargin) labelWrapper.classList.add('ml-2')
  }
  const clickable = root.querySelector('a, button')
  if (clickable?.classList.contains('justify-center')) {
    clickable.classList.remove('justify-center')
    clickable.classList.add('pl-2')
  }
  root.querySelector('span.grid')?.classList.remove('size-7')
}

/** Clone a native row into one of ours, with our icon, label and click handler. */
export function cloneNativeRow(template, { label, icon, onClick, suffix }) {
  const row = template.cloneNode(true)
  row.removeAttribute('id')
  // Marks the elements we own inside the host's DOM.
  row.classList.add('crm-xt')
  // Never inherit the template row's "current page" styling.
  row.setAttribute('data-state', 'inactive')
  row.classList.remove('bg-surface-elevation-3', 'shadow-sm', 'text-ink-gray-8')
  row
    .querySelectorAll('[aria-current]')
    .forEach((el) => el.removeAttribute('aria-current'))
  // A cloned RouterLink would still navigate; keep the element (its classes carry
  // the row layout) but turn it into a plain button.
  row.querySelectorAll('a').forEach((a) => {
    a.removeAttribute('href')
    a.removeAttribute('target')
    a.setAttribute('role', 'button')
  })
  // The template's own aria-label ("Call Logs") would otherwise be announced for
  // our row; the caller's label is set on the row below.
  row
    .querySelectorAll('[aria-label]')
    .forEach((el) => el.setAttribute('aria-label', label))

  const { wrapper: labelWrapper, textEl } = rowLabelParts(row)
  if (textEl) textEl.textContent = label
  if (labelWrapper) {
    // Tag the wrapper the host animates on collapse (it carries `w-auto`, plus
    // `ml-2` on nav rows) so syncCollapse() can hide the text on our static clones.
    normaliseToExpanded(row, labelWrapper)
    tagCollapsibleLabel(labelWrapper)
  }
  if (icon) swapRowIcon(row, icon)
  row.setAttribute('aria-label', label)
  // Collapse hooks for the icon rail. frappe-ui's SidebarItem swaps `pl-2` for
  // `justify-center` on the link and grows the icon holder to `size-7` when the
  // sidebar collapses; our clones are static markup, so syncCollapse() has to do
  // that for them or the icons stay left-hugged instead of centring on the rail.
  const clickableEl = row.querySelector('a, button')
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

/**
 * Clone the CRM's own collapsible-section label (`div[data-slot="sidebar-label"]`,
 * crm >= 1.81) for one of our groups: same chevron, spacing and type scale as the
 * CRM's "Public Views" / "Pinned Views" headers.
 */
export function cloneNativeSectionLabel(template, { label }) {
  const header = template.cloneNode(true)
  header.removeAttribute('id')
  header.classList.add('crm-xt', 'cursor-pointer', 'select-none')
  header.setAttribute('aria-label', label)
  header.setAttribute('aria-expanded', 'false')

  const textEl = Array.from(header.querySelectorAll('*')).find(
    (el) => !el.children.length && el.textContent.trim(),
  )
  if (textEl) {
    textEl.textContent = label
    // Tag the element the CRM animates on collapse (the <h3> carrying `w-auto
    // opacity-100`), never the text span: syncCollapse() adds `ml-2` to whatever it
    // finds, which on the span indents our label out of line with the CRM's own.
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
  // The clone inherits the source section's open/closed rotation; ours starts closed.
  const chevron = Array.from(header.querySelectorAll('span')).find((s) =>
    Array.from(s.classList).some((c) => c.startsWith('lucide-chevron')),
  )
  if (chevron) {
    chevron.classList.add('crm-xt-chevron')
    chevron.classList.remove('rotate-90')
    chevron.style.transform = ''
  }
  // On the collapsed rail frappe-ui's SidebarLabel hides its text and shows a
  // divider rule in its place (that's its `divider` prop). The clone is taken from
  // an expanded section, so that branch is absent and our header would collapse to
  // an empty 28px gap. Add the divider ourselves; syncCollapse() swaps them.
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

/**
 * Tag the element whose text collapses with the sidebar, recording *how* the host
 * animates it: nav rows slide their label (`ml-2 w-auto opacity-100`), while a
 * section label only fades/shrinks its `<h3>` (`w-auto opacity-100`, no margin).
 * Applying the row treatment to a section label adds an `ml-2` the CRM never has,
 * which indents our group header 8px past "Public Views" — so record the mode here
 * and let setLabelCollapsed() honour it.
 */
function tagCollapsibleLabel(el) {
  el.setAttribute(
    'data-xt-label',
    el.classList.contains('ml-2') ? 'margin' : '',
  )
}

/** Show/hide a tagged label for the collapsed rail, per its recorded mode. */
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

/**
 * Is the sidebar collapsed? crm <= 1.74 toggles a `w-12` class; crm >= 1.75 uses
 * frappe-ui's Sidebar, which sets an inline width instead — read that before
 * falling back to measuring, so this works before layout too.
 */
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
  // A zero width means "not laid out yet" (or hidden), not "collapsed" — treat it
  // as expanded so labels are never wrongly hidden before the first paint.
  if (!width) return false
  return width < 100
}
