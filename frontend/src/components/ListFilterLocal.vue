<!--
  Filter component that mirrors FCRM's Filter.vue behavior and styling.
  Works in isolated createApp context (no FCRM internal imports).

  API:
    v-model  - filter dict  { fieldname: [operator, value] } or { fieldname: value }
    doctype  - doctype name to fetch filterable fields from API
    docfields - (optional) pre-loaded field meta array; skips API call if provided
-->
<template>
  <Popover placement="bottom-end">
    <template #target="{ togglePopover, close }">
      <div class="flex items-center">
        <Button
          :label="__('Filter')"
          :class="filterCount ? 'rounded-r-none' : ''"
          @click="togglePopover()"
        >
          <template #prefix>
            <svg
              width="16"
              height="17"
              viewBox="0 0 16 17"
              fill="none"
              class="h-4"
            >
              <path
                d="M2 4.5H14"
                stroke="currentColor"
                stroke-miterlimit="10"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M4 8.5H12"
                stroke="currentColor"
                stroke-miterlimit="10"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path
                d="M6.5 12.5H9.5"
                stroke="currentColor"
                stroke-miterlimit="10"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </template>
          <template v-if="filterCount" #suffix>
            <div
              class="flex h-5 w-5 items-center justify-center rounded-[5px] bg-surface-base pt-px text-xs-medium text-ink-gray-8 shadow-sm"
            >
              {{ filterCount }}
            </div>
          </template>
        </Button>
        <Button
          v-if="filterCount"
          class="rounded-l-none border-l"
          icon="x"
          @click.stop="clearAllFilters(close)"
        />
      </div>
    </template>
    <template #body="{ close }">
      <div
        class="my-2 min-w-40 rounded-lg bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5 focus:outline-none"
      >
        <div class="min-w-72 p-2 sm:min-w-[400px]">
          <!-- Active filters -->
          <template v-if="filterList.length">
            <div
              v-for="(f, i) in filterList"
              :key="i"
              class="mb-3 flex items-center justify-between gap-2"
            >
              <div class="flex flex-1 items-center gap-2">
                <div class="w-13 pl-2 text-end text-base text-ink-gray-5">
                  {{ i === 0 ? __('Where') : __('And') }}
                </div>
                <div class="!min-w-[140px]">
                  <Autocomplete
                    :modelValue="f.field.fieldname"
                    :options="fieldOptionsFor(i)"
                    :placeholder="__('Filter by...')"
                    @change="(e) => updateFilterField(e, i)"
                  />
                </div>
                <div>
                  <FormControl
                    v-model="f.operator"
                    type="select"
                    :options="getOperators(f.field.fieldtype)"
                    :placeholder="__('Equals')"
                    @update:modelValue="() => onOperatorChange(f)"
                  />
                </div>
                <div class="!min-w-[140px]">
                  <!-- Select / Check -->
                  <FormControl
                    v-if="f.operator === 'is'"
                    type="select"
                    :modelValue="f.value"
                    :options="[
                      { label: 'Set', value: 'set' },
                      { label: 'Not Set', value: 'not set' },
                    ]"
                    @update:modelValue="(v) => onValueChange(v, f)"
                  />
                  <FormControl
                    v-else-if="isSelectOrCheck(f.field.fieldtype)"
                    type="select"
                    :modelValue="f.value"
                    :options="getSelectOptions(f.field)"
                    @update:modelValue="(v) => onValueChange(v, f)"
                  />
                  <!-- Number -->
                  <FormControl
                    v-else-if="typeNumber.includes(f.field.fieldtype)"
                    type="number"
                    :modelValue="f.value"
                    :placeholder="__('1000')"
                    @update:modelValue="(v) => onValueChange(v, f)"
                  />
                  <!-- Default text -->
                  <FormControl
                    v-else
                    type="text"
                    :modelValue="f.value"
                    :placeholder="getPlaceholder(f)"
                    @update:modelValue="(v) => onValueChange(v, f)"
                  />
                </div>
              </div>
              <Button variant="ghost" icon="x" @click="removeFilter(i)" />
            </div>
          </template>

          <!-- Empty state -->
          <div
            v-else
            class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5"
          >
            {{ __('Empty - Choose a field to filter by') }}
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between gap-2">
            <Autocomplete
              :modelValue="null"
              :options="fieldOptionsFor(-1)"
              :placeholder="__('Filter by...')"
              @change="(e) => addFilter(e)"
            >
              <template #target="{ togglePopover }">
                <Button
                  class="!text-ink-gray-5"
                  variant="ghost"
                  :label="__('Add Filter')"
                  iconLeft="plus"
                  @click="togglePopover()"
                />
              </template>
            </Autocomplete>
            <Button
              v-if="filterList.length"
              class="!text-ink-gray-5"
              variant="ghost"
              :label="__('Clear All Filters')"
              @click="clearAllFilters(close)"
            />
          </div>
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Autocomplete, FormControl, Popover, Button } from 'frappe-ui'

const __ =
  window.__ ||
  ((s, r) => (r ? s.replace(/\{(\d+)\}/g, (_, i) => r[i] ?? _) : s))

