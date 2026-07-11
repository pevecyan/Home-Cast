import type { Device } from '../api/devices'

// Icon for a playback target, shared across the picker, mini-player and cards.
export function deviceIcon(type?: Device['type']): string {
  switch (type) {
    case 'sonos':
      return 'mdi mdi-speaker'
    case 'local':
      return 'mdi mdi-cellphone'
    default:
      return 'mdi mdi-cast-audio'
  }
}
