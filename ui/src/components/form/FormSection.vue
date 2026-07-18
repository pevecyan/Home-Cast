<script setup lang="ts">
/**
 * A titled group of form controls. `label` renders as the app's small
 * uppercase section header; the default slot holds the controls (stacked with
 * a consistent gap).
 */
defineProps<{ label?: string }>()
</script>

<template>
  <div class="form-section">
    <div v-if="label" class="section-label">{{ label }}</div>
    <slot />
  </div>
</template>

<style scoped>
.form-section {
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
</style>
