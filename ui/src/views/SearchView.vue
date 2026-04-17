<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import SearchBar from '../components/SearchBar.vue'
import TrackList from '../components/TrackList.vue'
import SpeakerPicker from '../components/SpeakerPicker.vue'
import { searchMusic, type Track, type Artist, type Playlist } from '../api/music'
import { usePlayerStore } from '../stores/player'
import { useDevicesStore } from '../stores/devices'
import { useRecentStore } from '../stores/recent'
import { onImgError } from '../utils/imgFallback'
import type { PlayOptions } from '../components/SpeakerPicker.vue'
import AddToPlaylist from '../components/AddToPlaylist.vue'

const router = useRouter()
const player = usePlayerStore()
const devicesStore = useDevicesStore()
const recent = useRecentStore()

const query = ref('')
const filterType = ref('songs')
const results = ref<any[]>([])
const loading = ref(false)
const searched = ref(false)
const showPicker = ref(false)
const pendingTrack = ref<Track | null>(null)
const showAddToPlaylist = ref(false)
const playlistTrack = ref<Track | null>(null)

const showRecent = computed(() => !searched.value && !loading.value && recent.items.length > 0)

devicesStore.fetchDevices()

watch(filterType, () => {
  if (query.value.trim()) {
    onSearch(query.value.trim(), filterType.value)
  }
})

async function onSearch(q: string, type: string) {
  loading.value = true
  searched.value = true
  try {
    results.value = await searchMusic(q, type)
  } finally {
    loading.value = false
  }
}

function onPlayTrack(track: Track) {
  pendingTrack.value = track
  showPicker.value = true
}

async function onSelectSpeaker(opts: PlayOptions) {
  if (pendingTrack.value) {
    await player.playTrack(pendingTrack.value, opts.device, { shuffle: opts.shuffle, repeat: opts.repeat })
    pendingTrack.value = null
  }
}

function onArtistClick(artist: Artist) {
  router.push({ name: 'artist', params: { browseId: artist.browseId } })
}

function onPlaylistClick(playlist: Playlist) {
  router.push({ name: 'playlist', params: { playlistId: playlist.playlistId } })
}

function onAlbumClick(album: any) {
  router.push({ name: 'album', params: { browseId: album.browseId } })
}

function onRecentClick(item: any) {
  if (item.type === 'song') {
    const track: Track = {
      videoId: item.id,
      title: item.title,
      artists: item.subtitle ? item.subtitle.split(', ') : [],
      thumbnail: item.thumbnail,
    }
    onPlayTrack(track)
  } else if (item.type === 'artist') {
    router.push({ name: 'artist', params: { browseId: item.id } })
  } else if (item.type === 'playlist') {
    router.push({ name: 'playlist', params: { playlistId: item.id } })
  } else if (item.type === 'album') {
    router.push({ name: 'album', params: { browseId: item.id } })
  }
}

function onAddToPlaylist(track: Track) {
  playlistTrack.value = track
  showAddToPlaylist.value = true
}
</script>

