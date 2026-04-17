<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import MiniPlayer from './components/MiniPlayer.vue'
import { isDark, toggleDark } from './utils/darkMode'
import { useDevicesStore } from './stores/devices'
import { useRecentStore } from './stores/recent'
import { useFavoriteRadioStore } from './stores/favoriteRadio'

const router = useRouter()
const sidebarOpen = ref(false)
const devicesStore = useDevicesStore()
const recentStore = useRecentStore()
const favoriteRadioStore = useFavoriteRadioStore()

onMounted(async () => {
  if (!devicesStore.devices.length) {
    await devicesStore.fetchDevices()
  }
  await devicesStore.fetchAllStates()

  // Connect WebSocket (falls back to polling automatically)
  devicesStore.connectWs()

  // Load persisted data from server
  recentStore.load()
  favoriteRadioStore.load()
})

onUnmounted(() => {
  devicesStore.cleanup()
})

const navItems = [
  { label: 'Home', icon: 'mdi mdi-home-variant', to: '/' },
  { label: 'Search', icon: 'mdi mdi-magnify', to: '/search' },
  { label: 'Radio', icon: 'mdi mdi-radio', to: '/radio' },
  { label: 'Playlists', icon: 'mdi mdi-playlist-music', to: '/playlists' },
]

function navigate(to: string) {
  router.push(to)
  sidebarOpen.value = false
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
        <button class="sidebar-item theme-toggle" @click="toggleDark()">
          <i :class="isDark ? 'mdi mdi-weather-sunny' : 'mdi mdi-weather-night'"></i>
          <span>{{ isDark ? 'Light mode' : 'Dark mode' }}</span>
        </button>
      </div>
    </aside>

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

      <MiniPlayer />
    </div>
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
  height: 56px;
  display: flex;
  align-items: center;
  border-top: 1px solid var(--border-color);
}

/* ── Overlay ── */
.sidebar-overlay {
  display: none;
}

/* ── Main content ── */
.main-content {
  flex: 1;
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
