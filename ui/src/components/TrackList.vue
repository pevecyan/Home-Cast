<script setup lang="ts">
import type { Track } from '../api/music'
import { onImgError } from '../utils/imgFallback'

defineProps<{
  tracks: Track[]
  loading?: boolean
  numbered?: boolean
}>()

const emit = defineEmits<{
  play: [track: Track]
  addToPlaylist: [track: Track]
}>()
</script>

<template>
  <div class="track-list">
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading...</span>
    </div>
    <div
      v-for="(track, idx) in tracks"
      :key="track.videoId"
      class="track-item"
      @click="emit('play', track)"
    >
      <span v-if="numbered" class="track-num">{{ idx + 1 }}</span>
      <div class="track-thumb-wrap">
        <img
          v-if="track.thumbnail"
          :src="track.thumbnail"
          class="track-thumb"
          alt=""
          @error="onImgError"
        />
        <div class="track-thumb placeholder img-fallback" :style="{ display: track.thumbnail ? 'none' : 'flex' }">
          <i class="mdi mdi-music-note"></i>
        </div>
        <div class="track-play-overlay">
          <i class="mdi mdi-play"></i>
        </div>
      </div>
      <div class="track-info">
        <div class="track-title">{{ track.title }}</div>
        <div class="track-artist">
          {{ track.artists?.join(', ') }}
          <span v-if="track.duration" class="track-duration">
            &middot; {{ track.duration }}
          </span>
        </div>
      </div>
      <button
        class="track-add-btn"
        @click.stop="emit('addToPlaylist', track)"
        title="Add to playlist"
      >
        <i class="mdi mdi-playlist-plus"></i>
      </button>
    </div>
  </div>
</template>

<style scoped>
.track-list {
  display: flex;
  flex-direction: column;
}

.track-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.track-item:hover {
  background: var(--hover-bg);
}

.track-thumb-wrap {
  position: relative;
  width: 48px;
  height: 48px;
  flex-shrink: 0;
}

.track-thumb {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  object-fit: cover;
}

.track-thumb.placeholder {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.2rem;
}

.track-play-overlay {
  position: absolute;
  inset: 0;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s;
}

.track-play-overlay i {
  color: white;
  font-size: 1.4rem;
}

.track-item:hover .track-play-overlay {
  opacity: 1;
}

.track-num {
  width: 24px;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-secondary);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.track-info {
  flex: 1;
  min-width: 0;
}

.track-title {
  font-weight: 500;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track-artist {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track-add-btn {
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 1.2rem;
  cursor: pointer;
  padding: 4px;
  border-radius: 50%;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, background 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.track-item:hover .track-add-btn {
  opacity: 1;
}

.track-add-btn:hover {
  color: var(--p-primary-color, #6366f1);
  background: var(--hover-bg);
}

/* Always show on touch devices */
@media (hover: none) {
  .track-add-btn {
    opacity: 1;
  }
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px;
  color: var(--text-secondary);
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-color);
  border-top-color: var(--p-primary-color, #6366f1);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