<template>
  <div class="search-view">
    <h1 class="page-title">Search</h1>

    <SearchBar
      v-model:query="query"
      v-model:filter-type="filterType"
      @search="onSearch"
    />

    <!-- Recent section (before search) -->
    <div v-if="showRecent" class="recent-section">
      <h2 class="section-title">
        <i class="mdi mdi-history"></i> Recently played
      </h2>
      <div class="recent-grid">
        <div
          v-for="item in recent.items"
          :key="`${item.type}:${item.id}`"
          class="recent-card"
          @click="onRecentClick(item)"
        >
          <img
            v-if="item.thumbnail"
            :src="item.thumbnail"
            class="recent-thumb"
            :class="{ round: item.type === 'artist' }"
            alt=""
            @error="onImgError"
          />
          <div class="recent-thumb placeholder img-fallback" :class="{ round: item.type === 'artist' }" :style="{ display: item.thumbnail ? 'none' : 'flex' }">
            <i class="mdi mdi-music-note"></i>
          </div>
          <div class="recent-title">{{ item.title }}</div>
          <div class="recent-sub">{{ item.subtitle }}</div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Searching...</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="searched && !results.length" class="empty-state">
      <i class="mdi mdi-music-note-off"></i>
      <p>No results found</p>
    </div>

    <!-- Song results -->
    <div v-if="!loading && filterType === 'songs' && results.length" class="results-section">
      <TrackList :tracks="results" @play="onPlayTrack" @add-to-playlist="onAddToPlaylist" />
    </div>

    <!-- Artist results -->
    <div v-if="!loading && filterType === 'artists' && results.length" class="results-section">
      <div
        v-for="artist in results"
        :key="artist.browseId"
        class="result-card"
        @click="onArtistClick(artist)"
      >
        <img v-if="artist.thumbnail" :src="artist.thumbnail" class="result-thumb round" alt="" @error="onImgError" />
        <div class="result-thumb placeholder round img-fallback" :style="{ display: artist.thumbnail ? 'none' : 'flex' }">
          <i class="mdi mdi-account-music"></i>
        </div>
        <div class="result-info">
          <div class="result-title">{{ artist.name }}</div>
          <div class="result-sub">Artist</div>
        </div>
        <i class="mdi mdi-chevron-right result-chevron"></i>
      </div>
    </div>

    <!-- Playlist results -->
    <div v-if="!loading && filterType === 'playlists' && results.length" class="results-section">
      <div
        v-for="pl in results"
        :key="pl.playlistId"
        class="result-card"
        @click="onPlaylistClick(pl)"
      >
        <img v-if="pl.thumbnail" :src="pl.thumbnail" class="result-thumb" alt="" @error="onImgError" />
        <div class="result-thumb placeholder img-fallback" :style="{ display: pl.thumbnail ? 'none' : 'flex' }">
          <i class="mdi mdi-playlist-music"></i>
        </div>
        <div class="result-info">
          <div class="result-title">{{ pl.title }}</div>
          <div class="result-sub">{{ pl.author }} &middot; {{ pl.trackCount }} tracks</div>
        </div>
        <i class="mdi mdi-chevron-right result-chevron"></i>
      </div>
    </div>

    <!-- Album results -->
    <div v-if="!loading && filterType === 'albums' && results.length" class="results-section">
      <div
        v-for="album in results"
        :key="album.browseId"
        class="result-card"
        @click="onAlbumClick(album)"
      >
        <img v-if="album.thumbnail" :src="album.thumbnail" class="result-thumb" alt="" @error="onImgError" />
        <div class="result-thumb placeholder img-fallback" :style="{ display: album.thumbnail ? 'none' : 'flex' }">
          <i class="mdi mdi-album"></i>
        </div>
        <div class="result-info">
          <div class="result-title">{{ album.title }}</div>
          <div class="result-sub">{{ album.artists?.join(', ') }} &middot; {{ album.year }}</div>
        </div>
        <i class="mdi mdi-chevron-right result-chevron"></i>
      </div>
    </div>

    <SpeakerPicker
      v-model:visible="showPicker"
      @select="onSelectSpeaker"
    />

    <AddToPlaylist
      v-model:visible="showAddToPlaylist"
      :track="playlistTrack"
    />
  </div>
</template>

<style scoped>
.search-view {
  padding: 20px 16px;
}

.page-title {
  font-size: 1.6rem;
  font-weight: 800;
  margin-bottom: 16px;
  letter-spacing: -0.02em;
}

/* Recent section */
.recent-section {
  margin-top: 24px;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
}

.section-title i {
  font-size: 1.1rem;
  color: var(--text-secondary);
}

.recent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 12px;
}

.recent-card {
  cursor: pointer;
  text-align: center;
  padding: 8px;
  border-radius: 12px;
  transition: background 0.15s;
}

.recent-card:hover {
  background: var(--hover-bg);
}

.recent-thumb {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 10px;
  object-fit: cover;
  margin-bottom: 6px;
}

.recent-thumb.round {
  border-radius: 50%;
}

.recent-thumb.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.5rem;
}

.recent-title {
  font-weight: 600;
  font-size: 0.78rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recent-sub {
  font-size: 0.7rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Loading */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 16px;
  color: var(--text-secondary);
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

/* Empty state */
.empty-state {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-secondary);
}

.empty-state i {
  font-size: 3rem;
  color: var(--placeholder-color);
}

.empty-state p {
  margin-top: 8px;
  font-size: 0.9rem;
}

/* Results */
.results-section {
  margin-top: 20px;
}

.result-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.result-card:hover {
  background: var(--hover-bg);
}

.result-thumb {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

.result-thumb.round {
  border-radius: 50%;
}

.result-thumb.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.2rem;
}

.result-info {
  flex: 1;
  min-width: 0;
}

.result-title {
  font-weight: 500;
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-sub {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.result-chevron {
  color: var(--text-secondary);
  font-size: 1.2rem;
  flex-shrink: 0;
}
</style>
