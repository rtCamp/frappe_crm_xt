<!--
  Drop-in replacement for frappe-ui's ListFilter that uses frappe-ui's own
  Popover (reka-ui based, works in separate createApp context) instead of
  ListFilter/NestedPopover (headlessui based, breaks outside the main app).

  API is identical to frappe-ui's ListFilter:
    v-model  - filter dict  { fieldname: [operator, value] }
    docfields - array of field meta objects from DocType meta
-->
<template>
  <Popover>
    <template #target="{ togglePopover }">
      <Button label="Filter" @click="togglePopover()">
        <template #prefix>
          <!-- inline filter icon (same SVG as FilterIcon.vue) -->
          <svg width="16" height="17" viewBox="0 0 16 17" fill="none" class="h-4">
            <path d="M2 4.5H14" stroke="currentColor" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4 8.5H12" stroke="currentColor" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M6.5 12.5H9.5" stroke="currentColor" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </template>
        <template v-if="filters.length" #suffix>
          <div
            class="flex h-5 w-5 items-center justify-center rounded bg-surface-gray-7 pt-[1px] text-2xs font-medium text-ink-white"
          >
            {{ filters.length }}
          </div>
        </template>
      </Button>
    </template>
    <template #body="{ close }">
      <div class="my-2 rounded-lg border border-gray-100 bg-surface-white shadow-xl">
        <div class="min-w-[400px] p-2">
          <!-- Active filters -->
          <div
            v-for="(filter, i) in filters"
            :key="i"
            class="mb-3 flex items-center justify-between gap-2"
          >
            <div class="flex flex-1 items-center gap-2">
              <div class="w-13 flex-shrink-0 pl-2 text-end text-base text-ink-gray-5">
                {{ i === 0 ? 'Where' : 'And' }}
              </div>
              <div class="min-w-[140px] flex-1">
                <Autocomplete
                  :value="filter.fieldname"
                  :options="fields"
                  @change="filter.fieldname = $event.value"
                  placeholder="Filter by..."
                />
              </div>
              <div class="min-w-[140px] flex-shrink-0">
                <FormControl
                  type="select"
                  :modelValue="filter.operator"
                  @update:modelValue="filter.operator = $event.value || $event"
                  :options="getOperators(filter.field?.fieldtype)"
                  placeholder="Operator"
                />
              </div>
              <div class="min-w-[140px] flex-1">
                <component
                  :is="getValueSelector(filter.field?.fieldtype, filter.field?.options)"
                  v-model="filter.value"
                  placeholder="Value"
                />
              </div>
            </div>
            <Button variant="ghost" icon="x" @click="removeFilter(i)" />
          </div>

          <!-- Empty state -->
          <div v-if="!filters.length" class="mb-3 flex h-7 items-center px-3 text-sm text-ink-gray-5">
            Empty — choose a field to filter by
          </div>

          <!-- Footer row: Add filter + Apply + Clear -->
          <div class="flex items-center justify-between gap-2">
            <Autocomplete
              value=""
              :options="fields"
              @change="(field) => addFilter(field.value)"
              placeholder="Filter by..."
            >
              <template #target="{ togglePopover }">
                <Button class="!text-ink-gray-5" variant="ghost" @click="togglePopover()" label="Add filter">
                  <template #prefix><FeatherIcon name="plus" class="h-4" /></template>
                </Button>
              </template>
            </Autocomplete>
            <div class="flex gap-2">
              <Button
                v-if="filters.length"
                variant="solid"
                size="sm"
                label="Apply"
                @click="applyFilters(); close()"
              />
              <Button
                v-if="filters.length"
                class="!text-ink-gray-5"
                variant="ghost"
                label="Clear all"
                @click="clearFilters()"
              />
            </div>
          </div>
        </div>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import {
  Autocomplete, FeatherIcon, FormControl, Popover, Button,
} from 'frappe-ui'
// SearchComplete is not exported by frappe-ui's package.json exports map.
// For Link fields we fall back to a plain text input (sufficient for filtering).
const SearchComplete = null

