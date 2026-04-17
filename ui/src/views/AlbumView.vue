<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TrackList from '../components/TrackList.vue'
import SpeakerPicker from '../components/SpeakerPicker.vue'
import { getAlbum, type AlbumDetail, type Track } from '../api/music'
import { createPlaylist, listPlaylists, deletePlaylist, type SavedPlaylist } from '../api/playlists'
import { onImgError } from '../utils/imgFallback'
import { usePlayerStore } from '../stores/player'
import { useDevicesStore } from '../stores/devices'
import type { PlayOptions } from '../components/SpeakerPicker.vue'
import AddToPlaylist from '../components/AddToPlaylist.vue'

const route = useRoute()
const router = useRouter()
const player = usePlayerStore()
const devicesStore = useDevicesStore()

const album = ref<AlbumDetail | null>(null)
const loading = ref(true)
const showPicker = ref(false)
const pendingTrack = ref<Track | null>(null)
const playAll = ref(false)
const savedPlaylists = ref<SavedPlaylist[]>([])
const saving = ref(false)
const showAddToPlaylist = ref(false)
const playlistTrack = ref<Track | null>(null)

function onAddToPlaylist(track: Track) {
  playlistTrack.value = track
  showAddToPlaylist.value = true
}

const savedMatch = computed(() =>
  savedPlaylists.value.find(p => p.name === album.value?.title)
)
const isFavorited = computed(() => !!savedMatch.value)

const totalDuration = computed(() => {
  if (!album.value) return ''
  let secs = 0
  for (const t of album.value.tracks) {
    if (!t.duration) continue
    const parts = t.duration.split(':').map(Number)
    if (parts.length === 2) secs += parts[0] * 60 + parts[1]
    else if (parts.length === 3) secs += parts[0] * 3600 + parts[1] * 60 + parts[2]
  }
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  if (h > 0) return `${h} hr ${m} min`
  return `${m} min`
})

devicesStore.fetchDevices()

async function loadSavedPlaylists() {
  savedPlaylists.value = await listPlaylists()
}

async function toggleFavorite() {
  if (!album.value) return
  saving.value = true
  try {
    if (isFavorited.value && savedMatch.value) {
      await deletePlaylist(savedMatch.value.id)
    } else {
      await createPlaylist(album.value.title, album.value.tracks)
    }
    await loadSavedPlaylists()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const browseId = route.params.browseId as string
  const [a] = await Promise.all([
    getAlbum(browseId),
    loadSavedPlaylists(),
  ])
  album.value = a
  loading.value = false
})

function onPlayTrack(track: Track) {
  playAll.value = false
  pendingTrack.value = track
  showPicker.value = true
}

function onPlayAll() {
  playAll.value = true
  forceShuffle.value = false
  showPicker.value = true
}

const forceShuffle = ref(false)

function onShuffleAll() {
  playAll.value = true
  forceShuffle.value = true
  showPicker.value = true
}

async function onSelectSpeaker(opts: PlayOptions) {
  const { device, shuffle, repeat } = opts
  if (playAll.value && album.value?.audioPlaylistId) {
    await player.playYtPlaylist(album.value.audioPlaylistId, device, { shuffle, repeat }, {
      title: album.value.title,
      author: album.value.artists?.join(', '),
      thumbnail: album.value.thumbnail,
    })
  } else if (pendingTrack.value) {
    await player.playTrack(pendingTrack.value, device, { shuffle, repeat })
    pendingTrack.value = null
  }
}
</script>

