<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import { useDevicesStore } from '../stores/devices'
import type { Device } from '../api/devices'

const props = withDefaults(defineProps<{
  visible: boolean
  showPlayOptions?: boolean
  forceShuffle?: boolean
}>(), {
  showPlayOptions: true,
  forceShuffle: false,
})

watch(() => props.visible, (open) => {
  if (open && props.forceShuffle) {
    shuffle.value = true
    savePrefs()
  }
})

export interface PlayOptions {
  device: Device
  shuffle: boolean
  repeat: 'off' | 'all' | 'one'
}

const emit = defineEmits<{
  'update:visible': [value: boolean]
  select: [options: PlayOptions]
}>()

const devicesStore = useDevicesStore()

const STORAGE_KEY = 'home-cast-play-prefs'

function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return JSON.parse(raw)
  } catch { /* ignore */ }
  return { shuffle: false, repeat: 'off' }
}

function savePrefs() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    shuffle: shuffle.value,
    repeat: repeat.value,
  }))
}

const prefs = loadPrefs()
const shuffle = ref<boolean>(prefs.shuffle)
const repeat = ref<'off' | 'all' | 'one'>(prefs.repeat)

function cycleRepeat() {
  const order: Array<'off' | 'all' | 'one'> = ['off', 'all', 'one']
  const idx = order.indexOf(repeat.value)
  repeat.value = order[(idx + 1) % order.length]
  savePrefs()
}

const repeatIcon = computed(() =>
  repeat.value === 'one' ? 'mdi mdi-repeat-once' : 'mdi mdi-repeat'
)

function blurCloseButton() {
  setTimeout(() => {
    const el = document.activeElement as HTMLElement | null
    el?.blur()
  }, 0)
}

function onSelect(device: Device) {
  emit('select', { device, shuffle: shuffle.value, repeat: repeat.value })
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    header="Play on speaker"
    modal
    :closable="true"
    :closeOnEscape="true"
    :style="{ width: '90vw', maxWidth: '400px' }"
    @show="blurCloseButton"
  >
    <div v-if="showPlayOptions" class="play-options">
      <Button
        icon="mdi mdi-shuffle-variant"
        rounded
        text
        :class="{ 'mode-active': shuffle }"
        @click="shuffle = !shuffle; savePrefs()"
      />
      <Button
        :icon="repeatIcon"
        rounded
        text
        :class="{ 'mode-active': repeat !== 'off' }"
        @click="cycleRepeat"
      />
      <span class="options-label">
        <template v-if="shuffle">Shuffle</template>
        <template v-if="shuffle && repeat !== 'off'"> &middot; </template>
        <template v-if="repeat === 'all'">Repeat all</template>
        <template v-else-if="repeat === 'one'">Repeat one</template>
      </span>
    </div>

    <div class="speaker-list">
      <div v-if="!devicesStore.devices.length" class="empty">
        No speakers found
      </div>
      <button
        v-for="device in devicesStore.devices"
        :key="`${device.slug}:${device.type}`"
        class="speaker-option"
        @click="onSelect(device)"
      >
        <i :class="device.type === 'sonos' ? 'mdi mdi-speaker' : 'mdi mdi-cast-audio'"></i>
        <div>
          <div class="option-name">{{ device.friendly_name }}</div>
          <div class="option-type">{{ device.type }}</div>
        </div>
      </button>
    </div>
  </Dialog>
</template>

<style scoped>
.play-options {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 4px 12px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 8px;
}

.options-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-left: 4px;
}

.mode-active {
  color: var(--p-primary-color, #6366f1) !important;
}

.speaker-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.speaker-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: none;
  background: none;
  border-radius: 12px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: background 0.15s;
}

.speaker-option:hover {
  background: var(--hover-bg);
}

.speaker-option i {
  font-size: 1.2rem;
  color: var(--text-secondary);
}

.option-name {
  font-weight: 500;
  font-size: 0.9rem;
}

.option-type {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.empty {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
}
</style>
