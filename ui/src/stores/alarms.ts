import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  listAlarms, createAlarm, updateAlarm, deleteAlarm, toggleAlarm,
  type Alarm, type AlarmInput,
} from '../api/schedule'

export const useAlarmsStore = defineStore('alarms', () => {
  const alarms = ref<Alarm[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  async function load(force = false) {
    if (loaded.value && !force) return
    loading.value = true
    try {
      alarms.value = await listAlarms()
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function create(alarm: AlarmInput) {
    const created = await createAlarm(alarm)
    alarms.value.push(created)
    return created
  }

  async function update(id: string, alarm: Partial<AlarmInput>) {
    const updated = await updateAlarm(id, alarm)
    const i = alarms.value.findIndex(a => a.id === id)
    if (i !== -1) alarms.value[i] = updated
    return updated
  }

  async function remove(id: string) {
    await deleteAlarm(id)
    alarms.value = alarms.value.filter(a => a.id !== id)
  }

  async function toggle(id: string, enabled?: boolean) {
    const updated = await toggleAlarm(id, enabled)
    const i = alarms.value.findIndex(a => a.id === id)
    if (i !== -1) alarms.value[i] = updated
    return updated
  }

  return { alarms, loaded, loading, load, create, update, remove, toggle }
})
