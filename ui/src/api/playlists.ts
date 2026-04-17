import axios from 'axios'
import type { Track } from './music'

const api = axios.create({ baseURL: '/api' })

export interface SavedPlaylist {
  id: string
  name: string
  tracks: Track[]
}

export const listPlaylists = () =>
  api.get<SavedPlaylist[]>('/music/playlists').then(r => r.data)

export const createPlaylist = (name: string, tracks: Track[] = []) =>
  api.post<SavedPlaylist>('/music/playlists', { name, tracks }).then(r => r.data)

export const getPlaylist = (id: string) =>
  api.get<SavedPlaylist>(`/music/playlists/${id}`).then(r => r.data)

export const updatePlaylist = (id: string, data: Partial<SavedPlaylist>) =>
  api.put<SavedPlaylist>(`/music/playlists/${id}`, data).then(r => r.data)

export const deletePlaylist = (id: string) =>
  api.delete(`/music/playlists/${id}`).then(r => r.data)

export const playSavedPlaylist = (id: string, slug: string, type: string) =>
  api.post(`/music/playlists/${id}/play`, { slug, type }).then(r => r.data)
