<template>
  <div class="flex flex-col gap-2 truncate fcrm-xt-notif-host">
    <div
      class="inline-flex items-center cursor-pointer transition-colors focus:outline-none shrink-0 text-ink-gray-8 bg-surface-white border border-outline-gray-2 hover:border-outline-gray-3 active:border-outline-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded"
      @click="addShowNotifications"
    >
      <div class="truncate">
        {{ notificationSummary }}
      </div>
    </div>
    <div v-if="notifications?.length && show" class="flex flex-col gap-2">
      <div v-for="(notification, i) in notifications" :key="notification.name">
        <div v-if="isAllDay" class="flex gap-1">
          <div class="flex flex-col flex-1 items-center gap-2">
            <div class="flex items-center gap-2 w-full">
              <FormControl
                v-model="notification.type"
                class="flex-1 shrink-0"
                type="select"
                :options="[
                  {
                    label: __('Notification'),
                    value: 'Notification',
                  },
                  {
                    label: __('Email'),
                    value: 'Email',
                  },
                ]"
                variant="outline"
                :placeholder="__('Select Type')"
              />
              <div>{{ __('at') }}</div>
              <TimePicker
                v-if="isAllDay"
                v-model="notification.time"
                class="flex-1 shrink-0"
                variant="outline"
                :placeholder="__('08:00 AM')"
              />
            </div>
            <div class="flex items-center gap-2 w-full">
              <FormControl
                v-model.number="notification.before"
                class="w-fit"
                type="number"
                :min="min(notification)"
                :max="max(notification)"
                variant="outline"
                :placeholder="__('10')"
                @blur="handleIntervalChange(notification)"
              />
              <FormControl
                v-model="notification.interval"
                class="flex-1 shrink-0"
                type="select"
                :options="intervalOptions(notification)"
                variant="outline"
                :placeholder="__('minutes')"
                @update:modelValue="() => handleIntervalChange(notification)"
              />
            </div>
            <Button
              v-if="i == notifications.length - 1"
              class="w-full"
              :icon-left="BellIcon"
              :label="__('Add Notification')"
              variant="outline"
              size="sm"
              @click="addNotification"
            />
          </div>
          <Button
            icon="x"
            variant="ghost"
            @click="
              notifications.splice(notifications.indexOf(notification), 1)
            "
          />
        </div>
        <div v-else class="flex gap-1">
          <div class="flex flex-col flex-1 items-center gap-2">
            <div class="flex items-center gap-2 w-full">
              <FormControl
                v-model="notification.type"
                class="flex-1 shrink-0"
                type="select"
                :options="[
                  {
                    label: __('Notification'),
                    value: 'Notification',
                  },
                  {
                    label: __('Email'),
                    value: 'Email',
                  },
                ]"
                variant="outline"
                :placeholder="__('Select Type')"
              />
            </div>
            <div class="flex items-center gap-2 w-full">
              <FormControl
                v-model.number="notification.before"
                class="w-fit"
                type="number"
                :min="min(notification)"
                :max="max(notification)"
                :step="notification.interval === 'minutes' ? 5 : 1"
                variant="outline"
                :placeholder="__('10')"
                @blur="handleIntervalChange(notification)"
              />
              <FormControl
                v-model="notification.interval"
                class="flex-1 shrink-0"
                type="select"
                :options="intervalOptions(notification)"
                variant="outline"
                :placeholder="__('minutes')"
                @update:modelValue="() => handleIntervalChange(notification)"
              />
            </div>
            <Button
              v-if="i == notifications.length - 1"
              class="w-full"
              :icon-left="BellIcon"
              :label="__('Add Notification')"
              variant="outline"
              size="sm"
              @click="addNotification"
            />
          </div>
          <Button
            icon="x"
            variant="ghost"
            @click="
              notifications.splice(notifications.indexOf(notification), 1)
            "
          />
        </div>
        <div
          v-if="i < notifications.length - 1"
          class="w-full h-px mt-3 mb-1 border-t border-outline-gray-1"
        />
      </div>
    </div>
  </div>
</template>
<script setup>
import BellIcon from './Icons/BellIcon.vue'
import { min, max, handleIntervalChange } from './Calendar/utils'
import { TimePicker, FormControl, Button } from 'frappe-ui'
import { computed, ref } from 'vue'

const props = defineProps({
  isAllDay: { type: Boolean, default: false },
})

