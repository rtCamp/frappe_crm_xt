<template>
  <!-- Plain overlay — component is mounted directly to body by InjectedEventsTab -->
  <div
    class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/20 dark:bg-black/50 px-4 py-4"
    style="position: fixed; inset: 0; z-index: 9999"
    @click.self="emit('close')"
  >
    <div
      class="relative w-full max-w-xl overflow-hidden rounded-xl bg-surface-modal text-start shadow-xl"
    >
      <div class="bg-surface-modal px-4 pb-6 pt-5 sm:px-6">
        <!-- Header -->
        <div class="mb-6 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <h3 class="text-2xl font-semibold leading-6 text-ink-gray-9">
              {{
                mode === 'edit'
                  ? __('Edit an Event')
                  : mode === 'duplicate'
                    ? __('Duplicate an Event')
                    : __('Create an Event')
              }}
            </h3>
          </div>
          <div class="flex gap-1">
            <Button v-if="mode === 'edit'" variant="ghost" @click="deleteEvent">
              <template #icon>
                <FeatherIcon name="trash-2" class="h-4 w-4 text-ink-gray-9" />
              </template>
            </Button>
            <Button
              v-if="mode === 'edit'"
              variant="ghost"
              @click="duplicateEvent"
            >
              <template #icon>
                <FeatherIcon name="copy" class="h-4 w-4 text-ink-gray-9" />
              </template>
            </Button>
            <Button variant="ghost" @click="emit('close')">
              <template #icon>
                <FeatherIcon name="x" class="h-4 w-4 text-ink-gray-9" />
              </template>
            </Button>
          </div>
        </div>

        <!-- Form fields -->
        <div class="flex flex-col gap-4">
          <div class="flex items-center">
            <div class="text-base text-ink-gray-7 w-3/12">
              {{ __('Title') }}
            </div>
            <div class="flex gap-1 w-9/12">
              <Dropdown :options="colors">
                <div
                  class="flex items-center justify-center size-7 shrink-0 border border-outline-gray-2 bg-surface-white hover:border-outline-gray-3 hover:shadow-sm rounded cursor-pointer"
                >
                  <div
                    class="size-2.5 rounded-full"
                    :style="{ backgroundColor: _event.color || '#30A66D' }"
                  />
                </div>
              </Dropdown>
              <TextInput
                ref="titleRef"
                v-model="_event.title"
                class="w-full"
                size="sm"
                :placeholder="__('Call with John Doe')"
                variant="outline"
                required
              />
            </div>
          </div>

          <div class="flex items-center">
            <div class="text-base text-ink-gray-7 w-3/12">
              {{ __('All Day') }}
            </div>
            <Switch v-model="_event.isFullDay" />
          </div>

          <div class="border-t border-outline-gray-1" />

          <div class="flex items-center">
            <div class="text-base text-ink-gray-7 w-3/12">
              {{ __('Date & Time') }}
            </div>
            <div class="flex gap-2 w-9/12">
              <DatePicker
                :class="[_event.isFullDay ? 'w-full' : 'w-[158px]']"
                variant="outline"
                :value="_event.fromDate"
                :format="'MMM D, YYYY'"
                :placeholder="__('May 1, 2025')"
                :clearable="false"
                @update:modelValue="(d) => updateDate(d)"
              >
                <template #suffix="{ togglePopover }">
                  <FeatherIcon
                    name="chevron-down"
                    class="h-4 w-4 cursor-pointer"
                    @click="togglePopover"
                  />
                </template>
              </DatePicker>
              <TimePicker
                v-if="!_event.isFullDay"
                class="max-w-[112px]"
                variant="outline"
                :modelValue="_event.fromTime"
                :placeholder="__('Start Time')"
                @update:modelValue="(t) => updateTime(t, true)"
              />
              <TimePicker
                v-if="!_event.isFullDay"
                class="max-w-[112px]"
                variant="outline"
                :modelValue="_event.toTime"
                :options="toOptions"
                :placeholder="__('End Time')"
                placement="bottom-end"
                @update:modelValue="(t) => updateTime(t)"
              />
            </div>
          </div>

          <div class="flex items-start">
            <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
              {{ __('Attendees') }}
            </div>
            <div class="w-9/12">
              <Attendee
                v-model="peoples"
                :validate="validateEmail"
                :error-message="
                  (v) => __('{0} is an invalid email address', [v])
                "
              />
            </div>
          </div>

          <div class="flex items-start">
            <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
              {{ __('Visibility') }}
            </div>
            <div class="w-9/12">
              <FormControl
                v-model="_event.eventType"
                class="w-full"
                type="select"
                :options="[
                  { label: __('Private'), value: 'Private' },
                  { label: __('Public'), value: 'Public' },
                ]"
                variant="outline"
                :placeholder="__('Private or Public')"
              />
            </div>
          </div>

          <div class="flex items-start">
            <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
              {{ __('Location') }}
            </div>
            <div class="w-9/12">
              <TextInput
                v-model="_event.location"
                class="w-full"
                size="sm"
                variant="outline"
                :placeholder="__('Add Location')"
              />
            </div>
          </div>

          <div class="flex">
            <div class="mt-2 text-base text-ink-gray-7 w-3/12">
              {{ __('Description') }}
            </div>
            <div class="w-9/12">
              <TextEditor
                editor-class="!prose-sm overflow-auto min-h-[80px] max-h-80 py-1.5 px-2 rounded border border-outline-gray-2 placeholder-ink-gray-4 hover:border-outline-gray-3 hover:shadow-sm focus:bg-surface-white focus:border-outline-gray-4 focus:shadow-sm focus:ring-0 focus-visible:ring-2 focus-visible:ring-outline-gray-3 text-ink-gray-8 transition-colors"
                :bubbleMenu="true"
                :content="_event.description"
                :placeholder="__('Add Description.')"
                @change="(val) => (_event.description = val)"
              />
            </div>
          </div>

          <div class="border-t border-outline-gray-1" />

          <div class="flex">
            <div class="mt-1.5 text-base text-ink-gray-7 w-3/12">
              {{ __('Notifications') }}
            </div>
            <div class="w-9/12">
              <EventNotifications
                v-model="_event.notifications"
                :isAllDay="_event.isFullDay"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-4 pb-7 pt-4 sm:px-6">
        <div class="flex w-full items-center justify-between">
          <div>
            <ErrorMessage v-if="error" :message="__(error)" />
          </div>
          <div class="flex gap-2 justify-end">
            <Button :label="__('Cancel')" @click="emit('close')" />
            <Button
              variant="solid"
              :label="
                mode === 'edit'
                  ? __('Update')
                  : mode === 'duplicate'
                    ? __('Duplicate')
                    : __('Create')
              "
              :disabled="!dirty"
              :loading="saving"
              @click="update"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import EventNotifications from './EventNotifications.vue'
