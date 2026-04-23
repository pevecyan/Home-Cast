<script setup lang="ts">
import Dialog from 'primevue/dialog'
import { themeMode, sleepEnabled, volumeLockEnabled, type ThemeMode } from '../utils/settings'

defineProps<{ visible: boolean }>()
defineEmits<{ 'update:visible': [value: boolean] }>()

const themeOptions: { label: string; value: ThemeMode; icon: string }[] = [
  { label: 'Light', value: 'light', icon: 'mdi mdi-weather-sunny' },
  { label: 'Dark',  value: 'dark',  icon: 'mdi mdi-weather-night' },
  { label: 'Auto',  value: 'auto',  icon: 'mdi mdi-theme-light-dark' },
]
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="$emit('update:visible', $event)"
    header="Settings"
    modal
    :closable="true"
    :closeOnEscape="true"
    :style="{ width: '90vw', maxWidth: '420px' }"
  >
    <div class="settings">

      <div class="settings-section">
        <div class="section-label">Theme</div>
        <div class="theme-selector">
          <button
            v-for="opt in themeOptions"
            :key="opt.value"
            class="theme-option"
            :class="{ active: themeMode === opt.value }"
            @click="themeMode = opt.value"
          >
            <i :class="opt.icon"></i>
            <span>{{ opt.label }}</span>
          </button>
        </div>
      </div>

      <div class="settings-section">
        <div class="section-label">Features</div>

        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-name">Sleep timer</span>
            <span class="setting-desc">Show the sleep timer button on speakers</span>
          </div>
          <button
            class="toggle"
            :class="{ on: sleepEnabled }"
            @click="sleepEnabled = !sleepEnabled"
          >
            <span class="toggle-knob" />
          </button>
        </div>

        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-name">Volume lock</span>
            <span class="setting-desc">Allow locking a speaker's volume</span>
          </div>
          <button
            class="toggle"
            :class="{ on: volumeLockEnabled }"
            @click="volumeLockEnabled = !volumeLockEnabled"
          >
            <span class="toggle-knob" />
          </button>
        </div>
      </div>

    </div>
  </Dialog>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-label {
  font-size: 0.7rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

/* Theme selector */
.theme-selector {
  display: flex;
  gap: 8px;
}

.theme-option {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  border: 1.5px solid var(--border-color);
  background: none;
  border-radius: 10px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
  font-family: inherit;
}

.theme-option i {
  font-size: 1.3rem;
}

.theme-option:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.theme-option.active {
  border-color: var(--p-primary-color, #6366f1);
  color: var(--p-primary-color, #6366f1);
  background: var(--surface-dim);
}

/* Feature rows */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 0;
}

.setting-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.setting-name {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.setting-desc {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

/* Toggle switch */
.toggle {
  flex-shrink: 0;
  width: 44px;
  height: 24px;
  border-radius: 12px;
  border: none;
  background: var(--border-color);
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
  padding: 0;
}

.toggle.on {
  background: var(--p-primary-color, #6366f1);
}

.toggle-knob {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: left 0.2s;
  display: block;
}

.toggle.on .toggle-knob {
  left: 23px;
}
</style>
