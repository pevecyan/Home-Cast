<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import Dialog from 'primevue/dialog'
import MiniPlayer from './components/MiniPlayer.vue'
import NowPlaying from './components/NowPlaying.vue'
import SettingsDialog from './components/SettingsDialog.vue'
import { useDevicesStore } from './stores/devices'
import { useLocalPlayerStore } from './stores/localPlayer'
import { useRecentStore } from './stores/recent'
import { useFavoriteRadioStore } from './stores/favoriteRadio'
import { getVersion, getLatestGitHubVersion, type VersionInfo } from './api/version'
import { getHomeFeed, getMoodCategories } from './api/music'
import { loadServerSettings } from './utils/settings'
import type { Device } from './api/devices'

// Initialise dark mode reactivity (side-effectful import)
import './utils/darkMode'

const showSettings = ref(false)

const router = useRouter()
const sidebarOpen = ref(false)
const devicesStore = useDevicesStore()
const localPlayer = useLocalPlayerStore()
const recentStore = useRecentStore()
const favoriteRadioStore = useFavoriteRadioStore()

// --- Now Playing sheet ---
const audioEl = ref<HTMLAudioElement | null>(null)
const nowPlayingDevice = ref<Device | null>(null)
function openNowPlaying(device: Device) { nowPlayingDevice.value = device }
function closeNowPlaying() { nowPlayingDevice.value = null }

// --- PWA install prompt ---
const installEvent = ref<any>(null)
const canInstall = computed(() => !!installEvent.value)
function onBeforeInstall(e: Event) {
  e.preventDefault()
  installEvent.value = e
}
async function promptInstall() {
  if (!installEvent.value) return
  installEvent.value.prompt()
  await installEvent.value.userChoice
  installEvent.value = null
}

onMounted(async () => {
  if (audioEl.value) localPlayer.bindElement(audioEl.value)
  window.addEventListener('beforeinstallprompt', onBeforeInstall)

  // Only the local pseudo-device is present until we fetch real speakers.
  if (!devicesStore.hasRealDevices) {
    await devicesStore.fetchDevices()
  }
  await devicesStore.fetchAllStates()

  // Connect WebSocket (falls back to polling automatically)
  devicesStore.connectWs()

  // Load persisted data from server
  recentStore.load()
  favoriteRadioStore.load()
  loadServerSettings()

  // Load version info eagerly so it shows in sidebar immediately
  getVersion().then(v => { versionInfo.value = v }).catch(() => {})
  getLatestGitHubVersion().then(v => { latestVersion.value = v }).catch(() => {})

  // Warm the Discover feed cache on the server so opening Discover is instant.
  // Fire-and-forget: the backend caches the result (cache.discover_ttl).
  getHomeFeed().catch(() => {})
  getMoodCategories().catch(() => {})
})

onUnmounted(() => {
  devicesStore.cleanup()
  window.removeEventListener('beforeinstallprompt', onBeforeInstall)
})

const navItems = [
  { label: 'Home', icon: 'mdi mdi-home-variant', to: '/' },
  { label: 'Discover', icon: 'mdi mdi-compass-outline', to: '/discover' },
  { label: 'Radio', icon: 'mdi mdi-radio', to: '/radio' },
  { label: 'Playlists', icon: 'mdi mdi-playlist-music', to: '/playlists' },
]

function navigate(to: string) {
  router.push(to)
  sidebarOpen.value = false
}

const versionInfo = ref<VersionInfo | null>(null)
const showChangelog = ref(false)
const latestVersion = ref<string | null>(null)

const updateAvailable = computed(() => {
  if (!versionInfo.value || !latestVersion.value) return false
  return versionInfo.value.version !== latestVersion.value
})

async function openChangelog() {
  if (!versionInfo.value) {
    versionInfo.value = await getVersion()
  }
  showChangelog.value = true
}
</script>

