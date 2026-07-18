<script setup lang="ts" generic="T extends string | number">
/**
 * A row of mutually-exclusive segment buttons — the app's standard single-select
 * control (used for the theme picker, alarm repeat mode, …). Each option may
 * carry an mdi `icon`; icons stack above the label.
 */
export interface SegmentOption<V> {
  label: string
  value: V
  icon?: string
}

defineProps<{ modelValue: T; options: SegmentOption<T>[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: T] }>()
</script>

<template>
  <div class="segmented">
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      class="segment"
      :class="{ active: modelValue === opt.value, 'has-icon': !!opt.icon }"
      @click="emit('update:modelValue', opt.value)"
    >
      <i v-if="opt.icon" :class="opt.icon"></i>
      <span>{{ opt.label }}</span>
    </button>
  </div>
</template>

<style scoped>
.segmented {
  display: flex;
  gap: 8px;
}

.segment {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 8px;
  border: 1.5px solid var(--border-color);
  background: none;
  border-radius: 10px;
  color: var(--text-secondary);
  font-size: 0.8rem;
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
  font-family: inherit;
}

/* Icon variant stacks the icon above the label (theme picker). */
.segment.has-icon {
  flex-direction: column;
  gap: 6px;
  padding: 12px 8px;
}

.segment i {
  font-size: 1.3rem;
}

.segment:hover {
  background: var(--hover-bg);
  color: var(--text-primary);
}

.segment.active {
  border-color: var(--p-primary-color, #6366f1);
  color: var(--p-primary-color, #6366f1);
  background: var(--surface-dim);
}
</style>
