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

function hasOwnPlaylist(d: Device) {
  const s = store.getState(d)
  return !!(s?.queue?.trackCount && s.queue.trackCount > 0)
}

// All group devices
const groups = computed(() =>
  store.devices.filter(d => d.cast_type === 'group')
)

// Group member = audio chromecast that is actually listed in at least one group's members array
const groupMemberUuids = computed(() => {
  const uuids = new Set<string>()
  groups.value.forEach(g => g.members?.forEach(m => uuids.add(m)))
  return uuids
})

const groupMembers = computed(() =>
  store.devices.filter(d =>
    d.cast_type === 'audio' && d.uuid && groupMemberUuids.value.has(d.uuid) && !hasOwnPlaylist(d)
  )
)

// Idle group members (hidden unless expanded)
const idleGroupMembers = computed(() =>
  groupMembers.value.filter(d => !isActive(d))
)

// Active group members always visible
const activeGroupMembers = computed(() =>
  groupMembers.value.filter(d => isActive(d))
)

// Non-group devices: everything that isn't an actual group member (or has its own playlist)
const nonGroupDevices = computed(() =>
  store.devices.filter(d =>
    d.cast_type !== 'audio' ||
    !d.uuid ||
    !groupMemberUuids.value.has(d.uuid) ||
    hasOwnPlaylist(d)
  )
)

const activeSpeakers = computed(() => {
  const active = nonGroupDevices.value.filter(d => isActive(d))
  // Also include individually active group members
  return [...active, ...activeGroupMembers.value]
})

const idleSpeakers = computed(() =>
  nonGroupDevices.value.filter(d => !isActive(d))
)

// Members to show for a given group (expanded or group is active)
function getGroupMembers(groupSlug: string) {
  const group = store.devices.find(d => d.slug === groupSlug)
  const groupActive = group ? isActive(group) : false
  if (!expandedGroups.value.has(groupSlug) && !groupActive) return []
  if (group?.members?.length) {
    return idleGroupMembers.value.filter(d => d.uuid && group.members!.includes(d.uuid))
  }
  return idleGroupMembers.value
}

function isGroup(d: Device) {
  return d.cast_type === 'group'
}

function isExpanded(d: Device) {
  return expandedGroups.value.has(d.slug)
}

function memberCount(groupSlug: string) {
  const group = store.devices.find(d => d.slug === groupSlug)
  if (group?.members?.length) {
    return idleGroupMembers.value.filter(d => d.uuid && group.members!.includes(d.uuid)).length
  }
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
          <div v-if="isGroup(device) && groupMembers.length" class="group-wrapper">
            <SpeakerCard
              :device="device"
              :state="store.getState(device)"
              @toggle-play-pause="store.togglePlayPause(device)"
              @stop="store.stop(device)"
              @next="store.next(device)"
              @prev="store.prev(device)"

              @cycle-repeat="store.cycleRepeat(device)"
              @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
              @volume-change="onVolumeChange"
              :volume-locked="store.isVolumeLocked(device)"
              @toggle-volume-lock="store.toggleVolumeLock(device)"
              @jump-to-track="(d: Device, i: number) => store.jumpToTrack(d, i)"
              @transfer="(from: Device, to: Device) => store.transfer(from, to)"
            />
            <!-- Always show group members when group is active -->
            <div class="group-members">
              <SpeakerCard
                v-for="member in getGroupMembers(device.slug)"
                :key="`${member.slug}:${member.type}`"
                :device="member"
                :state="store.getState(member)"
                @toggle-play-pause="store.togglePlayPause(member)"
                @stop="store.stop(member)"
                @next="store.next(member)"
                @prev="store.prev(member)"
  
                @cycle-repeat="store.cycleRepeat(member)"
                @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
                @volume-change="onVolumeChange"
                :volume-locked="store.isVolumeLocked(member)"
                @toggle-volume-lock="store.toggleVolumeLock(member)"
                @jump-to-track="(d: Device, i: number) => store.jumpToTrack(d, i)"
                @transfer="(from: Device, to: Device) => store.transfer(from, to)"
              />
            </div>
          </div>
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
            @jump-to-track="(d: Device, i: number) => store.jumpToTrack(d, i)"
            @transfer="(from: Device, to: Device) => store.transfer(from, to)"
          />
        </template>
      </div>

      <!-- Idle speakers -->
      <div v-if="idleSpeakers.length" class="speakers-grid">
        <template v-for="device in idleSpeakers" :key="`${device.slug}:${device.type}`">
          <div v-if="isGroup(device)" class="group-wrapper" :class="{ collapsed: !isExpanded(device) && memberCount(device.slug) > 0 }">
            <SpeakerCard
              :device="device"
              :state="store.getState(device)"
              @toggle-play-pause="store.togglePlayPause(device)"
              @stop="store.stop(device)"
              @next="store.next(device)"
              @prev="store.prev(device)"

              @cycle-repeat="store.cycleRepeat(device)"
              @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
              @volume-change="onVolumeChange"
              :volume-locked="store.isVolumeLocked(device)"
              @toggle-volume-lock="store.toggleVolumeLock(device)"
              @jump-to-track="(d: Device, i: number) => store.jumpToTrack(d, i)"
              @transfer="(from: Device, to: Device) => store.transfer(from, to)"
            />
            <!-- Expand/collapse button -->
            <button
              v-if="memberCount(device.slug) > 0"
              class="expand-btn"
              @click="toggleGroup(device.slug)"
            >
              <i :class="isExpanded(device) ? 'mdi mdi-chevron-up' : 'mdi mdi-chevron-down'"></i>
              <span>{{ memberCount(device.slug) }} {{ memberCount(device.slug) === 1 ? 'speaker' : 'speakers' }}</span>
            </button>
            <!-- Expanded members -->
            <div v-if="getGroupMembers(device.slug).length" class="group-members">
              <SpeakerCard
                v-for="member in getGroupMembers(device.slug)"
                :key="`${member.slug}:${member.type}`"
                :device="member"
                :state="store.getState(member)"
                @toggle-play-pause="store.togglePlayPause(member)"
                @stop="store.stop(member)"
                @next="store.next(member)"
                @prev="store.prev(member)"
  
                @cycle-repeat="store.cycleRepeat(member)"
                @set-sleep="(d: any, m: number) => store.setSleep(d, m)"
                @volume-change="onVolumeChange"
                :volume-locked="store.isVolumeLocked(member)"
                @toggle-volume-lock="store.toggleVolumeLock(member)"
                @jump-to-track="(d: Device, i: number) => store.jumpToTrack(d, i)"
                @transfer="(from: Device, to: Device) => store.transfer(from, to)"
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
            @jump-to-track="(d: Device, i: number) => store.jumpToTrack(d, i)"
            @transfer="(from: Device, to: Device) => store.transfer(from, to)"
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
