import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface Track {
  videoId: string
  title: string
  artists: string[]
  album?: string
  duration?: string
  thumbnail?: string
}

export interface Artist {
  browseId: string
  name: string
  thumbnail?: string
}

export interface Playlist {
  playlistId: string
  title: string
  author?: string
  thumbnail?: string
  trackCount?: number
}

export interface ArtistDetail {
  name: string
  thumbnail?: string
  songs: Track[]
}

export interface PlaylistDetail {
  title: string
  author?: string
  thumbnail?: string
  trackCount?: number
  tracks: Track[]
}

export interface AlbumDetail {
  title: string
  artists: string[]
  year?: string
  thumbnail?: string
  trackCount?: number
  audioPlaylistId?: string
  tracks: Track[]
}

// --- Discover ---

export interface DiscoverCard {
  kind: 'playlist' | 'song' | 'album' | 'artist'
  title: string
  subtitle?: string
  thumbnail?: string
  playlistId?: string
  videoId?: string
  browseId?: string
  artists?: string[]
}

export interface HomeRow {
  title: string
  items: DiscoverCard[]
}

export interface MoodChip {
  title: string
  params: string
}

export interface MoodGroup {
  title: string
  chips: MoodChip[]
}

export const getHomeFeed = (refresh = false) =>
  api.get<HomeRow[]>('/music/home', { params: refresh ? { refresh: 1 } : {} }).then(r => r.data)

export const getMoodCategories = (refresh = false) =>
  api.get<MoodGroup[]>('/music/moods', { params: refresh ? { refresh: 1 } : {} }).then(r => r.data)

export const getMoodPlaylists = (params: string, refresh = false) =>
  api.get<DiscoverCard[]>(`/music/moods/${encodeURIComponent(params)}`, { params: refresh ? { refresh: 1 } : {} }).then(r => r.data)

export const searchMusic = (q: string, type: string = 'songs') =>
  api.get('/music/search', { params: { q, type } }).then(r => r.data)

export const getArtist = (browseId: string) =>
  api.get<ArtistDetail>(`/music/artist/${browseId}`).then(r => r.data)

export const getPlaylist = (playlistId: string) =>
  api.get<PlaylistDetail>(`/music/playlist/${playlistId}`).then(r => r.data)

export const getAlbum = (browseId: string) =>
  api.get<AlbumDetail>(`/music/album/${browseId}`).then(r => r.data)

export const prefetchSong = (videoId: string) =>
  api.post('/music/prefetch', { videoId }).catch(() => { /* best-effort */ })

export const playSong = (slug: string, type: string, videoId: string, shuffle = false, repeat = 'off', track?: Partial<Track>) =>
  api.post('/music/play', { slug, type, videoId, shuffle, repeat, track }).then(r => r.data)

export const playPlaylist = (slug: string, type: string, playlistId: string, shuffle = false, repeat = 'off') =>
  api.post('/music/play', { slug, type, playlistId, shuffle, repeat }).then(r => r.data)

// Play an explicit ordered track list on a speaker (used for browser → speaker handoff).
export const playTracksOn = (slug: string, type: string, tracks: Partial<Track>[], startIndex = 0, repeat = 'off') =>
  api.post('/music/play', { slug, type, tracks, startIndex, repeat }).then(r => r.data)
