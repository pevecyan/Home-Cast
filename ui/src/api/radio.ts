import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface RadioStation {
  stationuuid: string
  name: string
  url: string
  favicon: string | null
  tags: string
  codec: string
  bitrate: number
  votes: number
}

export const searchRadio = (q: string) =>
  api.get<RadioStation[]>('/radio/search', { params: { q } }).then(r => r.data)

export const getPopularRadio = () =>
  api.get<RadioStation[]>('/radio/popular').then(r => r.data)

export const playRadio = (slug: string, type: string, station: RadioStation) =>
  api.post('/radio/play', {
    slug,
    type,
    stationUrl: station.url,
    stationName: station.name,
    stationFavicon: station.favicon,
  }).then(r => r.data)
