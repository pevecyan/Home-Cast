import { defineStore } from 'pinia'
import { ref } from 'vue'
import { playSong, playPlaylist, type Track } from '../api/music'
import { playSavedPlaylist } from '../api/playlists'
import type { Device } from '../api/devices'
import { useRecentStore } from './recent'

export interface PlayOpts {
  shuffle?: boolean
  repeat?: string
}

export const usePlayerStore = defineStore('player', () => {
  const currentTrack = ref<Track | null>(null)
  const currentDevice = ref<Device | null>(null)
  const isPlaying = ref(false)
  const isLoading = ref(false)

  async function playTrack(track: Track, device: Device, opts: PlayOpts = {}) {
    isLoading.value = true
    currentTrack.value = track
    currentDevice.value = device
    try {
      await playSong(device.slug, device.type, track.videoId, opts.shuffle, opts.repeat, track)
      isPlaying.value = true
      useRecentStore().add({
        type: 'song',
        id: track.videoId,
        title: track.title,
        subtitle: track.artists?.join(', '),
        thumbnail: track.thumbnail,
      })
    } finally {
      isLoading.value = false
    }
  }

  async function playYtPlaylist(playlistId: string, device: Device, opts: PlayOpts = {}, meta?: { title?: string, author?: string, thumbnail?: string }) {
    isLoading.value = true
    currentDevice.value = device
    try {
      await playPlaylist(device.slug, device.type, playlistId, opts.shuffle, opts.repeat)
      isPlaying.value = true
      if (meta?.title) {
        useRecentStore().add({
          type: 'playlist',
          id: playlistId,
          title: meta.title,
          subtitle: meta.author,
          thumbnail: meta.thumbnail,
        })
      }
    } finally {
      isLoading.value = false
    }
  }

  async function playSaved(playlistId: string, device: Device, opts: PlayOpts = {}, meta?: { title?: string }) {
    isLoading.value = true
    currentDevice.value = device
    try {
      await playSavedPlaylist(playlistId, device.slug, device.type, opts.shuffle, opts.repeat)
      isPlaying.value = true
      if (meta?.title) {
        useRecentStore().add({
          type: 'playlist',
          id: playlistId,
          title: meta.title,
        })
      }
    } finally {
      isLoading.value = false
    }
  }

  return {
    currentTrack,
    currentDevice,
    isPlaying,
    isLoading,
    playTrack,
    playYtPlaylist,
    playSaved,
  }
})
