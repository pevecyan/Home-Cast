<script setup lang="ts">
import Dialog from 'primevue/dialog'
import { themeMode, sleepEnabled, volumeLockEnabled, type ThemeMode } from '../utils/settings'
import FormSection from './form/FormSection.vue'
import FormRow from './form/FormRow.vue'
import FormToggle from './form/FormToggle.vue'
import SegmentedControl from './form/SegmentedControl.vue'

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
      <FormSection label="Theme">
        <SegmentedControl v-model="themeMode" :options="themeOptions" />
      </FormSection>

      <FormSection label="Features">
        <FormRow name="Sleep timer" desc="Show the sleep timer button on speakers">
          <FormToggle v-model="sleepEnabled" />
        </FormRow>
        <FormRow name="Volume lock" desc="Allow locking a speaker's volume">
          <FormToggle v-model="volumeLockEnabled" />
        </FormRow>
      </FormSection>
    </div>
  </Dialog>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