import Attendee from './Attendee.vue'
import {
  Switch,
  TextEditor,
  ErrorMessage,
  DatePicker,
  TimePicker,
  dayjs,
  Dropdown,
  TextInput,
  FormControl,
  FeatherIcon,
  Button,
} from 'frappe-ui'
import { validateEmail } from '../utils'
import {
  normalizeParticipants,
  buildEndTimeOptions,
  computeAutoToTime,
  validateTimeRange,
} from '../composables/event'
import { CalendarColorMap as colorMap } from 'frappe-ui'
import { onMounted, ref, computed, h } from 'vue'

const __ =
  window.__ ||
  ((s, r) => (r ? s.replace(/\{(\d+)\}/g, (_, i) => r[i] ?? _) : s))

const props = defineProps({
  event: { type: Object, default: () => ({}) },
  doctype: { type: String, default: '' },
  docname: { type: String, default: '' },
})

const emit = defineEmits(['close', 'saved', 'deleted'])

const titleRef = ref(null)
const saving = ref(false)
const error = ref(null)

const mode = computed(() =>
  _event.value.id === 'duplicate'
    ? 'duplicate'
    : _event.value.id
      ? 'edit'
      : 'create',
)

const oldEvent = ref({})
const _event = ref({
  title: '',
  description: '',
  fromDate: '',
  toDate: '',
  fromTime: '',
  toTime: '',
  isFullDay: false,
  eventType: 'Public',
  location: '',
  color: '#30A66D',
  referenceDoctype: '',
  referenceDocname: '',
  event_participants: [],
  notifications: [],
})

