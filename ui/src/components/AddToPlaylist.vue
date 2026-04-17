<script setup lang="ts">
import { ref } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import { listPlaylists, createPlaylist, updatePlaylist, type SavedPlaylist } from '../api/playlists'
import type { Track } from '../api/music'

const props = defineProps<{
  visible: boolean
  track: Track | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const playlists = ref<SavedPlaylist[]>([])
const loading = ref(false)
const showCreate = ref(false)
const newName = ref('')
const addedTo = ref<string | null>(null)

async function loadPlaylists() {
  loading.value = true
  try {
    playlists.value = await listPlaylists()
  } finally {
    loading.value = false
  }
}

async function addToPlaylist(playlist: SavedPlaylist) {
  if (!props.track) return
  const alreadyExists = playlist.tracks.some(t => t.videoId === props.track!.videoId)
  if (alreadyExists) {
    addedTo.value = playlist.id
    setTimeout(() => close(), 800)
    return
  }
  await updatePlaylist(playlist.id, {
    tracks: [...playlist.tracks, props.track],
  })
  addedTo.value = playlist.id
  setTimeout(() => close(), 800)
}

async function onCreateAndAdd() {
  if (!newName.value.trim() || !props.track) return
  const pl = await createPlaylist(newName.value.trim(), [props.track])
  newName.value = ''
  showCreate.value = false
  addedTo.value = pl.id
  setTimeout(() => close(), 800)
}

function close() {
  addedTo.value = null
  showCreate.value = false
  emit('update:visible', false)
}

function onShow() {
  addedTo.value = null
  showCreate.value = false
  loadPlaylists()
}
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    header="Add to playlist"
    modal
    :closable="true"
    :closeOnEscape="true"
    :style="{ width: '90vw', maxWidth: '400px' }"
    @show="onShow"
  >
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner"></i>
    </div>

    <template v-else>
      <!-- Create new -->
      <div v-if="showCreate" class="create-form">
        <form @submit.prevent="onCreateAndAdd" style="display: flex; gap: 8px">
          <InputText v-model="newName" placeholder="New playlist name" style="flex: 1" autofocus />
          <Button label="Add" type="submit" size="small" />
        </form>
      </div>

      <button v-else class="playlist-option create-btn" @click="showCreate = true">
        <i class="mdi mdi-plus"></i>
        <span>New playlist</span>
      </button>

      <!-- Existing playlists -->
      <div class="playlist-list">
        <button
          v-for="pl in playlists"
          :key="pl.id"
          class="playlist-option"
          :class="{ added: addedTo === pl.id }"
          @click="addToPlaylist(pl)"
        >
          <i :class="addedTo === pl.id ? 'mdi mdi-check' : 'mdi mdi-playlist-music'"></i>
          <div class="pl-info">
            <div class="pl-name">{{ pl.name }}</div>
            <div class="pl-count">{{ pl.tracks.length }} tracks</div>
          </div>
        </button>
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
.loading {
  text-align: center;
  padding: 24px;
  color: var(--text-secondary);
  font-size: 1.5rem;
}

.create-form {
  padding: 4px 0 12px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 4px;
}

.playlist-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.playlist-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: none;
  background: none;
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: background 0.15s;
  color: var(--text-primary);
  font-family: inherit;
}

.playlist-option:hover {
  background: var(--hover-bg);
}

.playlist-option i {
  font-size: 1.2rem;
  color: var(--text-secondary);
  width: 24px;
  text-align: center;
}

.playlist-option.added i {
  color: #22c55e;
}

.playlist-option.create-btn {
  color: var(--p-primary-color, #6366f1);
  margin-bottom: 4px;
  border-bottom: 1px solid var(--border-color);
  border-radius: 10px 10px 0 0;
  padding-bottom: 12px;
}

.playlist-option.create-btn i {
  color: var(--p-primary-color, #6366f1);
}

.pl-info {
  flex: 1;
  min-width: 0;
}

.pl-name {
  font-weight: 500;
  font-size: 0.9rem;
}

.pl-count {
  font-size: 0.75rem;
  color: var(--text-secondary);
}
</style>
