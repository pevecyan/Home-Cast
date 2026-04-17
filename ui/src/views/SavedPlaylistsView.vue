<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import SpeakerPicker from '../components/SpeakerPicker.vue'
import {
  listPlaylists,
  createPlaylist,
  deletePlaylist,
  type SavedPlaylist,
} from '../api/playlists'
import { usePlayerStore } from '../stores/player'
import { useDevicesStore } from '../stores/devices'
import { useRouter } from 'vue-router'
import type { PlayOptions } from '../components/SpeakerPicker.vue'

const router = useRouter()
const player = usePlayerStore()
const devicesStore = useDevicesStore()

const playlists = ref<SavedPlaylist[]>([])
const loading = ref(true)
const showCreate = ref(false)
const newName = ref('')
const showPicker = ref(false)
const pendingPlaylistId = ref<string | null>(null)

devicesStore.fetchDevices()

onMounted(async () => {
  playlists.value = await listPlaylists()
  loading.value = false
})

async function onCreate() {
  if (!newName.value.trim()) return
  await createPlaylist(newName.value.trim())
  playlists.value = await listPlaylists()
  newName.value = ''
  showCreate.value = false
}

async function onDelete(id: string) {
  await deletePlaylist(id)
  playlists.value = await listPlaylists()
}

function onPlay(id: string) {
  pendingPlaylistId.value = id
  showPicker.value = true
}

async function onSelectSpeaker(opts: PlayOptions) {
  if (pendingPlaylistId.value) {
    await player.playSaved(pendingPlaylistId.value, opts.device)
    pendingPlaylistId.value = null
  }
}
</script>

<template>
  <div class="playlists-view">
    <div class="header-row">
      <h1 class="page-title">My Playlists</h1>
      <Button icon="pi pi-plus" rounded text @click="showCreate = true" />
    </div>

    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
    </div>

    <div v-else-if="!playlists.length" class="empty">
      <i class="mdi mdi-playlist-music" style="font-size: 3rem; color: var(--placeholder-color)"></i>
      <p>No saved playlists yet</p>
    </div>

    <div v-else class="playlist-list">
      <div
        v-for="pl in playlists"
        :key="pl.id"
        class="playlist-item"
        @click="router.push({ name: 'edit-playlist', params: { id: pl.id } })"
      >
        <div class="playlist-info">
          <div class="playlist-name">{{ pl.name }}</div>
          <div class="playlist-count">{{ pl.tracks.length }} tracks</div>
        </div>
        <Button
          icon="pi pi-play"
          rounded
          text
          size="small"
          :disabled="!pl.tracks.length"
          @click.stop="onPlay(pl.id)"
        />
        <Button
          icon="pi pi-pencil"
          rounded
          text
          size="small"
          @click.stop="router.push({ name: 'edit-playlist', params: { id: pl.id } })"
        />
        <Button
          icon="pi pi-trash"
          rounded
          text
          severity="danger"
          size="small"
          @click.stop="onDelete(pl.id)"
        />
      </div>
    </div>

    <Dialog
      v-model:visible="showCreate"
      header="New Playlist"
      modal
      :style="{ width: '90vw', maxWidth: '400px' }"
    >
      <form @submit.prevent="onCreate" style="display: flex; gap: 8px">
        <InputText v-model="newName" placeholder="Playlist name" style="flex: 1" />
        <Button label="Create" type="submit" />
      </form>
    </Dialog>

    <SpeakerPicker
      v-model:visible="showPicker"
      @select="onSelectSpeaker"
    />
  </div>
</template>

<style scoped>
.playlists-view {
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

.playlist-list {
  display: flex;
  flex-direction: column;
}

.playlist-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 8px;
  border-bottom: 1px solid var(--border-color);
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s;
}

.playlist-item:hover {
  background: var(--hover-bg);
}

.playlist-info {
  flex: 1;
}

.playlist-name {
  font-weight: 500;
}

.playlist-count {
  font-size: 0.8rem;
  color: var(--text-secondary);
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
