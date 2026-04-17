import { defineStore } from 'pinia'
import { ref } from 'vue'
import { io, type Socket } from 'socket.io-client'
import {
  getDevices,
  refreshDevices,
  getDeviceState,
  pauseDevice,
  resumeDevice,
  stopDevice,
  setVolume,
  nextTrack,
  prevTrack,
  setShuffle,
  setRepeat,
  setSleepTimer,
  type Device,
  type DeviceState,
} from '../api/devices'

const VOLUME_LOCK_MS = 4000

export const useDevicesStore = defineStore('devices', () => {
  const devices = ref<Device[]>([])
  const states = ref<Record<string, DeviceState>>({})
  const loading = ref(false)
  const volumeLocks: Record<string, number> = {}
  const wsConnected = ref(false)

  let socket: Socket | null = null
  let pollInterval: number | null = null

  function sortDevices(list: Device[]) {
    return list.sort((a, b) => a.friendly_name.localeCompare(b.friendly_name))
  }

  function applyStates(newStates: Record<string, DeviceState>) {
    const now = Date.now()
    for (const [key, newState] of Object.entries(newStates)) {
      // Respect volume locks
      if (volumeLocks[key] && now < volumeLocks[key]) {
        const existing = states.value[key]
        if (existing) {
          newState.volume = existing.volume
        }
      } else {
        delete volumeLocks[key]
      }
      states.value[key] = newState
    }
  }

  // --- WebSocket ---

  function connectWs() {
    if (socket) return

    // Connect to same origin — Vite proxy (dev) or nginx (prod) handles routing
    socket = io({
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionDelayMax: 10000,
    })

    socket.on('connect', () => {
      wsConnected.value = true
      stopPolling()
    })

    socket.on('disconnect', () => {
      wsConnected.value = false
      startPolling()
    })

    socket.on('states', (data: Record<string, DeviceState>) => {
      applyStates(data)
    })

    socket.on('connect_error', () => {
      wsConnected.value = false
      if (!pollInterval) startPolling()
    })
  }

  function disconnectWs() {
    if (socket) {
      socket.disconnect()
      socket = null
    }
    wsConnected.value = false
  }

  // --- Polling fallback ---

  function startPolling() {
    if (pollInterval) return
    pollInterval = window.setInterval(() => fetchAllStates(), 5000)
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }
  }

  // --- Data fetching ---

  async function fetchDevices() {
    loading.value = true
    try {
      devices.value = sortDevices(await getDevices())
    } finally {
      loading.value = false
    }
  }

  async function fetchState(device: Device) {
    const key = `${device.slug}:${device.type}`
    try {
      const newState = await getDeviceState(device.slug, device.type)
      if (volumeLocks[key] && Date.now() < volumeLocks[key]) {
        const existing = states.value[key]
        if (existing) {
          newState.volume = existing.volume
        }
      } else {
        delete volumeLocks[key]
      }
      states.value[key] = newState
    } catch {
      // device offline
    }
  }

  async function fetchAllStates() {
    await Promise.allSettled(devices.value.map(d => fetchState(d)))
    devices.value = sortDevices([...devices.value])
  }

  function getState(device: Device): DeviceState | undefined {
    return states.value[`${device.slug}:${device.type}`]
  }

  // --- Actions ---

  async function pause(device: Device) {
    await pauseDevice(device.slug, device.type)
    if (!wsConnected.value) await fetchState(device)
  }

  async function resume(device: Device) {
    await resumeDevice(device.slug, device.type)
    if (!wsConnected.value) await fetchState(device)
  }

  async function togglePlayPause(device: Device) {
    const state = getState(device)
    if (state?.status === 'PLAYING') {
      await pause(device)
    } else {
      await resume(device)
    }
  }

  async function stop(device: Device) {
    await stopDevice(device.slug, device.type)
    if (!wsConnected.value) await fetchState(device)
  }

  async function changeVolume(device: Device, volume: number) {
    const key = `${device.slug}:${device.type}`
    volumeLocks[key] = Date.now() + VOLUME_LOCK_MS
    if (states.value[key]) {
      states.value[key] = { ...states.value[key], volume }
    }
    await setVolume(device.slug, device.type, volume)
  }

  async function next(device: Device) {
    await nextTrack(device.slug, device.type)
  }

  async function prev(device: Device) {
    await prevTrack(device.slug, device.type)
  }

  async function toggleShuffle(device: Device) {
    const state = getState(device)
    const current = state?.queue?.shuffle ?? false
    await setShuffle(device.slug, device.type, !current)
    if (!wsConnected.value) await fetchState(device)
  }

  async function cycleRepeat(device: Device) {
    const state = getState(device)
    const current = state?.queue?.repeat ?? 'off'
    const next = current === 'off' ? 'all' : current === 'all' ? 'one' : 'off'
    await setRepeat(device.slug, device.type, next)
    if (!wsConnected.value) await fetchState(device)
  }

  async function setSleep(device: Device, minutes: number) {
    await setSleepTimer(device.slug, device.type, minutes)
    if (!wsConnected.value) await fetchState(device)
  }

  const refreshing = ref(false)

  async function refresh() {
    refreshing.value = true
    try {
      devices.value = sortDevices(await refreshDevices())
      await fetchAllStates()
    } finally {
      refreshing.value = false
    }
  }

  function cleanup() {
    disconnectWs()
    stopPolling()
  }

  return {
    devices,
    states,
    loading,
    refreshing,
    wsConnected,
    fetchDevices,
    fetchState,
    fetchAllStates,
    getState,
    pause,
    resume,
    togglePlayPause,
    stop,
    changeVolume,
    next,
    prev,
    toggleShuffle,
    cycleRepeat,
    setSleep,
    refresh,
    connectWs,
    cleanup,
  }
})