const typeCheck = ['Check']
const typeLink = ['Link', 'Dynamic Link']
const typeNumber = ['Float', 'Int', 'Currency', 'Percent']
const typeSelect = ['Select']
const typeString = ['Data', 'Long Text', 'Small Text', 'Text Editor', 'Text']
const typeDate = ['Date', 'Datetime']

const emits = defineEmits(['update:modelValue'])
const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  docfields: { type: Array, default: () => [] },
  doctype: { type: String, default: '' },
})

// ── Field meta (from props or API) ──────────────────────────────────────────
const fieldsFromApi = ref([])

const allFields = computed(() => {
  if (props.docfields.length) return props.docfields
  return fieldsFromApi.value
})

onMounted(() => {
  if (!props.docfields.length && props.doctype) fetchFields()
})

watch(
  () => props.doctype,
  (dt) => {
    if (dt && !props.docfields.length) fetchFields()
  },
)

function csrf() {
  return (
    window.csrf_token ||
    window.frappe?.csrf_token ||
    window.boot?.csrf_token ||
    ''
  )
}

async function fetchFields() {
  if (!props.doctype) return
  try {
    // Try CRM API first (returns richer field meta)
    const res = await fetch('/api/method/crm.api.doc.get_filterable_fields', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': csrf(),
        Accept: 'application/json',
      },
      body: JSON.stringify({ doctype: props.doctype }),
    })
    const data = await res.json()
    if (Array.isArray(data.message)) {
      fieldsFromApi.value = data.message
      return
    }
  } catch {
    /* fallback below */
  }
  // Fallback: build from DocType meta
  try {
    const res2 = await fetch('/api/method/frappe.client.get', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-Frappe-CSRF-Token': csrf(),
        Accept: 'application/json',
      },
      body: JSON.stringify({ doctype: 'DocType', name: props.doctype }),
    })
    const meta = await res2.json()
    const fields = (meta.message?.fields || []).filter(
      (f) =>
        !f.hidden &&
        !f.is_virtual &&
        (typeCheck.includes(f.fieldtype) ||
          typeLink.includes(f.fieldtype) ||
          typeNumber.includes(f.fieldtype) ||
          typeSelect.includes(f.fieldtype) ||
          typeString.includes(f.fieldtype) ||
          typeDate.includes(f.fieldtype)),
    )
    fieldsFromApi.value = fields
  } catch {
    /* silent */
  }
}

// ── Filter state ────────────────────────────────────────────────────────────
const filterList = ref([])

const filterCount = computed(() => filterList.value.length)

// Sync from external modelValue → internal filterList
watch(
  () => props.modelValue,
  (val) => {
    if (!val || !Object.keys(val).length) {
      filterList.value = []
      return
    }
    const newList = []
    for (const [key, rawValue] of Object.entries(val)) {
      const field = allFields.value.find((f) => f.fieldname === key) || {
        fieldname: key,
        fieldtype: 'Data',
        label: key,
        options: '',
      }
      let operator, value
      if (Array.isArray(rawValue) && rawValue.length >= 2) {
        const reverseMap = {
          is: 'is',
          '=': 'equals',
          '!=': 'not equals',
          LIKE: 'like',
          'NOT LIKE': 'not like',
          '>': '>',
          '<': '<',
          '>=': '>=',
          '<=': '<=',
          in: 'in',
          'not in': 'not in',
          between: 'between',
          timespan: 'timespan',
        }
        operator = reverseMap[rawValue[0]] || rawValue[0]
        value = rawValue[1]
      } else {
        value = rawValue
        operator = 'equals'
        if (field.fieldtype === 'Check') {
          value = rawValue ? 'Yes' : 'No'
        }
      }
      newList.push({ field, fieldname: key, operator, value })
    }
    filterList.value = newList
  },
  { immediate: true, deep: true },
)

// ── Available fields (excluding already-used) ───────────────────────────────
function fieldOptionsFor(currentIndex) {
  // Include the current row's own field so Autocomplete can resolve its label,
  // but exclude fields used by OTHER rows.
  const usedNames = new Set()
  filterList.value.forEach((f, i) => {
    if (i !== currentIndex) usedNames.add(f.fieldname)
  })
  return allFields.value
    .filter((f) => !usedNames.has(f.fieldname))
    .map((f) => ({
      label: f.label || f.fieldname,
      value: f.fieldname,
      fieldname: f.fieldname,
      fieldtype: f.fieldtype,
      options: f.options,
    }))
}

