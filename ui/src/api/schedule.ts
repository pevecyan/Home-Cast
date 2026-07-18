import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export type AlarmActionKind = 'playlist' | 'radio'
export type RepeatMode = 'off' | 'all' | 'one'

export interface AlarmTarget {
  /** device slug, or 'all' to fan out */
  slug: string
  /** device type, or 'all' */
  type: string
}

export interface AlarmAction {
  kind: AlarmActionKind
  /** saved-playlist id (kind==playlist) or station uuid (kind==radio) */
  ref: string | null
  /** display label captured at save time (playlist/station name) */
  name?: string
}

export interface Alarm {
  id: string
  /** HH:MM, 24h */
  time: string
  /** weekday mask, Mon=0..Sun=6; [] = one-shot */
  days: number[]
  target: AlarmTarget
  action: AlarmAction
  shuffle: boolean
  repeat: RepeatMode
  /** 0..1, applied before play; null = leave volume as-is */
  volume: number | null
  /** seconds to ramp volume from low to target; 0 = no fade */
  fadeIn: number
  enabled: boolean
}

export type AlarmInput = Omit<Alarm, 'id'>

export const listAlarms = () =>
  api.get<Alarm[]>('/schedule/alarms').then(r => r.data)

export const createAlarm = (alarm: AlarmInput) =>
  api.post<Alarm>('/schedule/alarms', alarm).then(r => r.data)

export const updateAlarm = (id: string, alarm: Partial<AlarmInput>) =>
  api.put<Alarm>(`/schedule/alarms/${id}`, alarm).then(r => r.data)

export const deleteAlarm = (id: string) =>
  api.delete(`/schedule/alarms/${id}`).then(r => r.data)

export const toggleAlarm = (id: string, enabled?: boolean) =>
  api.post<Alarm>(`/schedule/alarms/${id}/toggle`, enabled === undefined ? {} : { enabled }).then(r => r.data)
