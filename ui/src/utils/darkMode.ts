import { ref, watchEffect } from 'vue'

const STORAGE_KEY = 'home-cast-dark-mode'

function getInitial(): boolean {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored !== null) return stored === 'true'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export const isDark = ref(getInitial())

watchEffect(() => {
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem(STORAGE_KEY, String(isDark.value))
})

export function toggleDark() {
  isDark.value = !isDark.value
}
