<script setup lang="ts">
import { computed, ref } from 'vue'
import Slider from 'primevue/slider'
import { useDevicesStore } from '../stores/devices'
import { useLocalPlayerStore } from '../stores/localPlayer'
import { onImgErrorWithFallback } from '../utils/imgFallback'
import { deviceIcon } from '../utils/deviceIcon'
import type { Device } from '../api/devices'

const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ close: [] }>()

const devicesStore = useDevicesStore()
const localPlayer = useLocalPlayerStore()

const isLocal = computed(() => props.device.type === 'local')
const state = computed(() => devicesStore.getState(props.device))
const queue = computed(() => state.value?.queue)
const currentTrack = computed(() => queue.value?.currentTrack ?? null)
const isActive = computed(() => state.value?.status === 'PLAYING' || state.value?.status === 'PAUSED')
const isPlaying = computed(() => state.value?.status === 'PLAYING')
const hasQueue = computed(() => !!queue.value)
const canNext = computed(() => state.value?.canNext ?? false)
const canPrev = computed(() => state.value?.canPrev ?? false)
const repeatMode = computed(() => queue.value?.repeat ?? 'off')

const title = computed(() => currentTrack.value?.title || state.value?.nowPlaying?.title || 'Nothing playing')
const artist = computed(() => currentTrack.value?.artists?.join(', ') || '')
const thumb = computed(() => currentTrack.value?.thumbnail || state.value?.nowPlaying?.thumbnail)

// A cover to fall back to when the current track's own thumbnail fails to load:
// the playlist cover the backend backfilled (base64 data: URI on tracks that had
// no thumbnail of their own), else the first queue track that does have one.
const fallbackCover = computed(() => {
  const tracks = queue.value?.tracks ?? []
  const dataUri = tracks.find(t => t.thumbnail?.startsWith('data:'))?.thumbnail
  return dataUri || tracks.find(t => t.thumbnail)?.thumbnail
})

// --- Progress (local only — the backend does not expose position for speakers) ---
const showProgress = computed(() => isLocal.value && !!currentTrack.value)
const position = computed(() => localPlayer.position)
const duration = computed(() => localPlayer.duration)
const progressModel = computed({
  get: () => (duration.value ? (position.value / duration.value) * 100 : 0),
  set: (pct: number) => {
    if (duration.value) localPlayer.seek((pct / 100) * duration.value)
  },
})