const dirty = computed(
  () => JSON.stringify(_event.value) !== JSON.stringify(oldEvent.value),
)

const peoples = computed({
  get() {
    return _event.value.event_participants || []
  },
  set(list) {
    _event.value.event_participants = normalizeParticipants(list)
  },
})

const toOptions = computed(() => buildEndTimeOptions(_event.value.fromTime))

const colors = Object.keys(colorMap).map((c) => ({
  label: c.charAt(0).toUpperCase() + c.slice(1),
  value: colorMap[c].color,
  icon: h('div', {
    class: '!size-2.5 rounded-full',
    style: { backgroundColor: colorMap[c].color },
  }),
  onClick: () => (_event.value.color = colorMap[c].color),
}))

onMounted(() => {
  if (props.event) {
    let start = dayjs(props.event.starts_on)
    let end = dayjs(props.event.ends_on)
    if (!props.event.name) {
      start = dayjs()
      end = dayjs().add(1, 'hour')
    }
    _event.value = {
      id: props.event.name || '',
      title: props.event.subject || '',
      description: props.event.description || '',
      fromDate: start.format('YYYY-MM-DD'),
      toDate: end.format('YYYY-MM-DD'),
      fromTime: start.format('HH:mm'),
      toTime: end.format('HH:mm'),
      isFullDay: !!props.event.all_day,
      eventType: props.event.event_type || 'Public',
      location: props.event.location || '',
      color: props.event.color || '#30A66D',
      referenceDoctype: props.event.reference_doctype || '',
      referenceDocname: props.event.reference_docname || '',
      event_participants: props.event.event_participants || [],
      notifications: props.event.notifications || [],
    }
    oldEvent.value = JSON.parse(JSON.stringify(_event.value))
    setTimeout(() => titleRef.value?.el?.focus(), 100)
  }
})

function updateDate(d) {
  _event.value.fromDate = d
  _event.value.toDate = d
}

function updateTime(t, fromTime = false) {
  error.value = null
  const prevTo = _event.value.toTime
  if (fromTime) {
    _event.value.fromTime = t
    if (!_event.value.toTime || _event.value.toTime <= t) {
      _event.value.toTime = computeAutoToTime(t)
    }
  } else {
    _event.value.toTime = t
  }
  const { valid, error: err } = validateTimeRange({
    fromDate: _event.value.fromDate,
    fromTime: _event.value.fromTime,
    toTime: _event.value.toTime,
    isFullDay: _event.value.isFullDay,
  })
  if (!valid) {
    error.value = err
    _event.value.toTime = prevTo
  }
}

function update() {
  error.value = null
  if (!_event.value.title) {
    error.value = __('Title is required')
    titleRef.value?.el?.focus()
    return
  }
  const { valid, error: err } = validateTimeRange({
    fromDate: _event.value.fromDate,
    fromTime: _event.value.fromTime,
    toTime: _event.value.toTime,
    isFullDay: _event.value.isFullDay,
  })
  if (!valid) {
    error.value = err
    return
  }

  if (_event.value.id && _event.value.id !== 'duplicate') {
    updateEvent()
  } else {
    createEvent()
  }
}

