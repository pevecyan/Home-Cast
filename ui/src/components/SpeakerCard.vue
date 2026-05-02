<script setup lang="ts">
import { computed, ref } from 'vue'
import Slider from 'primevue/slider'
import Button from 'primevue/button'
import SpeakerPicker from './SpeakerPicker.vue'
import type { Device, DeviceState } from '../api/devices'
import { onImgError } from '../utils/imgFallback'
import { sleepEnabled, volumeLockEnabled } from '../utils/settings'

const props = defineProps<{
  device: Device
  state?: DeviceState
  volumeLocked?: boolean
}>()

const emit = defineEmits<{
  togglePlayPause: [device: Device]
  stop: [device: Device]
  next: [device: Device]
  prev: [device: Device]
  cycleRepeat: [device: Device]
  setSleep: [device: Device, minutes: number]
  volumeChange: [device: Device, volume: number]
  toggleVolumeLock: [device: Device]
  jumpToTrack: [device: Device, index: number]
  transfer: [fromDevice: Device, toDevice: Device]
}>()

const volumePercent = computed({
  get: () => Math.round((props.state?.volume ?? 0) * 100),
  set: (val: number) => emit('volumeChange', props.device, val / 100),
})

const isPlaying = computed(() => props.state?.status === 'PLAYING')
const isPaused = computed(() => props.state?.status === 'PAUSED')
const isActive = computed(() => isPlaying.value || isPaused.value)
const playPauseIcon = computed(() => isPlaying.value ? 'pi pi-pause' : 'pi pi-play')
const currentTrack = computed(() => props.state?.queue?.currentTrack)
const queueInfo = computed(() => props.state?.queue)
const hasQueue = computed(() => !!queueInfo.value)
const nowPlaying = computed(() => props.state?.nowPlaying)

const repeatMode = computed(() => props.state?.queue?.repeat ?? 'off')
const repeatIcon = computed(() =>
  repeatMode.value === 'one' ? 'mdi mdi-repeat-once' : 'mdi mdi-repeat'
)
const sleepTimer = computed(() => props.state?.sleepTimer)
const sleepRemaining = computed(() => {
  if (!sleepTimer.value) return ''
  const ends = new Date(sleepTimer.value.endsAt).getTime()
  const now = Date.now()
  const mins = Math.max(0, Math.ceil((ends - now) / 60000))
  if (mins <= 0) return ''
  return `${mins} min`
})
const showSleepMenu = ref(false)
const sleepOptions = [15, 30, 45, 60]
const showPlaylist = ref(false)
const showTransferPicker = ref(false)

const typeIcon = computed(() =>
  props.device.type === 'sonos' ? 'mdi mdi-speaker' : 'mdi mdi-cast-audio'
)
</script>