<template>
  <div class="album-view">
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
    </div>

    <template v-else-if="album">
      <!-- Hero header -->
      <div class="hero">
        <div class="hero-bg" :style="album.thumbnail ? { backgroundImage: `url(${album.thumbnail})` } : {}"></div>
        <div class="hero-content">
          <button class="back-btn" @click="router.back()">
            <i class="mdi mdi-chevron-left"></i>
          </button>
          <div class="hero-body">
            <img
              v-if="album.thumbnail"
              :src="album.thumbnail"
              class="hero-thumb"
              alt=""
              @error="onImgError"
            />
            <div class="hero-thumb placeholder img-fallback" :style="{ display: album.thumbnail ? 'none' : 'flex' }">
              <i class="mdi mdi-album"></i>
            </div>
            <div class="hero-info">
              <div class="hero-type">Album</div>
              <h1 class="hero-title">{{ album.title }}</h1>
              <div class="hero-meta">
                <span>{{ album.artists?.join(', ') }}</span>
                <span class="dot" v-if="album.year">&middot;</span>
                <span v-if="album.year">{{ album.year }}</span>
                <span class="dot" v-if="album.trackCount">&middot;</span>
                <span v-if="album.trackCount">{{ album.trackCount }} tracks</span>
                <span class="dot" v-if="totalDuration">&middot;</span>
                <span v-if="totalDuration">{{ totalDuration }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions bar -->
      <div class="actions-bar">
        <button class="play-btn" @click="onPlayAll">
          <i class="mdi mdi-play"></i>
          Play
        </button>
        <button class="shuffle-btn" @click="onShuffleAll">
          <i class="mdi mdi-shuffle-variant"></i>
          Shuffle
        </button>
        <button
          class="icon-btn"
          :class="{ favorited: isFavorited }"
          :disabled="saving"
          @click="toggleFavorite"
        >
          <i :class="isFavorited ? 'mdi mdi-heart' : 'mdi mdi-heart-outline'"></i>
        </button>
      </div>

      <!-- Track list -->
      <div class="tracks-section">
        <TrackList :tracks="album.tracks" :numbered="true" @play="onPlayTrack" @add-to-playlist="onAddToPlaylist" />
      </div>
    </template>

    <SpeakerPicker
      v-model:visible="showPicker"
      :force-shuffle="forceShuffle"
      @select="onSelectSpeaker"
    />
    <AddToPlaylist
      v-model:visible="showAddToPlaylist"
      :track="playlistTrack"
    />
  </div>
</template>

<style scoped>
.album-view {
  margin-top: -20px;
}

.hero {
  position: relative;
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  filter: blur(40px) saturate(1.5);
  transform: scale(1.3);
  opacity: 0.4;
}

.hero-content {
  position: relative;
  padding: 24px 16px 20px;
}

.back-btn {
  border: none;
  background: var(--surface-dim);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 1.4rem;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  transition: background 0.15s;
}

.back-btn:hover {
  background: var(--surface-dim);
}

.hero-body {
  display: flex;
  gap: 16px;
  align-items: flex-end;
}

.hero-thumb {
  width: 140px;
  height: 140px;
  border-radius: 10px;
  object-fit: cover;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
  flex-shrink: 0;
}

.hero-thumb.placeholder {
  background: rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255, 255, 255, 0.5);
  font-size: 3rem;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.hero-info {
  flex: 1;
  min-width: 0;
  padding-bottom: 4px;
}

.hero-type {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
  margin-bottom: 2px;
}

.hero-title {
  font-size: 1.4rem;
  font-weight: 800;
  line-height: 1.2;
  margin-bottom: 6px;
  letter-spacing: -0.01em;
}

.hero-meta {
  font-size: 0.8rem;
  color: var(--text-secondary);
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.dot {
  color: var(--text-secondary);
}

.actions-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
}

.play-btn,
.shuffle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: 24px;
  border: none;
  font-size: 0.85rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: transform 0.1s;
}

.play-btn:active,
.shuffle-btn:active {
  transform: scale(0.96);
}

.play-btn {
  background: var(--p-primary-color, #6366f1);
  color: white;
}

.play-btn i {
  font-size: 1.1rem;
}

.shuffle-btn {
  background: var(--surface-dim);
  color: var(--text-primary);
}

.shuffle-btn i {
  font-size: 1rem;
}

.icon-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.3rem;
  color: var(--text-secondary);
  transition: color 0.15s;
  margin-left: auto;
}

.icon-btn:hover {
  color: var(--text-primary);
}

.icon-btn.favorited {
  color: #ef4444;
}

.icon-btn:disabled {
  opacity: 0.4;
}

.tracks-section {
  padding: 0 16px 16px;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 80px 16px;
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--p-primary-color, #6366f1);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
