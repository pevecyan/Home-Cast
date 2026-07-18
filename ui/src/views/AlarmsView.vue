<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { useAlarmsStore } from '../stores/alarms'
import { useDevicesStore } from '../stores/devices'
import { useFavoriteRadioStore } from '../stores/favoriteRadio'
import { listPlaylists, type SavedPlaylist } from '../api/playlists'
import type { Alarm, AlarmInput, RepeatMode } from '../api/schedule'
import { deviceIcon } from '../utils/deviceIcon'
import FormSection from '../components/form/FormSection.vue'
import FormRow from '../components/form/FormRow.vue'
import FormToggle from '../components/form/FormToggle.vue'
import SegmentedControl from '../components/form/SegmentedControl.vue'

const alarmsStore = useAlarmsStore()
const devicesStore = useDevicesStore()
const favStore = useFavoriteRadioStore()

const playlists = ref<SavedPlaylist[]>([])

// Mon..Sun labels, index = weekday mask value (Mon=0..Sun=6)
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

// Speaker targets the server can drive (exclude the browser-only pseudo-device).
const speakerTargets = computed(() => [
  { label: 'All speakers', value: JSON.stringify({ slug: 'all', type: 'all' }), type: 'all' as const },
  ...devicesStore.devices
    .filter(d => d.type !== 'local')
    .map(d => ({
      label: d.friendly_name,
      value: JSON.stringify({ slug: d.slug, type: d.type }),
      type: d.type,
    })),
])

interface SourceOption { label: string; value: string; kind: 'playlist' | 'radio'; ref: string }

const sourceOptions = computed<SourceOption[]>(() => [
  ...playlists.value.map(p => ({
    label: `▶ ${p.name}`, value: `playlist:${p.id}`, kind: 'playlist' as const, ref: p.id,
  })),
  ...favStore.favorites.map(s => ({
    label: `📻 ${s.name}`, value: `radio:${s.stationuuid}`, kind: 'radio' as const, ref: s.stationuuid,
  })),
])

const repeatOptions: { label: string; value: RepeatMode; icon: string }[] = [
  { label: 'Off', value: 'off', icon: 'mdi mdi-repeat-off' },
  { label: 'All', value: 'all', icon: 'mdi mdi-repeat' },
  { label: 'One', value: 'one', icon: 'mdi mdi-repeat-once' },
]

// --- Editor state ---
const showEditor = ref(false)
const editingId = ref<string | null>(null)

const form = reactive({
  time: '07:00',
  days: [] as number[],
  targetValue: JSON.stringify({ slug: 'all', type: 'all' }),
  sourceValue: '' as string,
  shuffle: false,
  repeat: 'off' as RepeatMode,
  volumeEnabled: false,
  volume: 40,       // percent (0..100 for the slider)
  fadeIn: 0,        // seconds
})

const fadeEnabled = computed({
  get: () => form.fadeIn > 0,
  set: (on: boolean) => { form.fadeIn = on ? 60 : 0 },
})

function resetForm() {
  form.time = '07:00'
  form.days = []
  form.targetValue = JSON.stringify({ slug: 'all', type: 'all' })
  form.sourceValue = sourceOptions.value[0]?.value ?? ''
  form.shuffle = false
  form.repeat = 'off'
  form.volumeEnabled = false
  form.volume = 40
  form.fadeIn = 0
}

function openCreate() {
  editingId.value = null
  resetForm()
  showEditor.value = true
}

function openEdit(alarm: Alarm) {
  editingId.value = alarm.id
  form.time = alarm.time
  form.days = [...alarm.days]
  form.targetValue = JSON.stringify(alarm.target)
  form.sourceValue = `${alarm.action.kind}:${alarm.action.ref}`
  form.shuffle = alarm.shuffle
  form.repeat = alarm.repeat
  form.volumeEnabled = alarm.volume != null
  form.volume = alarm.volume != null ? Math.round(alarm.volume * 100) : 40
  form.fadeIn = alarm.fadeIn
  showEditor.value = true
}

function toggleDay(d: number) {
  const i = form.days.indexOf(d)
  if (i === -1) form.days.push(d)
  else form.days.splice(i, 1)
}