<template>
  <div class="speaker-card">
    <div class="speaker-header">
      <div class="speaker-info">
        <i :class="typeIcon" class="speaker-icon"></i>
        <div>
          <div class="speaker-name">{{ device.friendly_name }}</div>
          <div class="speaker-type">{{ device.type }}</div>
        </div>
      </div>
      <div v-if="isActive && sleepEnabled" class="sleep-wrapper">
        <div class="sleep-icon-btn" :class="{ active: !!sleepTimer }" @click="showSleepMenu = !showSleepMenu">
          <i class="mdi mdi-power-sleep"></i>
          <span v-if="sleepRemaining" class="sleep-remaining">{{ sleepRemaining }}</span>
        </div>
        <div v-if="showSleepMenu" class="sleep-menu">
          <button
            v-for="m in sleepOptions"
            :key="m"
            class="sleep-option"
            @click="$emit('setSleep', device, m); showSleepMenu = false"
          >
            {{ m }} min
          </button>
          <button
            v-if="sleepTimer"
            class="sleep-option cancel"
            @click="$emit('setSleep', device, 0); showSleepMenu = false"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="currentTrack"
      class="now-playing"
      :class="{ clickable: (queueInfo?.trackCount ?? 0) > 1 }"
      @click="(queueInfo?.trackCount ?? 0) > 1 && (showPlaylist = !showPlaylist)"
    >
      <img
        v-if="currentTrack.thumbnail"
        :src="currentTrack.thumbnail"
        class="np-thumb"
        alt=""
        @error="onImgError"
      />
      <div class="np-thumb placeholder img-fallback" :style="{ display: currentTrack.thumbnail ? 'none' : 'flex' }">
        <i class="mdi mdi-music-note"></i>
      </div>
      <div class="np-info">
        <div class="np-title">{{ currentTrack.title }}</div>
        <div class="np-artist">{{ currentTrack.artists?.join(', ') }}</div>
        <div v-if="queueInfo && (queueInfo.trackCount > 1 || repeatMode !== 'off')" class="np-queue">
          <template v-if="queueInfo.trackCount > 1">
            Track {{ queueInfo.currentIndex + 1 }} of {{ queueInfo.trackCount }}
          </template>
          <span v-if="repeatMode !== 'off'" class="np-modes">
            <template v-if="queueInfo.trackCount > 1">&middot;</template>
            <i v-if="repeatMode === 'all'" class="mdi mdi-repeat"></i>
            <i v-if="repeatMode === 'one'" class="mdi mdi-repeat-once"></i>
          </span>
        </div>
      </div>
    </div>

    <div v-if="!currentTrack && nowPlaying && isActive" class="now-playing">
      <img
        v-if="nowPlaying.thumbnail"
        :src="nowPlaying.thumbnail"
        class="np-thumb"
        alt=""
        @error="onImgError"
      />
      <div class="np-thumb placeholder img-fallback" :style="{ display: nowPlaying.thumbnail ? 'none' : 'flex' }">
        <i class="mdi mdi-radio"></i>
      </div>
      <div class="np-info">
        <div class="np-title">{{ nowPlaying.title }}</div>
        <div class="np-artist">Live</div>
      </div>
    </div>

    <div class="speaker-controls">
      <div class="volume-row">
        <i class="mdi mdi-volume-low"></i>
        <Slider v-model="volumePercent" :min="0" :max="100" class="volume-slider" :disabled="volumeLockEnabled && volumeLocked" />
        <i class="mdi mdi-volume-high"></i>
        <div
          v-if="volumeLockEnabled"
          class="volume-lock-btn"
          :class="{ 'mode-active': volumeLocked }"
          @click="$emit('toggleVolumeLock', device)"
        >
          <i :class="volumeLocked ? 'mdi mdi-lock' : 'mdi mdi-lock-open-outline'"></i>
        </div>
      </div>
      <div v-if="isActive" class="button-row">
        <Button
          v-if="isActive && hasQueue"
          icon="pi pi-step-backward"
          rounded
          text
          @click="$emit('prev', device)"
        />
        <Button
          :icon="playPauseIcon"
          rounded
          text
          @click="$emit('togglePlayPause', device)"
        />
        <Button icon="pi pi-stop" rounded text @click="$emit('stop', device)" />
        <Button
          v-if="isActive && hasQueue"
          icon="pi pi-step-forward"
          rounded
          text
          @click="$emit('next', device)"
        />
        <Button
          v-if="isActive && hasQueue"
          :icon="repeatIcon"
          rounded
          text
          :class="{ 'mode-active': repeatMode !== 'off' }"
          @click="$emit('cycleRepeat', device)"
        />
        <Button
          v-if="isActive && hasQueue"
          icon="mdi mdi-cast-audio"
          rounded
          text
          title="Move to another speaker"
          @click="showTransferPicker = true"
        />
      </div>

      <SpeakerPicker
        v-model:visible="showTransferPicker"
        :show-play-options="false"
        @select="({ device: target }) => { $emit('transfer', device, target); showTransferPicker = false }"
      />

      <!-- Playlist panel -->
      <div v-if="showPlaylist && queueInfo?.tracks?.length" class="playlist-panel">
        <div
          v-for="(track, idx) in queueInfo.tracks"
          :key="track.videoId + idx"
          class="playlist-item"
          :class="{ active: idx === queueInfo.currentIndex }"
          @click="$emit('jumpToTrack', device, idx)"
        >
          <img
            v-if="track.thumbnail"
            :src="track.thumbnail"
            class="pl-thumb"
            alt=""
            @error="onImgError"
          />
          <div v-else class="pl-thumb placeholder">
            <i class="mdi mdi-music-note"></i>
          </div>
          <div class="pl-info">
            <div class="pl-title">{{ track.title }}</div>
            <div class="pl-artist">{{ track.artists?.join(', ') }}</div>
          </div>
          <i v-if="idx === queueInfo.currentIndex" class="mdi mdi-volume-high pl-playing-icon"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.speaker-card {
  background: var(--card-bg);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

.speaker-header {
  display: flex;
  justify-content: space-between;
  align-items: top;
  margin-bottom: 12px;
}

.speaker-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.speaker-icon {
  font-size: 1.4rem;
  color: var(--text-secondary);
}

.speaker-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.speaker-type {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.sleep-wrapper {
  position: relative;
}

.sleep-icon-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 8px;
  color: var(--text-secondary);
  opacity: 0.4;
  transition: background 0.15s, color 0.15s, opacity 0.15s;
  font-size: 1rem;
}

.sleep-icon-btn:hover {
  background: var(--hover-bg);
  opacity: 0.7;
}

.sleep-icon-btn.active {
  color: var(--p-primary-color, #6366f1);
  opacity: 1;
}

.sleep-remaining {
  font-size: 0.7rem;
  font-weight: 600;
}

.now-playing {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  margin-bottom: 12px;
  background: var(--subtle-bg);
  border-radius: 10px;
}

.now-playing.clickable {
  cursor: pointer;
  transition: background 0.12s;
}

.now-playing.clickable:hover {
  background: var(--hover-bg);
}

.np-thumb {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.np-thumb.placeholder {
  background: var(--placeholder-bg);
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.2rem;
}

.np-info {
  flex: 1;
  min-width: 0;
}

.np-title {
  font-weight: 600;
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.np-artist {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.np-queue {
  font-size: 0.7rem;
  color: var(--text-secondary);
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.np-modes {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--p-primary-color, #6366f1);
}

.volume-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.volume-row i {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.volume-lock-btn {
  font-size: 0.85rem;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  line-height: 1;
}

.volume-lock-btn.mode-active i {
  color: var(--p-primary-color, #6366f1);
}

.volume-slider {
  flex: 1;
}

.button-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 4px;
}

.mode-active {
  color: var(--p-primary-color, #6366f1) !important;
}

.sleep-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: var(--card-bg);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 4px;
  display: flex;
  gap: 2px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  z-index: 10;
}

.sleep-option {
  border: none;
  background: none;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 0.75rem;
  font-family: inherit;
  cursor: pointer;
  color: var(--text-primary);
  white-space: nowrap;
  transition: background 0.15s;
}

.sleep-option:hover {
  background: var(--hover-bg);
}

.sleep-option.cancel {
  color: #ef4444;
}

.playlist-panel {
  margin-top: 8px;
  border-radius: 10px;
  background: var(--subtle-bg);
  overflow: hidden;
  max-height: 260px;
  overflow-y: auto;
}

.playlist-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  cursor: pointer;
  transition: background 0.12s;
}

.playlist-item:hover {
  background: var(--hover-bg);
}

.playlist-item.active {
  background: var(--hover-bg);
}

.pl-thumb {
  width: 36px;
  height: 36px;
  border-radius: 5px;
  object-fit: cover;
  flex-shrink: 0;
}

.pl-thumb.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1rem;
}

.pl-info {
  flex: 1;
  min-width: 0;
}

.pl-title {
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.playlist-item.active .pl-title {
  color: var(--p-primary-color, #6366f1);
}

.pl-artist {
  font-size: 0.7rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pl-playing-icon {
  font-size: 0.9rem;
  color: var(--p-primary-color, #6366f1);
  flex-shrink: 0;
}
</style>
