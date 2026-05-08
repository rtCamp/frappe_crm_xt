<template>
  <Dialog v-model="show" :options="{ size: 'xl' }">
    <!-- ── Header ── -->
    <template #body-header>
      <div class="mb-6 flex items-center justify-between">
        <h3 class="text-2xl font-semibold leading-6 text-ink-gray-9">
          {{
            mode === 'edit'
              ? _t('Edit an event')
              : mode === 'duplicate'
                ? _t('Duplicate an event')
                : _t('Create an event')
          }}
        </h3>
        <div class="flex gap-1">
          <!-- Delete (edit only) -->
          <button
            v-if="mode === 'edit'"
            class="inline-flex items-center justify-center size-7 rounded hover:bg-surface-gray-2 text-ink-gray-9 transition-colors"
            :title="_t('Delete')"
            @click="confirmDelete"
          >
            <svg
              viewBox="0 0 24 24"
              class="h-4 w-4"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6l-1 14H6L5 6" />
              <path d="M10 11v6" />
              <path d="M14 11v6" />
              <path d="M9 6V4h6v2" />
            </svg>
          </button>
          <!-- Duplicate (edit only) -->
          <button
            v-if="mode === 'edit'"
            class="inline-flex items-center justify-center size-7 rounded hover:bg-surface-gray-2 text-ink-gray-9 transition-colors"
            :title="_t('Duplicate')"
            @click="duplicateEvent"
          >
            <svg
              viewBox="0 0 24 24"
              class="h-4 w-4"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
              <path
                d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
              />
            </svg>
          </button>
          <!-- Close -->
          <button
            class="inline-flex items-center justify-center size-7 rounded hover:bg-surface-gray-2 text-ink-gray-9 transition-colors"
            @click="show = false"
          >
            <svg
              viewBox="0 0 24 24"
              class="h-4 w-4"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-linecap="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
      </div>
    </template>

    <!-- ── Body ── -->
    <template #body-content>
      <div class="flex flex-col gap-4">
        <!-- Title + color picker -->
        <div class="flex items-center">
          <div class="text-base text-ink-gray-7 w-3/12">{{ _t('Title') }}</div>
          <div class="flex gap-1 w-9/12">
            <Dropdown :options="colorOptions">
              <div
                class="flex items-center justify-center size-7 shrink-0 border border-outline-gray-2 bg-surface-white hover:border-outline-gray-3 hover:shadow-sm rounded cursor-pointer"
              >
                <div
                  style="
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    flex-shrink: 0;
                  "
                  :style="{ backgroundColor: form.color || '#30A66D' }"
                />
              </div>
            </Dropdown>
            <input
              ref="titleInput"
              v-model="form.title"
              type="text"
              :placeholder="_t('Call with John Doe')"
              class="w-full rounded border border-outline-gray-2 bg-surface-white px-3 py-1.5 text-sm text-ink-gray-9 placeholder-ink-gray-4 focus:border-outline-gray-3 focus:outline-none"
              required
              @keydown.enter.prevent="submit"
            />
          </div>
        </div>

        <!-- All day -->
        <div class="flex items-center">
          <div class="text-base text-ink-gray-7 w-3/12">
            {{ _t('All day') }}
          </div>
          <Switch v-model="form.isFullDay" />
        </div>

        <div class="border-t border-outline-gray-1" />

        <!-- Date & Time -->
        <div class="flex items-center">
          <div class="text-base text-ink-gray-7 w-3/12">
            {{ _t('Date & Time') }}
          </div>
          <div class="flex gap-2 w-9/12 flex-wrap">
            <DatePicker
              :class="form.isFullDay ? 'flex-1' : 'w-[158px]'"
              variant="outline"
              :value="form.fromDate"
              :format="'MMM D, YYYY'"
              :placeholder="_t('May 1, 2025')"
              :clearable="false"
              @update:modelValue="(d) => updateDate(d)"
            >
              <template #suffix="{ togglePopover }">
                <svg
                  viewBox="0 0 24 24"
                  class="h-4 w-4 cursor-pointer text-ink-gray-5"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  @click="togglePopover"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </template>
            </DatePicker>
            <TimePicker
              v-if="!form.isFullDay"
              class="max-w-[112px]"
              variant="outline"
              :modelValue="form.fromTime"
              :placeholder="_t('Start Time')"
              @update:modelValue="(t) => updateFromTime(t)"
            />
            <TimePicker
              v-if="!form.isFullDay"
              class="max-w-[112px]"
              variant="outline"
              :modelValue="form.toTime"
              :options="toTimeOptions"
              :placeholder="_t('End Time')"
              placement="bottom-end"
              @update:modelValue="(t) => updateToTime(t)"
            />
          </div>
        </div>

        <!-- Attendees -->
        <div class="flex items-start">
          <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
            {{ _t('Attendees') }}
          </div>
          <div class="w-9/12">
            <!-- Email tags input -->
            <div
              class="min-h-[34px] rounded border border-outline-gray-2 bg-surface-white px-2 py-1 flex flex-wrap gap-1 focus-within:border-outline-gray-3 cursor-text"
              @click="focusAttendeeInput"
            >
              <div
                v-for="a in form.attendees"
                :key="a.email"
                class="inline-flex items-center gap-1 rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-8"
              >
                <span>{{ a.email }}</span>
                <button
                  class="text-ink-gray-4 hover:text-ink-gray-7 leading-none"
                  @click.stop="removeAttendee(a.email)"
                >
                  ×
                </button>
              </div>
              <input
                ref="attendeeInput"
                v-model="attendeeInputVal"
                type="email"
                :placeholder="
                  form.attendees.length ? '' : _t('Add email address')
                "
                class="flex-1 min-w-[140px] bg-transparent text-sm text-ink-gray-9 placeholder-ink-gray-4 outline-none py-0.5"
                @keydown.enter.prevent="addAttendee"
                @keydown.tab.prevent="addAttendee"
                @keydown="
                  (e) => e.key === ',' && (e.preventDefault(), addAttendee())
                "
                @blur="addAttendee"
              />
            </div>
          </div>
        </div>

        <!-- Visibility -->
        <div class="flex items-start">
          <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
            {{ _t('Visibility') }}
          </div>
          <div class="w-9/12">
            <FormControl
              v-model="form.eventType"
              class="w-full"
              type="select"
              variant="outline"
              :options="[
                { label: _t('Private'), value: 'Private' },
                { label: _t('Public'), value: 'Public' },
              ]"
            />
          </div>
        </div>

        <!-- Location -->
        <div class="flex items-start">
          <div class="text-base text-ink-gray-7 mt-1.5 w-3/12">
            {{ _t('Location') }}
          </div>
          <div class="w-9/12">
            <input
              v-model="form.location"
              type="text"
              :placeholder="_t('Add location')"
              class="w-full rounded border border-outline-gray-2 bg-surface-white px-3 py-1.5 text-sm text-ink-gray-9 placeholder-ink-gray-4 focus:border-outline-gray-3 focus:outline-none"
            />
          </div>
        </div>

        <!-- Description -->
        <div class="flex">
          <div class="mt-2 text-base text-ink-gray-7 w-3/12">
            {{ _t('Description') }}
          </div>
          <div class="w-9/12">
            <TextEditor
              editor-class="!prose-sm overflow-auto min-h-[80px] max-h-80 py-1.5 px-2 rounded border border-outline-gray-2 hover:border-outline-gray-3 focus-within:border-outline-gray-3 bg-surface-white"
              :bubbleMenu="true"
              :content="form.description"
              :placeholder="_t('Add description.')"
              @change="(v) => (form.description = v)"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- ── Actions ── -->
    <template #actions>
      <div class="flex w-full items-center justify-between">
        <div>
          <ErrorMessage v-if="error" :message="_t(error)" />
        </div>
        <div class="flex gap-2 justify-end">
          <Button :label="_t('Cancel')" @click="show = false" />
          <Button
            variant="solid"
            :label="
              mode === 'edit'
                ? _t('Update')
                : mode === 'duplicate'
                  ? _t('Duplicate')
                  : _t('Create')
            "
            :disabled="!dirty"
            :loading="saving"
            @click="submit"
          />
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed, nextTick, h, onMounted } from 'vue'
import {
  Dialog,
  Button,
  Switch,
  DatePicker,
  TimePicker,
  Dropdown,
  FormControl,
  ErrorMessage,
  TextEditor,
  dayjs,
} from 'frappe-ui'

