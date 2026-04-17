<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import { getPlaylist, updatePlaylist, type SavedPlaylist } from '../api/playlists'
import { onImgError } from '../utils/imgFallback'

const route = useRoute()
const router = useRouter()

const playlist = ref<SavedPlaylist | null>(null)
const loading = ref(true)
const saving = ref(false)
const editingName = ref(false)
const nameInput = ref('')

onMounted(async () => {
  const id = route.params.id as string
  playlist.value = await getPlaylist(id)
  nameInput.value = playlist.value?.name || ''
  loading.value = false
})

function startEditName() {
  nameInput.value = playlist.value?.name || ''
  editingName.value = true
}

async function saveName() {
  if (!playlist.value || !nameInput.value.trim()) return
  saving.value = true
  try {
    playlist.value = await updatePlaylist(playlist.value.id, { name: nameInput.value.trim() })
    editingName.value = false
  } finally {
    saving.value = false
  }
}

async function removeTrack(index: number) {
  if (!playlist.value) return
  const tracks = [...playlist.value.tracks]
  tracks.splice(index, 1)
  saving.value = true
  try {
    playlist.value = await updatePlaylist(playlist.value.id, { tracks })
  } finally {
    saving.value = false
  }
}

async function moveTrack(from: number, to: number) {
  if (!playlist.value) return
  if (to < 0 || to >= playlist.value.tracks.length) return
  const tracks = [...playlist.value.tracks]
  const [item] = tracks.splice(from, 1)
  tracks.splice(to, 0, item)
  playlist.value = { ...playlist.value, tracks }
  saving.value = true
  try {
    await updatePlaylist(playlist.value.id, { tracks })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="edit-view">
    <div v-if="loading" class="loading">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
    </div>

    <template v-else-if="playlist">
      <!-- Header -->
      <div class="header">
        <button class="back-btn" @click="router.push('/playlists')">
          <i class="mdi mdi-arrow-left"></i>
        </button>
        <div v-if="!editingName" class="title-row" @click="startEditName">
          <h1 class="page-title">{{ playlist.name }}</h1>
          <i class="mdi mdi-pencil edit-icon"></i>
        </div>
        <form v-else class="name-form" @submit.prevent="saveName">
          <InputText
            v-model="nameInput"
            autofocus
            style="flex: 1"
            @keydown.escape="editingName = false"
          />
          <Button icon="pi pi-check" rounded text size="small" type="submit" :loading="saving" />
          <Button icon="pi pi-times" rounded text size="small" severity="secondary" @click="editingName = false" />
        </form>
      </div>

      <div class="track-count">{{ playlist.tracks.length }} tracks</div>

      <!-- Empty -->
      <div v-if="!playlist.tracks.length" class="empty">
        <i class="mdi mdi-playlist-music" style="font-size: 3rem; color: var(--placeholder-color)"></i>
        <p>No tracks in this playlist</p>
        <p class="empty-hint">Search for songs and add them here</p>
      </div>

      <!-- Track list -->
      <div v-else class="track-list">
        <div
          v-for="(track, idx) in playlist.tracks"
          :key="`${track.videoId}-${idx}`"
          class="track-item"
        >
          <span class="track-num">{{ idx + 1 }}</span>
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
          <div class="track-info">
            <div class="track-title">{{ track.title }}</div>
            <div class="track-artist">{{ track.artists?.join(', ') }}</div>
          </div>
          <div class="track-actions">
            <button
              class="action-btn"
              :disabled="idx === 0"
              @click="moveTrack(idx, idx - 1)"
              title="Move up"
            >
              <i class="mdi mdi-chevron-up"></i>
            </button>
            <button
              class="action-btn"
              :disabled="idx === playlist.tracks.length - 1"
              @click="moveTrack(idx, idx + 1)"
              title="Move down"
            >
              <i class="mdi mdi-chevron-down"></i>
            </button>
            <button
              class="action-btn remove"
              @click="removeTrack(idx)"
              title="Remove"
            >
              <i class="mdi mdi-close"></i>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.edit-view {
  padding: 16px;
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.back-btn {
  border: none;
  background: none;
  color: var(--text-primary);
  font-size: 1.3rem;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
}

.back-btn:hover {
  background: var(--hover-bg);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  flex: 1;
  min-width: 0;
  padding: 4px 0;
  border-radius: 8px;
}

.title-row:hover .edit-icon {
  opacity: 1;
}

.page-title {
  font-size: 1.4rem;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.edit-icon {
  font-size: 0.9rem;
  color: var(--text-secondary);
  opacity: 0.4;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.name-form {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}

.track-count {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 16px;
  padding-left: 36px;
}

/* Track list */
.track-list {
  display: flex;
  flex-direction: column;
}

.track-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 4px;
  border-radius: 10px;
  transition: background 0.15s;
}

.track-item:hover {
  background: var(--hover-bg);
}

.track-num {
  width: 24px;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-secondary);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.track-thumb {
  width: 44px;
  height: 44px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}

.track-thumb.placeholder {
  width: 44px;
  height: 44px;
  border-radius: 6px;
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.1rem;
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
  font-size: 0.78rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.track-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.action-btn {
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 1.1rem;
  cursor: pointer;
  padding: 4px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s, color 0.15s;
  width: 28px;
  height: 28px;
}

.action-btn:hover:not(:disabled) {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.action-btn:disabled {
  opacity: 0.2;
  cursor: default;
}

.action-btn.remove:hover {
  color: #ef4444;
}

/* Empty */
.loading,
.empty {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-secondary);
}

.empty p {
  margin-top: 8px;
}

.empty-hint {
  font-size: 0.85rem;
  opacity: 0.7;
}
</style>
