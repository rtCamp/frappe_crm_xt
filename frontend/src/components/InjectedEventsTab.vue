<template>
  <div class="flex h-full flex-col overflow-hidden bg-surface-white">
    <!-- ── Header ── -->
    <div
      class="mx-4 my-3 flex items-center justify-between text-lg font-medium sm:mx-10 sm:mb-4 sm:mt-8"
    >
      <div class="flex h-8 items-center text-xl font-semibold text-ink-gray-8">
        {{ _t('Events') }}
      </div>
      <Button variant="solid" @click="openEvent(null)">
        <template #prefix>
          <svg
            viewBox="0 0 24 24"
            class="h-4 w-4"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </template>
        <span>{{ _t('Schedule an Event') }}</span>
      </Button>
    </div>

    <!-- ── Scrollable list ── -->
    <div v-if="!loading && events.length" class="flex-1 overflow-y-auto py-3">
      <div v-for="(event, i) in events" :key="event.name">
        <div
          class="activity grid grid-cols-[30px_minmax(auto,_1fr)] gap-4 px-3 sm:px-10"
        >
          <!-- Left: timeline connector + calendar icon -->
          <div
            class="z-0 relative flex justify-center before:absolute before:left-[50%] before:-z-[1] before:top-0 before:border-l before:border-outline-gray-modals"
            :class="i !== events.length - 1 ? 'before:h-full' : 'before:h-4'"
          >
            <div
              class="flex h-8 w-7 items-center justify-center bg-surface-white text-ink-gray-8"
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
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
            </div>
          </div>

          <!-- Right: header + event card -->
          <div class="mb-5">
            <!-- "Owner has created an event" + time ago -->
            <div
              class="mb-1 flex items-center justify-stretch gap-2 py-1 text-base"
            >
              <div
                class="inline-flex items-center flex-wrap gap-1 text-ink-gray-5"
              >
                <Avatar
                  :image="event.owner.image"
                  :label="event.owner.label"
                  size="md"
                />
                <span class="font-medium text-ink-gray-8 ml-1">{{
                  event.owner.label
                }}</span>
                <span>{{ _t('has created an event') }}</span>
              </div>
              <div class="ml-auto whitespace-nowrap">
                <Tooltip :text="formatDate(event.creation)">
                  <div class="text-sm text-ink-gray-5">
                    {{ timeAgo(event.creation) }}
                  </div>
                </Tooltip>
              </div>
            </div>

            <!-- Event card -->
            <div
              class="flex gap-2 border cursor-pointer border-outline-gray-modals rounded-lg bg-surface-cards px-2.5 py-2.5 text-ink-gray-9"
              @click="openEvent(event)"
            >
              <!-- Color bar -->
              <div
                class="flex w-[2px] rounded-lg flex-shrink-0"
                :style="{ backgroundColor: event.color || '#30A66D' }"
              />
              <!-- Content -->
              <div class="flex-1 flex flex-col gap-1 text-base min-w-0">
                <div
                  class="flex items-center justify-between gap-2 font-medium text-ink-gray-7"
                >
                  <div class="truncate">{{ event.subject }}</div>
                  <!-- MultipleAvatar (inline) -->
                  <div
                    v-if="event.participants?.length > 1"
                    class="flex -space-x-1 flex-shrink-0"
                  >
                    <div
                      v-for="p in event.participants.slice(0, 3)"
                      :key="p.name"
                      class="size-5 rounded-full ring-1 ring-white overflow-hidden bg-surface-gray-3 flex items-center justify-center text-[9px] font-medium text-ink-gray-7"
                      :title="p.label"
                    >
                      <img
                        v-if="p.image"
                        :src="p.image"
                        :alt="p.label"
                        class="size-full object-cover"
                      />
                      <span v-else>{{
                        (p.label || '?').charAt(0).toUpperCase()
                      }}</span>
                    </div>
                    <div
                      v-if="event.participants.length > 3"
                      class="size-5 rounded-full ring-1 ring-white bg-surface-gray-2 flex items-center justify-center text-[9px] font-medium text-ink-gray-5"
                    >
                      +{{ event.participants.length - 3 }}
                    </div>
                  </div>
                </div>
                <div
                  class="flex justify-between gap-2 items-center text-ink-gray-6"
                >
                  <div>
                    {{
                      startEndTime(
                        event.starts_on,
                        event.ends_on,
                        event.all_day,
                      )
                    }}
                  </div>
                  <div>{{ startDate(event.starts_on) }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Loading ── -->
    <div
      v-else-if="loading"
      class="flex h-full flex-1 items-center justify-center text-sm text-ink-gray-5"
    >
      {{ _t('Loading…') }}
    </div>

    <!-- ── Empty state (matches PR exactly) ── -->
    <div
      v-else
      class="flex h-full flex-1 flex-col items-center justify-center gap-3 text-xl font-medium text-ink-gray-4"
    >
      <svg
        viewBox="0 0 24 24"
        class="h-10 w-10"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
      <span>{{ _t('No Events Scheduled') }}</span>
      <Button variant="solid" @click="openEvent(null)">
        <template #prefix>
          <svg
            viewBox="0 0 24 24"
            class="h-4 w-4"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </template>
        <span>{{ _t('Schedule an Event') }}</span>
      </Button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, createApp, h, defineComponent } from 'vue'
