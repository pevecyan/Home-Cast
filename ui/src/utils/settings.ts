import { ref, watch } from 'vue'
import axios from 'axios'

// --- Theme: local per-browser preference ---

const THEME_KEY = 'home-cast-theme'
export type ThemeMode = 'light' | 'dark' | 'auto'

function loadTheme(): ThemeMode {
  return (localStorage.getItem(THEME_KEY) as ThemeMode) ?? 'auto'
}

export const themeMode = ref<ThemeMode>(loadTheme())

watch(themeMode, val => localStorage.setItem(THEME_KEY, val))

// --- Feature flags: persisted on the server ---

export const sleepEnabled = ref(true)
export const volumeLockEnabled = ref(true)

let _saving = false

export async function loadServerSettings() {
  try {
    const { data } = await axios.get('/api/storage/settings')
    sleepEnabled.value = data.sleepEnabled ?? true
    volumeLockEnabled.value = data.volumeLockEnabled ?? true
  } catch {
    // server unreachable — keep defaults
  }
}

async function saveServerSettings() {
  if (_saving) return
  _saving = true
  try {
    await axios.post('/api/storage/settings', {
      sleepEnabled: sleepEnabled.value,
      volumeLockEnabled: volumeLockEnabled.value,
    })
  } finally {
    _saving = false
  }
}

watch([sleepEnabled, volumeLockEnabled], saveServerSettings)