const _t = window.__ || ((s) => s)

// ── Props / emits ─────────────────────────────────────────────────────────────
const props = defineProps({
  event: { type: Object, default: () => ({}) },
  doctype: { type: String, default: '' },
  docname: { type: String, default: '' },
})
const emit = defineEmits(['saved', 'deleted'])
const show = defineModel({ type: Boolean, default: false })

// ── State ─────────────────────────────────────────────────────────────────────
const saving = ref(false)
const error = ref('')
const titleInput = ref(null)
const attendeeInput = ref(null)
const attendeeInputVal = ref('')

// ── Color palette (matches frappe-ui CalendarColorMap) ────────────────────────
const PALETTE = [
  { name: 'green', color: '#30A66D' },
  { name: 'blue', color: '#2490EF' },
  { name: 'purple', color: '#7B5EA7' },
  { name: 'red', color: '#E24C4C' },
  { name: 'orange', color: '#F97316' },
  { name: 'yellow', color: '#EAB308' },
  { name: 'gray', color: '#6B7280' },
  { name: 'teal', color: '#0D9488' },
  { name: 'pink', color: '#EC4899' },
]

const colorOptions = computed(() =>
  PALETTE.map((c) => {
    const isActive = (form.value.color || '#30A66D') === c.color
    return {
      label: c.name.charAt(0).toUpperCase() + c.name.slice(1),
      // Functional component — Vue 3 accepts () => VNode as a component.
      // Active color gets an outline ring; inactive gets none.
      icon: () =>
        h('div', {
          style: {
            width: '12px',
            height: '12px',
            borderRadius: '50%',
            backgroundColor: c.color,
            flexShrink: '0',
            outline: isActive
              ? `2px solid ${c.color}`
              : '2px solid transparent',
            outlineOffset: '2px',
          },
        }),
      onClick: () => {
        form.value.color = c.color
      },
    }
  }),
)

