<script setup lang="ts">
/**
 * The app's toggle switch. A hand-rolled control (not PrimeVue's InputSwitch)
 * so every toggle in the app — Settings, Alarms, … — looks identical.
 */
defineProps<{ modelValue: boolean; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()
</script>

<template>
  <button
    type="button"
    class="toggle"
    :class="{ on: modelValue, disabled }"
    :disabled="disabled"
    @click="emit('update:modelValue', !modelValue)"
  >
    <span class="toggle-knob" />
  </button>
</template>

<style scoped>
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

.toggle.disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