<template>
  <div class="app-layout" :class="{ 'sidebar-open': sidebarOpen }">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <img src="/favicon.svg" alt="Home Cast" class="logo-icon" />
          <span class="logo-text">Home Cast</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <button
          v-for="item in navItems"
          :key="item.to"
          class="sidebar-item"
          :class="{ active: $route.path === item.to }"
          @click="navigate(item.to)"
        >
          <i :class="item.icon"></i>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <button v-if="canInstall" class="sidebar-item" @click="promptInstall">
          <i class="mdi mdi-download"></i>
          <span>Install app</span>
        </button>
        <button class="version-btn" @click="openChangelog">
          <i class="mdi mdi-tag-outline"></i>
          <span>v{{ versionInfo?.version ?? '…' }}</span>
          <span v-if="updateAvailable" class="update-dot" title="New version available"></span>
        </button>
        <button class="sidebar-item" @click="showSettings = true">
          <i class="mdi mdi-cog-outline"></i>
          <span>Settings</span>
        </button>
      </div>
    </aside>

    <SettingsDialog v-model:visible="showSettings" />

    <Dialog
      v-model:visible="showChangelog"
      header="Changelog"
      modal
      :closable="true"
      :closeOnEscape="true"
      :style="{ width: '90vw', maxWidth: '480px' }"
    >
      <div v-if="versionInfo" class="changelog">
        <div v-if="updateAvailable" class="update-banner">
          <i class="mdi mdi-arrow-up-circle-outline"></i>
          <span>Version <strong>v{{ latestVersion }}</strong> is available on GitHub</span>
        </div>
        <div v-for="entry in versionInfo.changelog" :key="entry.version" class="changelog-entry">
          <div class="changelog-header">
            <span class="changelog-version">v{{ entry.version }}</span>
            <span class="changelog-date">{{ entry.date }}</span>
          </div>
          <ul class="changelog-list">
            <li v-for="(change, i) in entry.changes" :key="i">{{ change }}</li>
          </ul>
        </div>
      </div>
    </Dialog>

    <!-- Overlay for mobile -->
    <div class="sidebar-overlay" @click="sidebarOpen = false"></div>

    <!-- Main content -->
    <div class="main-content">
      <header class="topbar">
        <button class="menu-btn" @click="sidebarOpen = !sidebarOpen">
          <i class="mdi mdi-menu"></i>
        </button>
        <span class="topbar-title">Home Cast</span>
      </header>

      <div class="page-content">
        <router-view />
      </div>

      <MiniPlayer @open="openNowPlaying" />
    </div>

    <!-- Single hidden audio element that drives local (browser) playback -->
    <audio ref="audioEl" hidden></audio>

    <NowPlaying
      v-if="nowPlayingDevice"
      :device="nowPlayingDevice"
      @close="closeNowPlaying"
    />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

/* ── Sidebar ── */
.sidebar {
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  width: 240px;
  background: var(--card-bg);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  z-index: 200;
  transition: transform 0.25s ease;
}

.sidebar-header {
  padding: 20px 16px 12px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
}

.logo-text {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-nav {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 0.9rem;
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  width: 100%;
  text-align: left;
}

.sidebar-item i {
  font-size: 1.25rem;
  width: 24px;
  text-align: center;
}

.sidebar-item:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.sidebar-item.active {
  background: var(--surface-dim);
  color: var(--p-primary-color, #6366f1);
  font-weight: 600;
}

.sidebar-footer {
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-top: 1px solid var(--border-color);
}

.version-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  border-radius: 10px;
  transition: background 0.15s, color 0.15s;
  width: 100%;
  text-align: left;
  font-family: inherit;
}

.version-btn i {
  font-size: 1.25rem;
  width: 24px;
  text-align: center;
}

.version-btn:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.update-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  flex-shrink: 0;
  margin-left: auto;
}

.update-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: color-mix(in srgb, #f59e0b 12%, transparent);
  border: 1px solid color-mix(in srgb, #f59e0b 40%, transparent);
  border-radius: 8px;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.update-banner i {
  font-size: 1.1rem;
  color: #f59e0b;
  flex-shrink: 0;
}

.changelog {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.changelog-entry {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.changelog-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.changelog-version {
  font-weight: 700;
  font-size: 1rem;
  color: var(--p-primary-color, #6366f1);
}

.changelog-date {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.changelog-list {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.changelog-list li {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

/* ── Overlay ── */
.sidebar-overlay {
  display: none;
}

/* ── Main content ── */
.main-content {
  flex: 1;
  min-width: 0;
  margin-left: 240px;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.topbar {
  display: none;
}

.page-content {
  flex: 1;
  padding-bottom: 64px;
  min-width: 0;
}

/* ── Mobile: sidebar is off-screen by default ── */
@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
  }

  .sidebar-open .sidebar {
    transform: translateX(0);
  }

  .sidebar-open .sidebar-overlay {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.4);
    z-index: 150;
  }

  .main-content {
    margin-left: 0;
  }

  .topbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--card-bg);
    border-bottom: 1px solid var(--border-color);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .menu-btn {
    border: none;
    background: none;
    color: var(--text-primary);
    font-size: 1.4rem;
    cursor: pointer;
    padding: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .topbar-title {
    font-weight: 700;
    font-size: 1.1rem;
  }
}
</style>