function fmt(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// --- Volume ---
const volumeModel = computed({
  get: () => Math.round((state.value?.volume ?? 0) * 100),
  set: (v: number) => devicesStore.changeVolume(props.device, v / 100),
})

const repeatIcon = computed(() =>
  repeatMode.value === 'one' ? 'mdi mdi-repeat-once' : 'mdi mdi-repeat',
)

function togglePlayPause() { devicesStore.togglePlayPause(props.device) }
function next() { devicesStore.next(props.device) }
function prev() { devicesStore.prev(props.device) }
function cycleRepeat() { devicesStore.cycleRepeat(props.device) }
function jumpTo(i: number) { devicesStore.jumpToTrack(props.device, i) }

// --- Collapse-on-scroll ---
// The moment the user starts scrolling the queue, shrink the cover art to its
// compact size and keep it there for the rest of this session (the overlay is
// re-created each time it opens, so `collapsed` resets to false on reopen).
// This is a one-way latch: because the art lives outside the scroll container,
// interpolating its size against scrollTop would reflow the queue and feed back
// into the scroll position — a latch avoids that jitter entirely.
const collapsed = ref(false)
function onQueueScroll(e: Event) {
  if (!collapsed.value && (e.target as HTMLElement).scrollTop > 0) {
    collapsed.value = true
  }
}
</script>

<template>
  <div class="np-overlay" @click.self="emit('close')">
    <div class="np-sheet">
      <header class="np-header">
        <button class="np-icon-btn" @click="emit('close')" title="Close">
          <i class="mdi mdi-close"></i>
        </button>
        <div class="np-device">
          <i :class="deviceIcon(device.type)"></i>
          <span>{{ device.friendly_name }}</span>
        </div>
        <span class="np-spacer"></span>
      </header>

      <div class="np-top" :class="{ collapsed }">
      <div class="np-art-wrap">
        <img
          v-if="thumb"
          :key="thumb"
          :src="thumb"
          class="np-art"
          alt=""
          @error="onImgErrorWithFallback(() => fallbackCover)"
        />
        <div class="np-art placeholder img-fallback" :style="{ display: thumb ? 'none' : 'flex' }">
          <i class="mdi mdi-music"></i>
        </div>
      </div>

      <div class="np-meta">
        <div class="np-title">{{ title }}</div>
        <div v-if="artist" class="np-artist">{{ artist }}</div>
        <div v-if="queue" class="np-pos">
          Track {{ (queue.currentIndex ?? 0) + 1 }} of {{ queue.trackCount }}
        </div>
      </div>

      <!-- Progress bar (local play only) -->
      <div v-if="showProgress" class="np-progress">
        <span class="np-time">{{ fmt(position) }}</span>
        <Slider v-model="progressModel" :min="0" :max="100" class="np-progress-slider" />
        <span class="np-time">{{ fmt(duration) }}</span>
      </div>

      <!-- Transport. Three equal zones keep play/pause dead center regardless
           of how many buttons flank it. -->
      <div class="np-controls">
        <div class="np-ctrl-side np-ctrl-side--left">
          <button
            class="np-ctrl"
            :class="{ 'ctrl-active': repeatMode !== 'off' }"
            :disabled="!hasQueue"
            @click="cycleRepeat"
            title="Repeat"
          >
            <i :class="repeatIcon"></i>
          </button>
          <button class="np-ctrl" :disabled="!canPrev" @click="prev" title="Previous">
            <i class="mdi mdi-skip-previous"></i>
          </button>
        </div>
        <button class="np-ctrl np-play" :disabled="!isActive" @click="togglePlayPause">
          <i :class="isPlaying ? 'mdi mdi-pause' : 'mdi mdi-play'"></i>
        </button>
        <div class="np-ctrl-side np-ctrl-side--right">
          <button class="np-ctrl" :disabled="!canNext" @click="next" title="Next">
            <i class="mdi mdi-skip-next"></i>
          </button>
        </div>
      </div>

      <!-- Volume -->
      <div class="np-volume">
        <i class="mdi mdi-volume-low"></i>
        <Slider v-model="volumeModel" :min="0" :max="100" class="np-volume-slider" />
        <i class="mdi mdi-volume-high"></i>
      </div>
      </div>

      <!-- Queue (only this scrolls) -->
      <div v-if="queue?.tracks?.length" class="np-queue" @scroll="onQueueScroll">
        <div class="np-queue-head">Up next</div>
        <div
          v-for="(t, i) in queue.tracks"
          :key="t.videoId + i"
          class="np-queue-item"
          :class="{ active: i === queue.currentIndex }"
          @click="jumpTo(i)"
        >
          <img
            v-if="t.thumbnail"
            :key="t.thumbnail"
            :src="t.thumbnail"
            class="np-q-thumb"
            alt=""
            @error="onImgErrorWithFallback(() => fallbackCover)"
          />
          <div class="np-q-thumb placeholder img-fallback" :style="{ display: t.thumbnail ? 'none' : 'flex' }">
            <i class="mdi mdi-music-note"></i>
          </div>
          <div class="np-q-info">
            <div class="np-q-title">{{ t.title }}</div>
            <div class="np-q-artist">{{ t.artists?.join(', ') }}</div>
          </div>
          <i v-if="i === queue.currentIndex" class="mdi mdi-volume-high np-q-playing"></i>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.np-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: np-fade 0.18s ease-out;
}

