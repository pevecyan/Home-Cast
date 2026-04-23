import { ref, watchEffect } from 'vue'
import { themeMode } from './settings'

const systemDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
  systemDark.value = e.matches
})

export const isDark = ref(false)

watchEffect(() => {
  if (themeMode.value === 'dark') isDark.value = true
  else if (themeMode.value === 'light') isDark.value = false
  else isDark.value = systemDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
})

export function toggleDark() {
  themeMode.value = isDark.value ? 'light' : 'dark'
}
