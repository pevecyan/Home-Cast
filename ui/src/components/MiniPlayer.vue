<script setup lang="ts">
import { computed, ref } from 'vue'
import { useDevicesStore } from '../stores/devices'
import { usePlayerStore } from '../stores/player'
import { onImgError } from '../utils/imgFallback'

const devicesStore = useDevicesStore()
const playerStore = usePlayerStore()
const currentIndex = ref(0)

const activeSpeakers = computed(() => {
  return devicesStore.devices.filter(d => {
    const s = devicesStore.getState(d)
    return s?.status === 'PLAYING' || s?.status === 'PAUSED'
  })
})

const hasSpeakers = computed(() => activeSpeakers.value.length > 0)
const multiSpeakers = computed(() => activeSpeakers.value.length > 1)

const safeIndex = computed(() => {
  if (activeSpeakers.value.length === 0) return 0
  return Math.min(currentIndex.value, activeSpeakers.value.length - 1)
})

const currentDevice = computed(() => activeSpeakers.value[safeIndex.value])
const currentState = computed(() =>
  currentDevice.value ? devicesStore.getState(currentDevice.value) : undefined
)

const trackTitle = computed(() =>
  currentState.value?.queue?.currentTrack?.title
  || currentState.value?.nowPlaying?.title
  || 'Unknown'
)

const trackArtist = computed(() =>
  currentState.value?.queue?.currentTrack?.artists?.join(', ') || ''
)

const trackThumb = computed(() =>
  currentState.value?.queue?.currentTrack?.thumbnail
  || currentState.value?.nowPlaying?.thumbnail
)

const isPlaying = computed(() => currentState.value?.status === 'PLAYING')

const typeIcon = computed(() =>
  currentDevice.value?.type === 'sonos' ? 'mdi mdi-speaker' : 'mdi mdi-cast-audio'
)


function togglePlayPause() {
  if (currentDevice.value) {
    devicesStore.togglePlayPause(currentDevice.value)
  }
}

function prev() {
  if (safeIndex.value > 0) currentIndex.value = safeIndex.value - 1
}

function next() {
  if (safeIndex.value < activeSpeakers.value.length - 1) currentIndex.value = safeIndex.value + 1
}

let touchStartX = 0

function onTouchStart(e: TouchEvent) {
  touchStartX = e.touches[0].clientX
}

function onTouchEnd(e: TouchEvent) {
  const diff = e.changedTouches[0].clientX - touchStartX
  if (Math.abs(diff) > 50) {
    if (diff < 0) next()
    else prev()
  }
}
</script>

<template>
  <!-- Loading state when user initiates playback -->
  <div v-if="playerStore.isLoading && !hasSpeakers" class="mini-player">
    <div class="mini-loading">
      <i class="pi pi-spin pi-spinner"></i>
      <span>Loading track...</span>
    </div>
  </div>

  <div
    v-if="hasSpeakers"
    class="mini-player"
    @touchstart="onTouchStart"
    @touchend="onTouchEnd"
  >
    <!-- Prev arrow -->
    <button
      v-if="multiSpeakers"
      class="nav-arrow"
      :class="{ disabled: safeIndex === 0 }"
      @click="prev"
    >
      <i class="mdi mdi-chevron-left"></i>
    </button>

    <!-- Thumbnail -->
    <img
      v-if="trackThumb"
      :src="trackThumb"
      class="mini-thumb"
      alt=""
      @error="onImgError"
    />
    <div class="mini-thumb placeholder img-fallback" v-else>
      <i class="mdi mdi-music-note"></i>
    </div>

    <!-- Two-line info: speaker on top, track below -->
    <div class="mini-info">
      <div class="mini-speaker">
        <i :class="typeIcon" class="mini-speaker-icon"></i>
        <span class="mini-speaker-name">{{ currentDevice?.friendly_name }}</span>
        <!-- Dots inline with speaker name when multi -->
        <span v-if="multiSpeakers" class="dots">
          <span
            v-for="(_, i) in activeSpeakers"
            :key="i"
            class="dot"
            :class="{ active: i === safeIndex }"
            @click="currentIndex = i"
          ></span>
        </span>
      </div>
      <div class="mini-track">
        <span class="mini-title">{{ trackTitle }}</span>
        <span v-if="trackArtist" class="mini-sep">&middot;</span>
        <span v-if="trackArtist" class="mini-artist">{{ trackArtist }}</span>
      </div>
    </div>

    <!-- Play/Pause button -->
    <button class="play-pause-btn" @click="togglePlayPause">
      <i :class="isPlaying ? 'mdi mdi-pause' : 'mdi mdi-play'"></i>
    </button>

    <!-- Next arrow -->
    <button
      v-if="multiSpeakers"
      class="nav-arrow"
      :class="{ disabled: safeIndex === activeSpeakers.length - 1 }"
      @click="next"
    >
      <i class="mdi mdi-chevron-right"></i>
    </button>
  </div>
</template>

<style scoped>
.mini-player {
  position: fixed;
  bottom: 0;
  left: 240px;
  right: 0;
  height: 56px;
  background: var(--card-bg);
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  padding: 0 12px;
  gap: 10px;
  z-index: 99;
  overflow: hidden;
}

.nav-arrow {
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.nav-arrow:hover:not(.disabled) {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.nav-arrow.disabled {
  opacity: 0.3;
  cursor: default;
}

.mini-thumb {
  width: 38px;
  height: 38px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.mini-thumb.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.1rem;
}

.mini-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.mini-speaker {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  color: var(--text-secondary);
  line-height: 1;
  overflow: hidden;
}

.mini-speaker-icon {
  font-size: 0.8rem;
}

.mini-speaker-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 140px;
}

.dots {
  display: inline-flex;
  gap: 4px;
  align-items: center;
  margin-left: 4px;
}

.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--placeholder-color);
  cursor: pointer;
  transition: background 0.15s, transform 0.15s;
}

.dot.active {
  background: var(--p-primary-color, #6366f1);
  transform: scale(1.3);
}

.mini-track {
  display: flex;
  align-items: center;
  gap: 5px;
  min-width: 0;
  line-height: 1;
  overflow: hidden;
}

.mini-title {
  font-weight: 600;
  font-size: 0.8rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex-shrink: 1;
}

.mini-sep {
  color: var(--text-secondary);
  font-size: 0.75rem;
  flex-shrink: 0;
}

.mini-artist {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex-shrink: 1;
}

.play-pause-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: var(--surface-dim);
  color: var(--text-primary);
  font-size: 1.1rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
  padding-top:3px;
}

.play-pause-btn:hover {
  background: var(--hover-bg);
}

.mini-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

@media (max-width: 768px) {
  .mini-player {
    left: 0;
    max-width: 100vw;
    box-sizing: border-box;
  }

  .mini-speaker-name {
    max-width: 100px;
  }
}
</style>