.np-sheet {
  width: 100%;
  max-width: 460px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--card-bg);
  border-radius: 18px;
  padding: 12px 20px 20px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
  animation: np-pop 0.2s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Pinned block: art, title, progress, transport, volume — never scrolls.
   Gets `.collapsed` once the user starts scrolling the queue, which shrinks the
   cover art so it doesn't hog the screen while browsing. */
.np-top {
  flex-shrink: 0;
}

@keyframes np-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes np-pop {
  from { transform: scale(0.96); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

/* Mobile: keep the natural bottom-sheet feel */
@media (max-width: 768px) {
  .np-overlay {
    align-items: flex-end;
    padding: 0;
  }

  .np-sheet {
    max-width: 100%;
    max-height: 96vh;
    padding-top: 6px;
    border-radius: 18px 18px 0 0;
    animation: np-rise 0.22s ease-out;
  }

  .np-art-wrap {
    margin: 4px 0 12px;
  }
  .np-top.collapsed .np-art-wrap {
    margin: 2px 0 8px;
  }

  .np-art {
    width: min(58vw, 240px);
    height: min(58vw, 240px);
  }
  /* Collapsed size (76px) is inherited from the base rule. */

  @keyframes np-rise {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }
}

.np-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.np-icon-btn {
  border: none;
  background: none;
  color: var(--text-primary);
  font-size: 1.6rem;
  cursor: pointer;
  line-height: 1;
  display: flex;
}

.np-device {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.np-spacer { width: 32px; }

.np-art-wrap {
  display: flex;
  justify-content: center;
  margin: 8px 0 20px;
  transition: margin 0.2s ease;
}
.np-top.collapsed .np-art-wrap {
  margin: 4px 0 12px;
}

.np-art {
  width: min(70vw, 300px);
  height: min(70vw, 300px);
  border-radius: 14px;
  object-fit: cover;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
  transition: width 0.2s ease, height 0.2s ease;
}
.np-top.collapsed .np-art {
  width: 76px;
  height: 76px;
}

.np-art.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 3rem;
}

.np-meta { text-align: center; margin-bottom: 16px; }

.np-title {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.np-artist {
  font-size: 0.95rem;
  color: var(--text-secondary);
  margin-top: 4px;
}

.np-pos {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 6px;
}

.np-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.np-progress-slider { flex: 1; }

.np-time {
  font-size: 0.7rem;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
  min-width: 34px;
  text-align: center;
}

.np-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18px;
  margin-bottom: 20px;
}
/* Equal-width side zones so the play button stays dead center even though the
   left side has more buttons (repeat + prev) than the right (next). */
.np-ctrl-side {
  flex: 1 1 0;
  display: flex;
  align-items: center;
  gap: 18px;
}
.np-ctrl-side--left { justify-content: flex-end; }
.np-ctrl-side--right { justify-content: flex-start; }

.np-ctrl {
  border: none;
  background: none;
  color: var(--text-primary);
  font-size: 1.8rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.np-ctrl:disabled { opacity: 0.3; cursor: default; }

.np-ctrl.ctrl-active { color: var(--p-primary-color, #6366f1); }

.np-play {
  width: 62px;
  height: 62px;
  border-radius: 50%;
  background: var(--p-primary-color, #6366f1);
  color: #fff;
  font-size: 2rem;
}


.np-volume {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: var(--text-secondary);
}

.np-volume-slider { flex: 1; }

/* Only the queue scrolls */
.np-queue {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin: 0 -8px;
  padding: 0 8px;
}

.np-queue-head {
  position: sticky;
  top: 0;
  background: var(--card-bg);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 6px 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.np-queue-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px;
  border-radius: 8px;
  cursor: pointer;
}

.np-queue-item:hover { background: var(--hover-bg); }
.np-queue-item.active { background: var(--surface-dim); }

.np-q-thumb {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.np-q-thumb.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
}

.np-q-info { flex: 1; min-width: 0; }

.np-q-title {
  font-size: 0.85rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.np-q-artist {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.np-q-playing { color: var(--p-primary-color, #6366f1); }
</style>