// ── Operators (matches FCRM Filter.vue) ─────────────────────────────────────
function getOperators(fieldtype) {
  const opts = []
  if (typeString.includes(fieldtype)) {
    opts.push(
      { label: __('Equals'), value: 'equals' },
      { label: __('Not equals'), value: 'not equals' },
      { label: __('Like'), value: 'like' },
      { label: __('Not like'), value: 'not like' },
      { label: __('Is'), value: 'is' },
    )
  }
  if (typeNumber.includes(fieldtype)) {
    opts.push(
      { label: __('Equals'), value: 'equals' },
      { label: __('Not equals'), value: 'not equals' },
      { label: __('<'), value: '<' },
      { label: __('>'), value: '>' },
      { label: __('<='), value: '<=' },
      { label: __('>='), value: '>=' },
      { label: __('Is'), value: 'is' },
    )
  }
  if (typeSelect.includes(fieldtype)) {
    opts.push(
      { label: __('Equals'), value: 'equals' },
      { label: __('Not equals'), value: 'not equals' },
      { label: __('Is'), value: 'is' },
    )
  }
  if (typeLink.includes(fieldtype)) {
    opts.push(
      { label: __('Equals'), value: 'equals' },
      { label: __('Not equals'), value: 'not equals' },
      { label: __('Like'), value: 'like' },
      { label: __('Not like'), value: 'not like' },
      { label: __('Is'), value: 'is' },
    )
  }
  if (typeCheck.includes(fieldtype)) {
    opts.push({ label: __('Equals'), value: 'equals' })
  }
  if (typeDate.includes(fieldtype)) {
    opts.push(
      { label: __('Equals'), value: 'equals' },
      { label: __('Not equals'), value: 'not equals' },
      { label: __('Is'), value: 'is' },
      { label: __('>'), value: '>' },
      { label: __('<'), value: '<' },
    )
  }
  if (!opts.length) {
    opts.push(
      { label: __('Equals'), value: 'equals' },
      { label: __('Like'), value: 'like' },
      { label: __('Is'), value: 'is' },
    )
  }
  return opts
}

// ── Value helpers ───────────────────────────────────────────────────────────
function isSelectOrCheck(fieldtype) {
  return typeSelect.includes(fieldtype) || typeCheck.includes(fieldtype)
}

function getSelectOptions(field) {
  if (typeCheck.includes(field.fieldtype)) {
    return [
      { label: 'Yes', value: 'Yes' },
      { label: 'No', value: 'No' },
    ]
  }
  return (field.options || '')
    .split('\n')
    .filter(Boolean)
    .map((v) => ({ label: v, value: v }))
}

function getDefaultOperator(fieldtype) {
  if (
    typeSelect.includes(fieldtype) ||
    typeCheck.includes(fieldtype) ||
    typeNumber.includes(fieldtype)
  )
    return 'equals'
  return 'like'
}

function getDefaultValue(field) {
  if (typeSelect.includes(field.fieldtype))
    return (field.options || '').split('\n').filter(Boolean)[0] || ''
  if (typeCheck.includes(field.fieldtype)) return 'Yes'
  return ''
}

function getPlaceholder(f) {
  if (['like', 'not like'].includes(f.operator)) return __('%John%')
  if (typeLink.includes(f.field.fieldtype)) return __('Select a value')
  return __('Enter value')
}

// ── Mutations ───────────────────────────────────────────────────────────────
function addFilter(data) {
  if (!data?.fieldname) return
  const field =
    allFields.value.find((f) => f.fieldname === data.fieldname) || data
  filterList.value.push({
    field,
    fieldname: data.fieldname,
    operator: getDefaultOperator(field.fieldtype),
    value: getDefaultValue(field),
  })
  apply()
}

function updateFilterField(data, index) {
  if (!data?.fieldname) return
  const field =
    allFields.value.find((f) => f.fieldname === data.fieldname) || data
  filterList.value.splice(index, 1, {
    field,
    fieldname: data.fieldname,
    operator: getDefaultOperator(field.fieldtype),
    value: getDefaultValue(field),
  })
  apply()
}

function removeFilter(index) {
  filterList.value.splice(index, 1)
  apply()
}

function clearAllFilters(closeFn) {
  filterList.value = []
  apply()
  closeFn?.()
}

function onOperatorChange(f) {
  f.value = getDefaultValue(f.field)
  if (f.operator === 'is') f.value = 'set'
  apply()
}

function onValueChange(value, f) {
  f.value = value?.target ? value.target.value : value?.value ?? value
  apply()
}

// ── Apply: convert internal state → emit modelValue ─────────────────────────
// Uses same operatorMap as FCRM's Filter.vue
const operatorMap = {
  is: 'is',
  equals: '=',
  'not equals': '!=',
  like: 'LIKE',
  'not like': 'NOT LIKE',
  '>': '>',
  '<': '<',
  '>=': '>=',
  '<=': '<=',
  in: 'in',
  'not in': 'not in',
  between: 'between',
  timespan: 'timespan',
}

function apply() {
  const obj = {}
  for (const f of filterList.value) {
    // Transform like values to include %
    let value = f.value
    if (
      (f.operator === 'like' || f.operator === 'not like') &&
      typeof value === 'string' &&
      !value.includes('%')
    ) {
      value = `%${value}%`
    }

    if (['equals', '='].includes(f.operator)) {
      obj[f.fieldname] = value === 'Yes' ? true : value === 'No' ? false : value
    } else {
      obj[f.fieldname] = [operatorMap[f.operator] || f.operator, value]
    }
  }
  emits('update:modelValue', obj)
}
</script>
