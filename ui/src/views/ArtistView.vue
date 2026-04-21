<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import TrackList from '../components/TrackList.vue'
import SpeakerPicker from '../components/SpeakerPicker.vue'
import { getArtist, prefetchSong, type ArtistDetail, type Track } from '../api/music'
import { onImgError } from '../utils/imgFallback'
import { usePlayerStore } from '../stores/player'
import { useDevicesStore } from '../stores/devices'
import type { PlayOptions } from '../components/SpeakerPicker.vue'
import AddToPlaylist from '../components/AddToPlaylist.vue'

const route = useRoute()
const player = usePlayerStore()
const devicesStore = useDevicesStore()

const artist = ref<ArtistDetail | null>(null)
const loading = ref(true)
const showPicker = ref(false)
const pendingTrack = ref<Track | null>(null)
const showAddToPlaylist = ref(false)
const playlistTrack = ref<Track | null>(null)

function onAddToPlaylist(track: Track) {
  playlistTrack.value = track
  showAddToPlaylist.value = true
}

devicesStore.fetchDevices()

onMounted(async () => {
  const browseId = route.params.browseId as string
  const a = await getArtist(browseId)
  artist.value = a
  loading.value = false
  a.songs.slice(0, 3).forEach(t => prefetchSong(t.videoId))
})

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
</script>

<template>
  <div class="artist-view">
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
    </div>

    <template v-else-if="artist">
      <div class="artist-header">
        <img
          v-if="artist.thumbnail"
          :src="artist.thumbnail"
          class="artist-thumb"
          alt=""
          @error="onImgError"
        />
        <div class="artist-thumb placeholder img-fallback" :style="{ display: artist.thumbnail ? 'none' : 'flex' }">
          <i class="mdi mdi-account-music" style="font-size: 2.5rem"></i>
        </div>
        <h1>{{ artist.name }}</h1>
      </div>

      <h2 class="section-title">Top Songs</h2>
      <TrackList :tracks="artist.songs" @play="onPlayTrack" @add-to-playlist="onAddToPlaylist" />
    </template>

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
.artist-view {
  padding: 16px;
}

.artist-header {
  text-align: center;
  margin-bottom: 24px;
}

.artist-thumb {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  object-fit: cover;
  margin-bottom: 12px;
}

.artist-thumb.placeholder {
  background: var(--placeholder-bg);
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  margin: 0 auto 12px;
}

.artist-header h1 {
  font-size: 1.5rem;
  font-weight: 700;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 8px;
}

.loading {
  text-align: center;
  padding: 48px;
}
</style>
