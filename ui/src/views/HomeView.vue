<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDevicesStore } from '../stores/devices'
import SpeakerCard from '../components/SpeakerCard.vue'
import Button from 'primevue/button'
import type { Device } from '../api/devices'

const store = useDevicesStore()

// Expanded groups: set of group slugs
const expandedGroups = ref<Set<string>>(new Set())

function toggleGroup(slug: string) {
  if (expandedGroups.value.has(slug)) {
    expandedGroups.value.delete(slug)
  } else {
    expandedGroups.value.add(slug)
  }
  // Trigger reactivity
  expandedGroups.value = new Set(expandedGroups.value)
}

function isActive(d: Device) {
  const s = store.getState(d)
  return s?.status === 'PLAYING' || s?.status === 'PAUSED'
}

// All group devices
const groups = computed(() =>
  store.devices.filter(d => d.cast_type === 'group')
)

// Group member = audio chromecast when a group exists
const groupMembers = computed(() =>
  groups.value.length
    ? store.devices.filter(d => d.cast_type === 'audio')
    : []
)

// Idle group members (hidden unless expanded)
const idleGroupMembers = computed(() =>
  groupMembers.value.filter(d => !isActive(d))
)

// Active group members always visible
const activeGroupMembers = computed(() =>
  groupMembers.value.filter(d => isActive(d))
)

// Non-group devices (cast, sonos, groups themselves)
const nonGroupDevices = computed(() =>
  store.devices.filter(d => d.cast_type !== 'audio' || !groups.value.length)
)

const activeSpeakers = computed(() => {
  const active = nonGroupDevices.value.filter(d => isActive(d))
  // Also include individually active group members
  return [...active, ...activeGroupMembers.value]
})

const idleSpeakers = computed(() =>
  nonGroupDevices.value.filter(d => !isActive(d))
)

// Members to show for a given group (when expanded)
function getGroupMembers(groupSlug: string) {
  if (!expandedGroups.value.has(groupSlug)) return []
  return idleGroupMembers.value
}

function isGroup(d: Device) {
  return d.cast_type === 'group'
}

function isExpanded(d: Device) {
  return expandedGroups.value.has(d.slug)
}

function memberCount() {
  return idleGroupMembers.value.length
}

function onVolumeChange(device: Device, volume: number) {
  store.changeVolume(device, volume)
}
</script>

<template>
  <div class="home-view">
    <div class="header-row">
      <h1 class="page-title">Speakers</h1>
      <Button
        icon="pi pi-refresh"
        rounded
        text
        :loading="store.refreshing"
        @click="store.refresh()"
      />
    </div>

    <div v-if="store.loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
    </div>

    <div v-else-if="!store.devices.length" class="empty">
      <i class="mdi mdi-speaker-off" style="font-size: 3rem; color: var(--placeholder-color)"></i>
      <p>No speakers found on the network</p>
    </div>

    <template v-else>
      <!-- Active speakers -->
      <div v-if="activeSpeakers.length" class="speakers-grid active-section">
        <template v-for="device in activeSpeakers" :key="`${device.slug}:${device.type}`">
          <SpeakerCard
            :device="device"
            :state="store.getState(device)"
            @toggle-play-pause="store.togglePlayPause(device)"
            @stop="store.stop(device)"
            @next="store.next(device)"
            @prev="store.prev(device)"
            @toggle-shuffle="store.toggleShuffle(device)"
            @cycle-repeat="store.cycleRepeat(device)"
            @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
            @volume-change="onVolumeChange"
          />
        </template>
      </div>

      <!-- Idle speakers -->
      <div v-if="idleSpeakers.length" class="speakers-grid">
        <template v-for="device in idleSpeakers" :key="`${device.slug}:${device.type}`">
          <div v-if="isGroup(device)" class="group-wrapper" :class="{ collapsed: !isExpanded(device) }">
            <SpeakerCard
              :device="device"
              :state="store.getState(device)"
              @toggle-play-pause="store.togglePlayPause(device)"
              @stop="store.stop(device)"
              @next="store.next(device)"
              @prev="store.prev(device)"
              @toggle-shuffle="store.toggleShuffle(device)"
              @cycle-repeat="store.cycleRepeat(device)"
              @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
              @volume-change="onVolumeChange"
            />
            <!-- Expand/collapse button -->
            <button
              v-if="memberCount() > 0"
              class="expand-btn"
              @click="toggleGroup(device.slug)"
            >
              <i :class="isExpanded(device) ? 'mdi mdi-chevron-up' : 'mdi mdi-chevron-down'"></i>
              <span>{{ memberCount() }} {{ memberCount() === 1 ? 'speaker' : 'speakers' }}</span>
            </button>
            <!-- Expanded members -->
            <div v-if="isExpanded(device)" class="group-members">
              <SpeakerCard
                v-for="member in getGroupMembers(device.slug)"
                :key="`${member.slug}:${member.type}`"
                :device="member"
                :state="store.getState(member)"
                @toggle-play-pause="store.togglePlayPause(member)"
                @stop="store.stop(member)"
                @next="store.next(member)"
                @prev="store.prev(member)"
                @toggle-shuffle="store.toggleShuffle(member)"
                @cycle-repeat="store.cycleRepeat(member)"
                @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
                @volume-change="onVolumeChange"
              />
            </div>
          </div>
          <!-- Non-group idle devices -->
          <SpeakerCard
            v-else
            :device="device"
            :state="store.getState(device)"
            @toggle-play-pause="store.togglePlayPause(device)"
            @stop="store.stop(device)"
            @next="store.next(device)"
            @prev="store.prev(device)"
            @toggle-shuffle="store.toggleShuffle(device)"
            @cycle-repeat="store.cycleRepeat(device)"
            @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
            @volume-change="onVolumeChange"
          />
        </template>
      </div>
    </template>
  </div>
</template>

<style scoped>
.home-view {
  padding: 16px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
}

.speakers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  align-items: start;
}

.active-section {
  margin-bottom: 16px;
}

/* Group wrapper — one continuous card */
.group-wrapper {
  background: var(--card-bg);
  border-radius: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.group-wrapper :deep(> .speaker-card) {
  box-shadow: none;
  border-radius: 16px 16px 0 0;
}

.group-wrapper.collapsed :deep(> .speaker-card) {
  border-radius: 16px;
}

.expand-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  width: 100%;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-family: inherit;
  padding: 6px 0;
  cursor: pointer;
  transition: color 0.15s;
  border-top: 1px solid var(--border-color);
}

.expand-btn:hover {
  color: var(--text-primary);
}

.expand-btn i {
  font-size: 0.85rem;
}

.group-members {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 8px 8px;
}

.group-members :deep(.speaker-card) {
  box-shadow: none;
  background: var(--subtle-bg);
  border-radius: 12px;
  padding: 10px 12px;
}

.loading,
.empty {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-secondary);
}

.empty p {
  margin-top: 12px;
}
</style>