import { dayjs, Avatar, Tooltip, Button, Dialogs } from 'frappe-ui'
import InjectedEventModal from './InjectedEventModal.vue'

const _t = window.__ || ((s) => s)

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
})

// ── State ────────────────────────────────────────────────────────────────────
const loading = ref(true)
const events = ref([])
let _modalApp = null
let _modalEl = null

// ── Helpers ──────────────────────────────────────────────────────────────────
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

function getUser(email) {
  const u = window.frappe?.boot?.user_info?.[email] || {}
  return {
    label: u.fullname || u.full_name || email?.split('@')[0] || email || '?',
    image: u.image || u.user_image || '',
    name: email,
  }
}

// ── Fetch ─────────────────────────────────────────────────────────────────────
async function fetchEvents() {
  loading.value = true
  try {
    // Use a dedicated server-side method so we don't need direct read
    // permission on the 'Event Participants' child doctype.
    const raw =
      (await apiFetch('frappe_crm_xt.api.event.get_doc_events', {
        doctype: props.doctype,
        docname: props.docname,
      })) || []

    events.value = raw.map((ev) => {
      const owner = getUser(ev.owner)
      const evParts = ev.event_participants || []
      return {
        ...ev,
        owner,
        participants: [
          owner,
          ...evParts
            .filter((p) => p.email && p.email !== ev.owner)
            .map((p) => getUser(p.email)),
        ],
      }
    })
  } catch (e) {
    console.warn('[crm-xt] events fetch error', e)
  } finally {
    loading.value = false
  }
}

// ── Modal ─────────────────────────────────────────────────────────────────────
function closeModal() {
  if (_modalApp) {
    _modalApp.unmount()
    _modalApp = null
  }
  if (_modalEl?.parentNode) {
    _modalEl.parentNode.removeChild(_modalEl)
    _modalEl = null
  }
}

function openEvent(event) {
  closeModal()
  const el = document.createElement('div')
  document.body.appendChild(el)
  _modalEl = el
  // Wrap InjectedEventModal + Dialogs in a root component so frappe-ui's
  // confirmDialog has a Dialogs mount point in the same Vue app instance.
  const Root = defineComponent({
    render() {
      return h('div', [
        h(InjectedEventModal, {
          event: event || {},
          doctype: props.doctype,
          docname: props.docname,
          onClose: closeModal,
          onSaved: () => {
            closeModal()
            fetchEvents()
          },
          onDeleted: () => {
            closeModal()
            fetchEvents()
          },
        }),
        h(Dialogs),
      ])
    },
  })
  _modalApp = createApp(Root)
  _modalApp.config.globalProperties.__ = window.__ || ((s) => s)
  _modalApp.mount(el)
}

// ── Formatting ────────────────────────────────────────────────────────────────
function startEndTime(s, e, allDay) {
  if (allDay) return _t('All day')
  return `${dayjs(s).format('h:mm a')} - ${dayjs(e).format('h:mm a')}`
}

function startDate(s) {
  return dayjs(s).format('ddd, D MMM YYYY')
}

function formatDate(d) {
  return dayjs(d).format('ddd, D MMM YYYY, h:mm a')
}

function timeAgo(date) {
  const diff = dayjs().diff(dayjs(date), 'second')
  if (diff < 60) return _t('just now')
  if (diff < 3600) return `${Math.floor(diff / 60)} ${_t('min ago')}`
  if (diff < 86400) return `${Math.floor(diff / 3600)} ${_t('hr ago')}`
  if (diff < 604800) return `${Math.floor(diff / 86400)} ${_t('days ago')}`
  return dayjs(date).format('D MMM YYYY')
}

onMounted(fetchEvents)
</script>
