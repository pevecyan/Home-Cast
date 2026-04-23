import axios from 'axios'

const api = axios.create({ baseURL: '/api' })
const ghApi = axios.create({ baseURL: 'https://api.github.com' })

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

export const getLatestGitHubVersion = async (): Promise<string | null> => {
  try {
    const release = await ghApi
      .get<{ tag_name: string }>('/repos/pevecyan/Home-Cast/releases/latest')
      .then(r => r.data)
    return release.tag_name.replace(/^v/, '')
  } catch {
    return null
  }
}