const canSave = computed(() => !!form.sourceValue && !!form.time)

async function save() {
  const source = sourceOptions.value.find(s => s.value === form.sourceValue)
  if (!source) return
  const payload: AlarmInput = {
    time: form.time,
    days: [...form.days].sort((a, b) => a - b),
    target: JSON.parse(form.targetValue),
    action: { kind: source.kind, ref: source.ref, name: source.label.replace(/^[▶📻]\s*/, '') },
    shuffle: form.shuffle,
    repeat: form.repeat,
    volume: form.volumeEnabled ? form.volume / 100 : null,
    fadeIn: form.fadeIn,
    enabled: true,
  }
  if (editingId.value) {
    await alarmsStore.update(editingId.value, payload)
  } else {
    await alarmsStore.create(payload)
  }
  showEditor.value = false
}

async function onToggle(alarm: Alarm) {
  await alarmsStore.toggle(alarm.id)
}

async function onDelete(alarm: Alarm) {
  await alarmsStore.remove(alarm.id)
}

// --- Display helpers ---
function daysLabel(alarm: Alarm): string {
  if (!alarm.days.length) return 'Once'
  if (alarm.days.length === 7) return 'Every day'
  const weekdays = [0, 1, 2, 3, 4]
  if (alarm.days.length === 5 && weekdays.every(d => alarm.days.includes(d))) return 'Weekdays'
  if (alarm.days.length === 2 && alarm.days.includes(5) && alarm.days.includes(6)) return 'Weekends'
  return [...alarm.days].sort((a, b) => a - b).map(d => DAYS[d]).join(', ')
}

function targetLabel(alarm: Alarm): string {
  if (alarm.target.slug === 'all') return 'All speakers'
  const d = devicesStore.devices.find(dev => dev.slug === alarm.target.slug)
  return d?.friendly_name ?? alarm.target.slug
}

onMounted(async () => {
  alarmsStore.load()
  favStore.load()
  if (!devicesStore.hasRealDevices) devicesStore.fetchDevices()
  try { playlists.value = await listPlaylists() } catch { /* ignore */ }
})
</script>