const typeCheck  = ['Check']
const typeLink   = ['Link']
const typeNumber = ['Float', 'Int']
const typeSelect = ['Select']
const typeString = ['Data','Long Text','Small Text','Text Editor','Text','JSON','Code']

const emits = defineEmits(['update:modelValue'])
const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  docfields:  { type: Array,  default: () => [] },
})

const fields = computed(() =>
  props.docfields
    .filter(f => !f.is_virtual && (
      typeCheck.includes(f.fieldtype) || typeLink.includes(f.fieldtype) ||
      typeNumber.includes(f.fieldtype) || typeSelect.includes(f.fieldtype) ||
      typeString.includes(f.fieldtype)
    ))
    .map(f => ({ label: f.label, value: f.fieldname, description: f.fieldtype, ...f }))
)

// Local mutable copy for editing before applying
const localFilters = ref([])

const filters = computed({
  get: () => {
    return Object.entries(props.modelValue).map(([fieldname, [operator, value]]) => {
      const field = getField(fieldname)
      return { fieldname, operator, value, field }
    })
  },
  set: (value) => emits('update:modelValue', makeFiltersDict(value)),
})

function getField(fieldname) {
  return fields.value.find(f => f.fieldname === fieldname) || { fieldname, fieldtype: 'Data' }
}

function makeFiltersDict(list) {
  return list.reduce((acc, f) => {
    acc[f.fieldname] = [f.operator, f.value]
    return acc
  }, {})
}

function getOperators(fieldtype) {
  const opts = []
  if (typeString.includes(fieldtype) || typeLink.includes(fieldtype))
    opts.push({ label: 'Equals', value: '=' }, { label: 'Not Equals', value: '!=' },
               { label: 'Like', value: 'like' }, { label: 'Not Like', value: 'not like' })
  if (typeNumber.includes(fieldtype))
    opts.push({ label: '<', value: '<' }, { label: '>', value: '>' },
               { label: '<=', value: '<=' }, { label: '>=', value: '>=' },
               { label: 'Equals', value: '=' }, { label: 'Not Equals', value: '!=' })
  if (typeSelect.includes(fieldtype))
    opts.push({ label: 'Equals', value: '=' }, { label: 'Not Equals', value: '!=' })
  if (typeCheck.includes(fieldtype))
    opts.push({ label: 'Equals', value: '=' })
  return opts.length ? opts : [{ label: 'Equals', value: '=' }, { label: 'Like', value: 'like' }]
}

function getDefaultOperator(fieldtype) {
  if (['Select','Link','Check','Float','Int'].includes(fieldtype)) return '='
  return 'like'
}

function getValueSelector(fieldtype, options) {
  if (typeSelect.includes(fieldtype) || typeCheck.includes(fieldtype)) {
    const _options = fieldtype === 'Check' ? ['Yes', 'No'] : (options || '').split('\n')
    return h(FormControl, { type: 'select', options: _options })
  }
  return h(FormControl, { type: 'text' })
}

function getDefaultValue(field) {
  if (typeSelect.includes(field.fieldtype)) return (field.options || '').split('\n')[0] || ''
  if (typeCheck.includes(field.fieldtype)) return 'Yes'
  return ''
}

function addFilter(fieldname) {
  const field = getField(fieldname)
  const newList = [...filters.value, {
    fieldname,
    operator: getDefaultOperator(field.fieldtype),
    value: getDefaultValue(field),
    field,
  }]
  emits('update:modelValue', makeFiltersDict(newList))
}

function removeFilter(index) {
  const newList = filters.value.filter((_, i) => i !== index)
  emits('update:modelValue', makeFiltersDict(newList))
}

function applyFilters() {
  emits('update:modelValue', makeFiltersDict(filters.value))
}

function clearFilters() {
  emits('update:modelValue', {})
}
</script>
