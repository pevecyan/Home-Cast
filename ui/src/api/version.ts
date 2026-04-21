import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface ChangelogEntry {
  version: string
  date: string
  changes: string[]
}

export interface VersionInfo {
  version: string
  changelog: ChangelogEntry[]
}

export const getVersion = () =>
  api.get<VersionInfo>('/version').then(r => r.data)
