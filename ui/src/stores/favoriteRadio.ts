import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
import type { RadioStation } from '../api/radio'

const api = axios.create({ baseURL: '/api' })

export const useFavoriteRadioStore = defineStore('favoriteRadio', () => {
  const favorites = ref<RadioStation[]>([])
  const loaded = ref(false)

  async function load() {
    if (loaded.value) return
    try {
      favorites.value = (await api.get<RadioStation[]>('/storage/favorites')).data
    } catch {
      // fallback: migrate from localStorage
      try {
        const local = JSON.parse(localStorage.getItem('home-cast-favorite-radio') || '[]')
        if (local.length) {
          for (const s of local) {
            await api.post('/storage/favorites', s)
          }
          favorites.value = (await api.get<RadioStation[]>('/storage/favorites')).data
          localStorage.removeItem('home-cast-favorite-radio')
        }
      } catch { /* ignore */ }
    }
    loaded.value = true
  }

  async function add(station: RadioStation) {
    if (isFavorite(station.stationuuid)) return
    favorites.value = (await api.post<RadioStation[]>('/storage/favorites', station)).data
  }

  async function remove(stationuuid: string) {
    favorites.value = (await api.delete<RadioStation[]>(`/storage/favorites/${stationuuid}`)).data
  }

  async function toggle(station: RadioStation) {
    if (isFavorite(station.stationuuid)) {
      await remove(station.stationuuid)
    } else {
      await add(station)
    }
  }

  function isFavorite(stationuuid: string): boolean {
    return favorites.value.some(s => s.stationuuid === stationuuid)
  }

  return { favorites, load, add, remove, toggle, isFavorite }
})