const notifications = defineModel({ type: Array, default: () => [] })
const show = ref(false)

const intervalOptions = (n) => {
  if (props.isAllDay) {
    if (n.interval === 'minutes' || n.interval === 'hours') {
      n.interval = 'days'
    }

    if (!n.time) {
      n.time = '08:00'
    }

    return [
      {
        label: n.before == 1 ? __('day before') : __('days before'),
        value: 'days',
      },
      {
        label: n.before == 1 ? __('week before') : __('weeks before'),
        value: 'weeks',
      },
    ]
  }
  return [
    {
      label: n.before == 1 ? __('minute before') : __('minutes before'),
      value: 'minutes',
    },
    {
      label: n.before == 1 ? __('hour before') : __('hours before'),
      value: 'hours',
    },
    {
      label: n.before == 1 ? __('day before') : __('days before'),
      value: 'days',
    },
    {
      label: n.before == 1 ? __('week before') : __('weeks before'),
      value: 'weeks',
    },
  ]
}

function addNotification() {
  notifications.value ??= []
  if (props.isAllDay) {
    notifications.value.push({
      type: 'Notification',
      before: 1,
      interval: 'days',
      time: '08:00',
    })
  } else {
    notifications.value.push({
      type: 'Notification',
      before: 10,
      interval: 'minutes',
    })
  }
}

function addShowNotifications() {
  if (!notifications.value?.length) {
    addNotification()
    show.value = true
  } else {
    show.value = !show.value
  }
}

const notificationSummary = computed(() => {
  if (!notifications.value?.length) return __('Add Notification')
  return notifications.value
    .map((n) => {
      let intervalLabel = ''
      switch (n.interval) {
        case 'minutes':
          intervalLabel = n.before == 1 ? __('minute') : __('minutes')
          break
        case 'hours':
          intervalLabel = n.before == 1 ? __('hour') : __('hours')
          break
        case 'days':
          intervalLabel = n.before == 1 ? __('day') : __('days')
          break
        case 'weeks':
          intervalLabel = n.before == 1 ? __('week') : __('weeks')
          break
      }
      if (props.isAllDay) {
        let time = formatTime(n.time)
        return `${n.before} ${intervalLabel} before at ${time}`
      } else {
        return `${n.before} ${intervalLabel} before`
      }
    })
    .join(', ')
})

function formatTime(time) {
  if (!time) {
    time = '08:00'
  }
  const [hours, minutes] = time.split(':').map(Number)
  const period = hours >= 12 ? 'pm' : 'am'
  const formattedHours = hours % 12 || 12
  return `${formattedHours.toString().padStart(1, '0')}:${minutes
    .toString()
    .padStart(2, '0')} ${period}`
}
</script>

<style scoped>
/*
 * Add a chevron-down icon to every FormControl type="select" trigger inside
 * this notifications component (Notification/Email picker, interval picker).
 *
 * FormControl with type="select" renders a Reka-UI <button role="combobox"
 * data-slot="trigger"> without any visible chevron in this build, so users
 * can't tell it's a dropdown. The selector below is precise:
 *   - scoped to this component via `[data-v-...]` (Vue auto-adds it)
 *   - limited to the `.fcrm-xt-notif-host` wrapper we just added
 *   - matches only Reka-UI select triggers, not regular buttons
 * So the Cancel/X/Add Notification buttons are untouched.
 */
.fcrm-xt-notif-host :deep(button[role='combobox'][data-slot='trigger']) {
  justify-content: space-between;
}
.fcrm-xt-notif-host :deep(button[role='combobox'][data-slot='trigger'])::after {
  content: '';
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23687076' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>");
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
  transition: transform 0.15s ease;
}
.fcrm-xt-notif-host
  :deep(
    button[role='combobox'][data-slot='trigger'][data-state='open']
  )::after {
  transform: rotate(180deg);
}

/*
 * TimePicker (e.g. all-day "at <time>" picker) hits the same Tailwind
 * logical-property bug as the date/time row in the parent modal — the chevron
 * wrapper has `end-0`/`pe-2` classes that don't get compiled, so it falls back
 * to the left edge of the input. Fix it within this component only.
 */
.fcrm-xt-notif-host :deep(.relative > .absolute.end-0) {
  right: 0;
  left: auto;
  inset-inline-end: 0;
  inset-inline-start: auto;
  padding-inline-end: 0.5rem; /* matches pe-2 (8px) */
}
</style>