<template>
  <div class="alarms-view">
    <div class="header-row">
      <h1 class="page-title">Alarms</h1>
      <Button icon="pi pi-plus" rounded text @click="openCreate" />
    </div>

    <div v-if="alarmsStore.loading && !alarmsStore.alarms.length" class="empty">Loading…</div>

    <div v-else-if="!alarmsStore.alarms.length" class="empty">
      <i class="mdi mdi-alarm-off"></i>
      <p>No alarms yet.</p>
      <p class="hint">Schedule a playlist or radio station to play at a set time.</p>
    </div>

    <ul v-else class="alarm-list">
      <li v-for="alarm in alarmsStore.alarms" :key="alarm.id" class="alarm-card" :class="{ disabled: !alarm.enabled }">
        <div class="alarm-main" @click="openEdit(alarm)">
          <div class="alarm-time">{{ alarm.time }}</div>
          <div class="alarm-meta">
            <span class="alarm-days">{{ daysLabel(alarm) }}</span>
            <span class="alarm-sub">
              <i :class="alarm.action.kind === 'radio' ? 'mdi mdi-radio' : 'mdi mdi-playlist-music'"></i>
              {{ alarm.action.name || alarm.action.ref }}
            </span>
            <span class="alarm-sub">
              <i :class="alarm.target.slug === 'all' ? 'mdi mdi-speaker-multiple' : deviceIcon(alarm.target.type as any)"></i>
              {{ targetLabel(alarm) }}
              <template v-if="alarm.volume != null"> · {{ Math.round(alarm.volume * 100) }}%</template>
              <template v-if="alarm.fadeIn > 0"> · fade {{ alarm.fadeIn }}s</template>
            </span>
          </div>
        </div>
        <div class="alarm-actions">
          <FormToggle :modelValue="alarm.enabled" @update:modelValue="onToggle(alarm)" />
          <button class="icon-btn danger" title="Delete" @click.stop="onDelete(alarm)">
            <i class="mdi mdi-delete-outline"></i>
          </button>
        </div>
      </li>
    </ul>

    <!-- Editor -->
    <Dialog
      v-model:visible="showEditor"
      :header="editingId ? 'Edit alarm' : 'New alarm'"
      modal
      :style="{ width: '90vw', maxWidth: '440px' }"
    >
      <div class="editor">
        <FormSection label="When">
          <FormRow name="Time">
            <input v-model="form.time" type="time" class="time-input" />
          </FormRow>
          <FormRow stacked>
            <div class="day-chips">
              <button
                v-for="(label, d) in DAYS"
                :key="d"
                type="button"
                class="day-chip"
                :class="{ active: form.days.includes(d) }"
                @click="toggleDay(d)"
              >{{ label }}</button>
            </div>
            <span class="hint">{{ form.days.length ? 'Recurring' : 'One-shot — fires once, then turns off' }}</span>
          </FormRow>
        </FormSection>

        <FormSection label="Play">
          <FormRow name="Source" stacked>
            <Select
              v-model="form.sourceValue"
              :options="sourceOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="Pick a playlist or radio station"
              :emptyMessage="'Save a playlist or favorite a radio station first'"
              class="full"
            />
          </FormRow>
          <FormRow name="On speaker" stacked>
            <Select
              v-model="form.targetValue"
              :options="speakerTargets"
              optionLabel="label"
              optionValue="value"
              class="full"
            />
          </FormRow>
          <FormRow name="Shuffle">
            <FormToggle v-model="form.shuffle" />
          </FormRow>
          <FormRow name="Repeat" stacked>
            <SegmentedControl v-model="form.repeat" :options="repeatOptions" />
          </FormRow>
        </FormSection>

        <FormSection label="Volume">
          <FormRow name="Set volume" desc="Adjust before playback starts">
            <FormToggle v-model="form.volumeEnabled" />
          </FormRow>
          <FormRow v-if="form.volumeEnabled" stacked>
            <div class="slider-row">
              <input v-model.number="form.volume" type="range" min="0" max="100" class="range grow" />
              <span class="slider-val">{{ form.volume }}%</span>
            </div>
          </FormRow>
          <FormRow v-if="form.volumeEnabled" name="Fade in" desc="Ramp up gently from silent">
            <FormToggle v-model="fadeEnabled" />
          </FormRow>
          <FormRow v-if="form.volumeEnabled && fadeEnabled" stacked>
            <div class="slider-row">
              <input v-model.number="form.fadeIn" type="range" min="5" max="300" step="5" class="range grow" />
              <span class="slider-val">{{ form.fadeIn }}s</span>
            </div>
          </FormRow>
        </FormSection>
      </div>

      <template #footer>
        <Button label="Cancel" text @click="showEditor = false" />
        <Button label="Save" :disabled="!canSave" @click="save" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.alarms-view {
  padding: 16px;
}

.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 48px 16px;
}

.empty i {
  font-size: 3rem;
  opacity: 0.4;
}

.empty .hint {
  font-size: 0.85rem;
  opacity: 0.7;
}

.alarm-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.alarm-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 14px;
  transition: opacity 0.15s;
}

.alarm-card.disabled {
  opacity: 0.5;
}

.alarm-main {
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  flex: 1;
  min-width: 0;
}

.alarm-time {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.alarm-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.alarm-days {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.9rem;
}

.alarm-sub {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.alarm-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.icon-btn {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 1.3rem;
  padding: 4px;
  border-radius: 8px;
  display: flex;
}

.icon-btn.danger:hover {
  color: #ef4444;
  background: var(--hover-bg);
}

/* ── Editor ── */
.editor {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.time-input {
  font-size: 1.4rem;
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: 10px;
  background: var(--surface-dim, var(--card-bg));
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.full {
  width: 100%;
}

.day-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.day-chip {
  border: 1.5px solid var(--border-color);
  background: none;
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.day-chip.active {
  background: var(--surface-dim);
  border-color: var(--p-primary-color, #6366f1);
  color: var(--p-primary-color, #6366f1);
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 14px;
}

.grow {
  flex: 1;
}

.range {
  accent-color: var(--p-primary-color, #6366f1);
  height: 4px;
}

.slider-val {
  font-size: 0.85rem;
  color: var(--text-secondary);
  width: 42px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
</style>