function createEvent() {
  saving.value = true
  error.value = null
  const currentUser =
    window.frappe?.boot?.user || window.frappe?.session?.user || ''
  const participants = [
    {
      doctype: 'Event Participants',
      reference_doctype: props.doctype,
      reference_docname: props.docname,
    },
  ]
  if (currentUser && currentUser !== 'Administrator') {
    participants.push({
      doctype: 'Event Participants',
      reference_doctype: 'User',
      reference_docname: currentUser,
      email: currentUser,
    })
  }
  ;(_event.value.event_participants || []).forEach((p) => {
    if (p.email && !participants.some((ep) => ep.email === p.email)) {
      participants.push({ doctype: 'Event Participants', email: p.email })
    }
  })
  apiFetch('frappe.client.insert', {
    doc: {
      doctype: 'Event',
      subject: _event.value.title,
      description: _event.value.description,
      starts_on: _event.value.fromDate + ' ' + _event.value.fromTime,
      ends_on: _event.value.toDate + ' ' + _event.value.toTime,
      all_day: _event.value.isFullDay || false,
      event_type: _event.value.eventType,
      location: _event.value.location || '',
      color: _event.value.color,
      reference_doctype: props.doctype,
      reference_docname: props.docname,
      event_participants: participants,
      notifications: _event.value.notifications,
    },
  })
    .then(() => {
      emit('saved')
    })
    .catch((e) => {
      error.value = e?.message || 'Failed to create event'
    })
    .finally(() => {
      saving.value = false
    })
}

function updateEvent() {
  if (!_event.value.id) {
    error.value = __('Event ID is required')
    return
  }
  saving.value = true
  error.value = null
  apiFetch('frappe.client.get', { doctype: 'Event', name: _event.value.id })
    .then((doc) => {
      const currentUser = window.frappe?.session?.user || ''
      const keepEmails = new Set([
        props.docname,
        currentUser,
        ...(_event.value.event_participants || [])
          .map((p) => p.email)
          .filter(Boolean),
      ])
      const existingParts = (doc.event_participants || []).filter(
        (p) => keepEmails.has(p.email) || keepEmails.has(p.reference_docname),
      )
      ;(_event.value.event_participants || []).forEach((p) => {
        if (p.email && !existingParts.some((ep) => ep.email === p.email)) {
          existingParts.push({ doctype: 'Event Participants', email: p.email })
        }
      })
      Object.assign(doc, {
        subject: _event.value.title,
        description: _event.value.description,
        starts_on: _event.value.fromDate + ' ' + _event.value.fromTime,
        ends_on: _event.value.toDate + ' ' + _event.value.toTime,
        all_day: _event.value.isFullDay,
        event_type: _event.value.eventType,
        location: _event.value.location || '',
        color: _event.value.color,
        event_participants: existingParts,
        notifications: _event.value.notifications,
      })
      return apiFetch('frappe.client.save', { doc })
    })
    .then(() => {
      emit('saved')
    })
    .catch((e) => {
      error.value = e?.message || 'Failed to update event'
    })
    .finally(() => {
      saving.value = false
    })
}

function duplicateEvent() {
  if (!_event.value.id) return
  _event.value.id = 'duplicate'
  _event.value.title = _event.value.title + ' (Copy)'
  setTimeout(() => titleRef.value?.el?.focus(), 100)
}

function deleteEvent() {
  if (!_event.value.id) return
  if (!window.confirm(__('Are you sure you want to delete this event?'))) return
  saving.value = true
  apiFetch('frappe.client.delete', { doctype: 'Event', name: _event.value.id })
    .then(() => {
      emit('deleted')
    })
    .catch((e) => {
      error.value = e?.message || 'Failed to delete event'
    })
    .finally(() => {
      saving.value = false
    })
}

function csrf() {
  return window.csrf_token || window.boot?.csrf_token || ''
}

async function apiFetch(method, params = {}) {
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': csrf(),
      Accept: 'application/json',
    },
    body: JSON.stringify(params),
  })
  const data = await res.json()
  if (data.exc) throw new Error(data._server_messages || data.exc)
  return data.message
}
</script>
