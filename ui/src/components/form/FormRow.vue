<script setup lang="ts">
/**
 * A single form row: a name (+ optional description) on the left and a control
 * on the right. Matches the Settings feature-row layout.
 *
 * Use the default slot for the right-hand control. When `stacked` is set the
 * control drops below the label instead — for full-width inputs (sliders,
 * selects, day chips).
 */
defineProps<{ name?: string; desc?: string; stacked?: boolean }>()
</script>

<template>
  <div class="form-row" :class="{ stacked }">
    <div v-if="name || desc" class="row-info">
      <span v-if="name" class="row-name">{{ name }}</span>
      <span v-if="desc" class="row-desc">{{ desc }}</span>
    </div>
    <div class="row-control">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 0;
}

.form-row.stacked {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.row-name {
  font-size: 0.9rem;
  color: var(--text-primary);
}

.row-desc {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.form-row.stacked .row-control {
  width: 100%;
}
</style>
