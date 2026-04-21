import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface Device {
  type: 'chromecast' | 'sonos'
  friendly_name: string
  slug: string
  host: string
  port: number
  cast_type?: 'audio' | 'cast' | 'group'
}

export interface QueueTrack {
  videoId: string
  title?: string
  artists?: string[]
  album?: string
  thumbnail?: string
}

export interface QueueInfo {
  currentIndex: number
  trackCount: number
  currentTrack: QueueTrack | null
  tracks: QueueTrack[]
  shuffle: boolean
  repeat: 'off' | 'all' | 'one'
}

export interface NowPlaying {
  title?: string
  thumbnail?: string
  contentId?: string
}

export interface SleepTimer {
  endsAt: string
}

export interface DeviceState {
  status: 'IDLE' | 'PLAYING' | 'PAUSED'
  volume: number
  queue?: QueueInfo
  nowPlaying?: NowPlaying
  sleepTimer?: SleepTimer
}

export const getDevices = () =>
  api.get<Device[]>('/get-devices').then(r => r.data)

export const refreshDevices = () =>
  api.post<Device[]>('/refresh-devices').then(r => r.data)

export const getDeviceState = (slug: string, type: string) =>
  api.post<DeviceState>('/device/slug/state', { slug, type }).then(r => r.data)

export const playUrl = (slug: string, type: string, url: string) =>
  api.post('/device/slug/play-url', { slug, type, url }).then(r => r.data)

export const pauseDevice = (slug: string, type: string) =>
  api.post('/device/slug/pause', { slug, type }).then(r => r.data)

export const resumeDevice = (slug: string, type: string) =>
  api.post('/device/slug/resume', { slug, type }).then(r => r.data)

export const stopDevice = (slug: string, type: string) =>
  api.post('/device/slug/stop', { slug, type }).then(r => r.data)

export const setVolume = (slug: string, type: string, volume: number) =>
  api.post('/device/slug/volume/set', { slug, type, volume }).then(r => r.data)

export const adjustVolume = (slug: string, type: string, delta: number) =>
  api.post('/device/slug/volume/delta', { slug, type, delta }).then(r => r.data)

export const nextTrack = (slug: string, type: string) =>
  api.post('/device/slug/next', { slug, type }).then(r => r.data)

export const prevTrack = (slug: string, type: string) =>
  api.post('/device/slug/prev', { slug, type }).then(r => r.data)

export const setShuffle = (slug: string, type: string, enabled: boolean) =>
  api.post('/device/slug/shuffle', { slug, type, enabled }).then(r => r.data)

export const setSleepTimer = (slug: string, type: string, minutes: number) =>
  api.post('/device/slug/sleep', { slug, type, minutes }).then(r => r.data)

export const setRepeat = (slug: string, type: string, mode: string) =>
  api.post('/device/slug/repeat', { slug, type, mode }).then(r => r.data)

export const playTrackAt = (slug: string, index: number) =>
  api.post('/device/slug/play-track', { slug, index }).then(r => r.data)

export const transferQueue = (fromSlug: string, toSlug: string, toType: string) =>
  api.post('/music/transfer', { fromSlug, toSlug, toType }).then(r => r.data)