// ── Blank form factory ────────────────────────────────────────────────────────
function blankForm() {
  const now = dayjs()
  return {
    id: '',
    title: '',
    description: '',
    fromDate: now.format('YYYY-MM-DD'),
    toDate: now.format('YYYY-MM-DD'),
    fromTime: now.add(1, 'hour').startOf('hour').format('HH:mm'),
    toTime: now.add(2, 'hour').startOf('hour').format('HH:mm'),
    isFullDay: false,
    eventType: 'Public',
    location: '',
    color: '#30A66D',
    attendees: [],
  }
}

const form = ref(blankForm())
const oldForm = ref(blankForm())

// ── Mode ──────────────────────────────────────────────────────────────────────
const mode = computed(() => {
  if (!form.value.id) return 'create'
  if (form.value.id === 'duplicate') return 'duplicate'
  return 'edit'
})

const dirty = computed(
  () => JSON.stringify(form.value) !== JSON.stringify(oldForm.value),
)

// ── Populate form from event prop ─────────────────────────────────────────────
onMounted(() => {
  if (props.event?.name) {
    const e = props.event
    const start = dayjs(e.starts_on)
    const end = dayjs(e.ends_on)
    form.value = {
      id: e.name,
      title: e.subject || '',
      description: e.description || '',
      fromDate: start.format('YYYY-MM-DD'),
      toDate: end.format('YYYY-MM-DD'),
      fromTime: start.format('HH:mm'),
      toTime: end.format('HH:mm'),
      isFullDay: !!e.all_day,
      eventType: e.event_type || 'Public',
      location: e.location || '',
      color: e.color || '#30A66D',
      attendees: (e.event_participants || [])
        .filter((p) => p.email && p.email !== e.owner)
        .map((p) => ({ email: p.email })),
    }
    oldForm.value = JSON.parse(JSON.stringify(form.value))
  }
  nextTick(() => titleInput.value?.focus())
})

// ── Time helpers ──────────────────────────────────────────────────────────────
function allSlots() {
  const slots = []
  for (let h = 0; h < 24; h++) {
    for (let m of [0, 15, 30, 45]) {
      const hh = String(h).padStart(2, '0')
      const mm = String(m).padStart(2, '0')
      const ampm = h < 12 ? 'am' : 'pm'
      const h12 = h % 12 || 12
      slots.push({ value: `${hh}:${mm}`, label: `${h12}:${mm} ${ampm}` })
    }
  }
  return slots
}

const toTimeOptions = computed(() => {
  const slots = allSlots()
  if (!form.value.fromTime) return slots
  const startIdx = slots.findIndex((s) => s.value > form.value.fromTime)
  if (startIdx === -1) return []
  const [fh, fm] = form.value.fromTime.split(':').map(Number)
  const fromMins = fh * 60 + fm
  return slots.slice(startIdx).map((s) => {
    const [th, tm] = s.value.split(':').map(Number)
    const diff = th * 60 + tm - fromMins
    const hrs = Math.floor(diff / 60)
    const mins = diff % 60
    const dur =
      hrs && mins ? `${hrs}h ${mins}m` : hrs ? `${hrs} hr` : `${mins} min`
    return { ...s, label: `${s.label} (${dur})` }
  })
})

function updateDate(d) {
  form.value.fromDate = d
  form.value.toDate = d
}

function updateFromTime(t) {
  error.value = ''
  form.value.fromTime = t
  // auto-advance end time
  const [h, m] = t.split(':').map(Number)
  let nh = h + 1,
    nm = m
  if (nh >= 24) {
    nh = 23
    nm = 59
  }
  const newTo = `${String(nh).padStart(2, '0')}:${String(nm).padStart(2, '0')}`
  if (!form.value.toTime || form.value.toTime <= t) {
    form.value.toTime = newTo
  }
}

function updateToTime(t) {
  error.value = ''
  if (!form.value.isFullDay && t <= form.value.fromTime) {
    error.value = _t('End time should be after start time')
    return
  }
  form.value.toTime = t
}

