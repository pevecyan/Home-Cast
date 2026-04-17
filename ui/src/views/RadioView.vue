<script setup lang="ts">
import { ref, onMounted } from 'vue'
import SpeakerPicker from '../components/SpeakerPicker.vue'
import { searchRadio, getPopularRadio, playRadio, type RadioStation } from '../api/radio'
import { onImgError } from '../utils/imgFallback'
import { useDevicesStore } from '../stores/devices'
import { useFavoriteRadioStore } from '../stores/favoriteRadio'
import type { PlayOptions } from '../components/SpeakerPicker.vue'

const devicesStore = useDevicesStore()
const favStore = useFavoriteRadioStore()

const query = ref('')
const stations = ref<RadioStation[]>([])
const loading = ref(false)
const showPicker = ref(false)
const pendingStation = ref<RadioStation | null>(null)

devicesStore.fetchDevices()

onMounted(async () => {
  loading.value = true
  try {
    stations.value = await getPopularRadio()
  } finally {
    loading.value = false
  }
})

async function onSearch() {
  if (!query.value.trim() && stations.value.length) return
  loading.value = true
  try {
    if (query.value.trim()) {
      stations.value = await searchRadio(query.value.trim())
    } else {
      stations.value = await getPopularRadio()
    }
  } finally {
    loading.value = false
  }
}

function onStationClick(station: RadioStation) {
  pendingStation.value = station
  showPicker.value = true
}

function onFavToggle(e: Event, station: RadioStation) {
  e.stopPropagation()
  favStore.toggle(station)
}

async function onSelectSpeaker(opts: PlayOptions) {
  if (pendingStation.value) {
    await playRadio(opts.device.slug, opts.device.type, pendingStation.value)
    pendingStation.value = null
  }
}
</script>

<template>
  <div class="radio-view">
    <h1 class="page-title">Radio</h1>

    <form @submit.prevent="onSearch" class="search-form">
      <div class="search-input-container">
        <i class="mdi mdi-magnify search-icon"></i>
        <input
          v-model="query"
          type="text"
          placeholder="Search Slovenian radio stations..."
          class="search-input"
        />
        <button
          v-if="query"
          type="button"
          class="clear-btn"
          @click="query = ''; onSearch()"
        >
          <i class="mdi mdi-close"></i>
        </button>
      </div>
    </form>

    <!-- Favorites -->
    <div v-if="favStore.favorites.length && !query" class="favorites-section">
      <h2 class="section-title">
        <i class="mdi mdi-heart"></i> Favorites
      </h2>
      <div class="favorites-row">
        <div
          v-for="station in favStore.favorites"
          :key="'fav-' + station.stationuuid"
          class="fav-card"
          @click="onStationClick(station)"
        >
          <img
            v-if="station.favicon"
            :src="station.favicon"
            class="fav-icon"
            alt=""
            @error="onImgError"
          />
          <div class="fav-icon placeholder img-fallback" :style="{ display: station.favicon ? 'none' : 'flex' }">
            <i class="mdi mdi-radio"></i>
          </div>
          <div class="fav-name">{{ station.name }}</div>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading stations...</span>
    </div>

    <div v-else-if="!stations.length" class="empty-state">
      <i class="mdi mdi-radio-off"></i>
      <p>No stations found</p>
    </div>

    <!-- Station list -->
    <div v-else class="station-list">
      <h2 v-if="!query" class="section-title" style="margin-bottom: 8px;">
        <i class="mdi mdi-trending-up"></i> Popular
      </h2>
      <div
        v-for="station in stations"
        :key="station.stationuuid"
        class="station-card"
        @click="onStationClick(station)"
      >
        <img
          v-if="station.favicon"
          :src="station.favicon"
          class="station-icon"
          alt=""
          @error="onImgError"
        />
        <div class="station-icon placeholder img-fallback" :style="{ display: station.favicon ? 'none' : 'flex' }">
          <i class="mdi mdi-radio"></i>
        </div>
        <div class="station-info">
          <div class="station-name">{{ station.name }}</div>
          <div class="station-meta">
            <span v-if="station.bitrate" class="station-bitrate">{{ station.bitrate }} kbps</span>
          </div>
        </div>
        <button
          class="fav-btn"
          :class="{ active: favStore.isFavorite(station.stationuuid) }"
          @click="onFavToggle($event, station)"
        >
          <i :class="favStore.isFavorite(station.stationuuid) ? 'mdi mdi-heart' : 'mdi mdi-heart-outline'"></i>
        </button>
        <i class="mdi mdi-play-circle-outline station-play"></i>
      </div>
    </div>

    <SpeakerPicker
      v-model:visible="showPicker"
      :show-play-options="false"
      @select="onSelectSpeaker"
    />
  </div>
</template>

<style scoped>
.radio-view {
  padding: 20px 16px;
}

.page-title {
  font-size: 1.6rem;
  font-weight: 800;
  margin-bottom: 16px;
  letter-spacing: -0.02em;
}

.search-input-container {
  display: flex;
  align-items: center;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 0 16px;
  box-shadow: 0 1px 4px var(--surface-dim);
  transition: box-shadow 0.2s;
}

.search-input-container:focus-within {
  box-shadow: 0 2px 12px var(--surface-dim);
}

.search-icon {
  font-size: 1.3rem;
  color: var(--text-secondary);
  margin-right: 10px;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  background: none;
  font-size: 1rem;
  padding: 14px 0;
  color: var(--text-primary);
  font-family: inherit;
  min-width: 0;
  width: 0;
}

.search-input::placeholder {
  color: var(--text-secondary);
}

.clear-btn {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 4px;
  display: flex;
  align-items: center;
  font-size: 1.1rem;
}

/* Section titles */
.section-title {
  font-size: 1rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
}

.section-title i {
  font-size: 1.1rem;
  color: var(--text-secondary);
}

/* Favorites */
.favorites-section {
  margin-top: 20px;
  margin-bottom: 24px;
}

.favorites-row {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding: 12px 0 4px;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.favorites-row::-webkit-scrollbar {
  display: none;
}

.fav-card {
  flex-shrink: 0;
  width: 80px;
  text-align: center;
  cursor: pointer;
  padding: 6px;
  border-radius: 10px;
  transition: background 0.15s;
}

.fav-card:hover {
  background: var(--hover-bg);
}

.fav-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  object-fit: cover;
  margin: 0 auto 6px;
}

.fav-icon.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.2rem;
}

.fav-name {
  font-size: 0.7rem;
  font-weight: 500;
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

/* Station list */
.station-list {
  margin-top: 20px;
}

.station-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
  max-width: 100%;
}

.station-card:hover {
  background: var(--hover-bg);
}

.station-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
  flex-shrink: 0;
}

.station-icon.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.3rem;
}

.station-info {
  flex-grow: 0;
  min-width: 0;
  overflow: hidden;
  width: 100%;
}

.station-name {
  font-weight: 500;
  font-size: 0.95rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.station-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.station-tags {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.station-bitrate {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--surface-dim);
  font-size: 0.7rem;
  font-weight: 500;
}

.fav-btn {
  border: none;
  background: none;
  cursor: pointer;
  font-size: 1.1rem;
  color: var(--text-secondary);
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  transition: color 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.fav-btn.active {
  color: #ef4444;
}

.station-play {
  font-size: 1.5rem;
  color: var(--text-secondary);
  flex-shrink: 0;
  width: 32px;
  transition: color 0.15s;
}

.station-card:hover .station-play {
  color: var(--p-primary-color, #6366f1);
}
</style>
