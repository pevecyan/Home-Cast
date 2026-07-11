import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Device, DeviceState, QueueTrack } from '../api/devices'
import { prefetchSong } from '../api/music'
import { useDevicesStore } from './devices'

// The browser-as-a-speaker pseudo-device. Its slug/type combine to the state
// key `local:this-browser`, which the backend never emits — so websocket
// snapshots leave it untouched (see devices store applyStates).
export const LOCAL_SLUG = 'this-browser'
export const LOCAL_TYPE = 'local' as const
export const LOCAL_KEY = `${LOCAL_SLUG}:${LOCAL_TYPE}`

export const localDevice: Device = {
  type: LOCAL_TYPE,
  friendly_name: 'This device',
  slug: LOCAL_SLUG,
  host: '',
  port: 0,
}

export function mediaUrl(videoId: string) {
  // Same-origin; served by /media/<id>.mp3 (range-capable → seekable).
  return `/api/media/${videoId}.mp3`
}

type Repeat = 'off' | 'all' | 'one'

export const useLocalPlayerStore = defineStore('localPlayer', () => {
  // The single <audio> element. Bound from App.vue, or created on demand.
  let audio: HTMLAudioElement | null = null

  const tracks = ref<QueueTrack[]>([])
  const currentIndex = ref(0)
  const repeat = ref<Repeat>('off')
  const shuffle = ref(false)
  const status = ref<'IDLE' | 'PLAYING' | 'PAUSED'>('IDLE')
  const volume = ref(1)
  const position = ref(0)
  const duration = ref(0)

  function currentTrack(): QueueTrack | null {
    return tracks.value[currentIndex.value] ?? null
  }

  function writeState() {
    const devicesStore = useDevicesStore()
    const track = currentTrack()
    const state: DeviceState = {
      status: status.value,
      volume: volume.value,
      queue: track
        ? {
            currentIndex: currentIndex.value,
            trackCount: tracks.value.length,
            currentTrack: track,
            tracks: tracks.value,
            repeat: repeat.value,
          }
        : undefined,
    }
    devicesStore.states[LOCAL_KEY] = state
  }

  function ensureAudio(): HTMLAudioElement {
    if (audio) return audio
    audio = new Audio()
    bindElement(audio)
    return audio
  }

  // Wire an <audio> element (created here or provided by App.vue) to the store.
  function bindElement(el: HTMLAudioElement) {
    audio = el
    el.volume = volume.value
    el.addEventListener('timeupdate', () => {
      position.value = el.currentTime
      if (!Number.isNaN(el.duration) && Number.isFinite(el.duration)) {
        duration.value = el.duration
      }
    })
    el.addEventListener('durationchange', () => {
      if (!Number.isNaN(el.duration) && Number.isFinite(el.duration)) {
        duration.value = el.duration
      }
    })
    el.addEventListener('play', () => {
      status.value = 'PLAYING'
      writeState()
    })
    el.addEventListener('pause', () => {
      // Ignore the pause fired right before a source switch / end handling.
      if (status.value === 'PLAYING' && !el.ended) {
        status.value = 'PAUSED'
        writeState()
      }
    })
    el.addEventListener('ended', () => {
      handleEnded()
    })
  }

  function loadCurrent(autoplay = true) {
    const el = ensureAudio()
    const track = currentTrack()
    if (!track) return
    prefetchSong(track.videoId)
    el.src = mediaUrl(track.videoId)
    position.value = 0
    duration.value = 0
    if (autoplay) {
      el.play().catch(() => { /* autoplay gesture may be required */ })
    }
    writeState()
  }

  function handleEnded() {
    if (repeat.value === 'one') {
      loadCurrent(true)
      return
    }
    const atEnd = currentIndex.value >= tracks.value.length - 1
    if (atEnd) {
      if (repeat.value === 'all' && tracks.value.length > 0) {
        currentIndex.value = 0
        loadCurrent(true)
      } else {
        status.value = 'IDLE'
        writeState()
      }
    } else {
      currentIndex.value += 1
      loadCurrent(true)
    }
  }

  function shuffleTracks(list: QueueTrack[], keepFirstIndex: number): { list: QueueTrack[]; index: number } {
    // Fisher-Yates over a copy, then move the intended current track to front.
    const arr = [...list]
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      ;[arr[i], arr[j]] = [arr[j], arr[i]]
    }
    const target = list[keepFirstIndex]
    const at = arr.findIndex(t => t.videoId === target?.videoId)
    if (at > 0) {
      arr.splice(at, 1)
      arr.unshift(target)
    }
    return { list: arr, index: 0 }
  }

  // --- Public transport API ---

  function play(list: QueueTrack[], index = 0, opts: { shuffle?: boolean; repeat?: Repeat } = {}) {
    shuffle.value = !!opts.shuffle
    repeat.value = opts.repeat ?? 'off'
    if (shuffle.value && list.length > 1) {
      const s = shuffleTracks(list, index)
      tracks.value = s.list
      currentIndex.value = s.index
    } else {
      tracks.value = [...list]
      currentIndex.value = Math.min(Math.max(index, 0), Math.max(list.length - 1, 0))
    }
    loadCurrent(true)
  }

  function resume() {
    ensureAudio().play().catch(() => {})
  }

  function pause() {
    audio?.pause()
  }

  function toggle() {
    if (status.value === 'PLAYING') pause()
    else resume()
  }

  function stop() {
    if (audio) {
      audio.pause()
      audio.removeAttribute('src')
      audio.load()
    }
    tracks.value = []
    currentIndex.value = 0
    status.value = 'IDLE'
    position.value = 0
    duration.value = 0
    writeState()
  }

  function next() {
    if (tracks.value.length === 0) return
    if (currentIndex.value < tracks.value.length - 1) {
      currentIndex.value += 1
    } else if (repeat.value === 'all') {
      currentIndex.value = 0
    } else {
      return
    }
    loadCurrent(true)
  }

  function prev() {
    if (tracks.value.length === 0) return
    // Restart current track if we're more than 3s in, else go back.
    if (position.value > 3) {
      seek(0)
      return
    }
    if (currentIndex.value > 0) {
      currentIndex.value -= 1
    } else if (repeat.value === 'all') {
      currentIndex.value = tracks.value.length - 1
    } else {
      seek(0)
      return
    }
    loadCurrent(true)
  }

  function jumpTo(index: number) {
    if (index < 0 || index >= tracks.value.length) return
    currentIndex.value = index
    loadCurrent(true)
  }

  function setVolume(v: number) {
    volume.value = Math.min(Math.max(v, 0), 1)
    if (audio) audio.volume = volume.value
    writeState()
  }

  function cycleRepeat() {
    repeat.value = repeat.value === 'off' ? 'all' : repeat.value === 'all' ? 'one' : 'off'
    writeState()
  }

  function seek(seconds: number) {
    const el = ensureAudio()
    el.currentTime = Math.min(Math.max(seconds, 0), duration.value || seconds)
    position.value = el.currentTime
  }

  // Snapshot for handing off to a physical speaker.
  function snapshot() {
    return {
      tracks: tracks.value,
      currentIndex: currentIndex.value,
      repeat: repeat.value,
      position: position.value,
    }
  }

  return {
    // state
    tracks,
    currentIndex,
    repeat,
    shuffle,
    status,
    volume,
    position,
    duration,
    // element wiring
    bindElement,
    // transport
    play,
    resume,
    pause,
    toggle,
    stop,
    next,
    prev,
    jumpTo,
    setVolume,
    cycleRepeat,
    seek,
    snapshot,
    currentTrack,
  }
})
