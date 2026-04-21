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
