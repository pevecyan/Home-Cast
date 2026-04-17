import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface RecentItem {
  type: 'playlist' | 'artist' | 'song'
  id: string
  title: string
  subtitle?: string
  thumbnail?: string
  timestamp: number
}

export const useRecentStore = defineStore('recent', () => {
  const items = ref<RecentItem[]>([])
  const loaded = ref(false)

  async function load() {
    if (loaded.value) return
    try {
      items.value = (await api.get<RecentItem[]>('/storage/recents')).data
    } catch {
      // fallback: migrate from localStorage
      try {
        const local = JSON.parse(localStorage.getItem('home-cast-recent') || '[]')
        if (local.length) {
          // push them one by one in reverse so order is preserved
          for (const item of [...local].reverse()) {
            await api.post('/storage/recents', item)
          }
          items.value = (await api.get<RecentItem[]>('/storage/recents')).data
          localStorage.removeItem('home-cast-recent')
        }
      } catch { /* ignore */ }
    }
    loaded.value = true
  }

  async function add(item: Omit<RecentItem, 'timestamp'>) {
    const entry = { ...item, timestamp: Date.now() }
    try {
      items.value = (await api.post<RecentItem[]>('/storage/recents', entry)).data
    } catch {
      // best-effort, don't break playback
    }
  }

  return { items, load, add }
})