// ── Attendees ─────────────────────────────────────────────────────────────────
function focusAttendeeInput() {
  attendeeInput.value?.focus()
}

function addAttendee() {
  const email = attendeeInputVal.value.trim().replace(/,$/, '')
  if (!email) return
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    error.value = _t('{0} is an invalid email address', [email])
    return
  }
  if (!form.value.attendees.some((a) => a.email === email)) {
    form.value.attendees.push({ email })
  }
  attendeeInputVal.value = ''
  error.value = ''
}

function removeAttendee(email) {
  form.value.attendees = form.value.attendees.filter((a) => a.email !== email)
}

// ── Duplicate ─────────────────────────────────────────────────────────────────
function duplicateEvent() {
  form.value.id = 'duplicate'
  form.value.title = form.value.title + ' (Copy)'
  oldForm.value = JSON.parse(
    JSON.stringify({ ...form.value, id: '', title: '' }),
  ) // force dirty
  nextTick(() => titleInput.value?.focus())
}

// ── Delete ────────────────────────────────────────────────────────────────────
function confirmDelete() {
  if (!form.value.id || form.value.id === 'duplicate') return
  if (!window.confirm(_t('Are you sure you want to delete this event?'))) return
  deleteEvent()
}

async function deleteEvent() {
  saving.value = true
  error.value = ''
  try {
    await apiFetch('frappe.client.delete', {
      doctype: 'Event',
      name: form.value.id,
    })
    show.value = false
    emit('deleted')
  } catch (e) {
    error.value = e?.message || _t('Failed to delete event')
  } finally {
    saving.value = false
  }
}

// ── Submit ────────────────────────────────────────────────────────────────────
function submit() {
  error.value = ''

  // Flush any pending attendee input
  if (attendeeInputVal.value.trim()) addAttendee()

  if (!form.value.title.trim()) {
    error.value = _t('Title is required')
    titleInput.value?.focus()
    return
  }
  if (!form.value.isFullDay && form.value.toTime <= form.value.fromTime) {
    error.value = _t('End time should be after start time')
    return
  }

  if (mode.value === 'edit') {
    updateEvent()
  } else {
    createEvent()
  }
}

async function createEvent() {
  saving.value = true
  error.value = ''
  try {
    // boot.user is the reliable source in the CRM SPA context
    const currentUser =
      window.frappe?.boot?.user || window.frappe?.session?.user || ''

    const participants = [
      // Link to the CRM Lead / Deal that owns this events tab
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
    // Email-only attendees — no Contact link (omit reference fields entirely
    // so Frappe doesn't require a reference_docname for them)
    form.value.attendees.forEach((a) => {
      participants.push({
        doctype: 'Event Participants',
        email: a.email,
      })
    })

    await apiFetch('frappe.client.insert', {
      doc: buildDoc(participants),
    })
    show.value = false
    emit('saved')
  } catch (e) {
    error.value = e?.message || _t('Failed to create event')
  } finally {
    saving.value = false
  }
}

async function updateEvent() {
  saving.value = true
  error.value = ''
  try {
    // Get current doc then patch
    const doc = await apiFetch('frappe.client.get', {
      doctype: 'Event',
      name: form.value.id,
    })
    const patch = buildDoc(doc.event_participants || [])
    Object.assign(doc, patch)
    // Sync attendees in participants table
    const currentUser = window.frappe?.session?.user || ''
    const keepEmails = new Set([
      props.docname,
      currentUser,
      ...form.value.attendees.map((a) => a.email),
    ])
    doc.event_participants = doc.event_participants.filter(
      (p) => keepEmails.has(p.email) || keepEmails.has(p.reference_docname),
    )
    form.value.attendees.forEach((a) => {
      if (!doc.event_participants.some((p) => p.email === a.email)) {
        doc.event_participants.push({
          doctype: 'Event Participants',
          email: a.email,
        })
      }
    })
    await apiFetch('frappe.client.save', { doc })
    show.value = false
    emit('saved')
  } catch (e) {
    error.value = e?.message || _t('Failed to update event')
  } finally {
    saving.value = false
  }
}

function buildDoc(participants) {
  const d = form.value.fromDate
  return {
    doctype: 'Event',
    subject: form.value.title.trim(),
    description: form.value.description || '',
    starts_on:
      d +
      ' ' +
      (form.value.isFullDay ? '00:00:00' : form.value.fromTime + ':00'),
    ends_on:
      d + ' ' + (form.value.isFullDay ? '23:59:59' : form.value.toTime + ':00'),
    all_day: form.value.isFullDay ? 1 : 0,
    event_type: form.value.eventType || 'Public',
    location: form.value.location || '',
    color: form.value.color || '#30A66D',
    status: 'Open',
    event_participants: participants,
  }
}

// ── API ───────────────────────────────────────────────────────────────────────
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
