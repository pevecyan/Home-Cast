<script setup lang="ts">

const query = defineModel<string>('query', { default: '' })
const filterType = defineModel<string>('filterType', { default: 'songs' })

const emit = defineEmits<{
  search: [query: string, type: string]
}>()

const typeOptions = [
  { label: 'Songs', value: 'songs', icon: 'mdi-music-note' },
  { label: 'Artists', value: 'artists', icon: 'mdi-account-music' },
  { label: 'Playlists', value: 'playlists', icon: 'mdi-playlist-music' },
  { label: 'Albums', value: 'albums', icon: 'mdi-album' },
]

function onSubmit() {
  if (query.value.trim()) {
    emit('search', query.value.trim(), filterType.value)
  }
}
</script>

<template>
  <div class="search-bar">
    <form @submit.prevent="onSubmit" class="search-form">
      <div class="search-input-container">
        <i class="mdi mdi-magnify search-icon"></i>
        <input
          v-model="query"
          type="text"
          placeholder="What do you want to listen to?"
          class="search-input"
        />
        <button
          v-if="query"
          type="button"
          class="clear-btn"
          @click="query = ''"
        >
          <i class="mdi mdi-close"></i>
        </button>
      </div>
    </form>
    <div class="filter-row">
      <button
        v-for="opt in typeOptions"
        :key="opt.value"
        class="filter-pill"
        :class="{ active: filterType === opt.value }"
        @click="filterType = opt.value"
      >
        <i :class="'mdi ' + opt.icon"></i>
        {{ opt.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>

.search-input-container {
  display: flex;
  align-items: center;
  background: var(--card-bg);
  border-radius: 12px;
  padding: 0 16px;
  box-shadow: 0 1px 4px var(--surface-dim);
  transition: box-shadow 0.2s;
}

.search-input-container:focus-within {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12);
}

.search-icon {
  font-size: 1.3rem;
  color: var(--text-secondary);
  margin-right: 10px;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  background: none;
  font-size: 1rem;
  padding: 14px 0;
  color: var(--text-primary);
  font-family: inherit;
  min-width: 0;
  width: 0;
}

.search-input::placeholder {
  color: var(--text-secondary);
}

.clear-btn {
  border: none;
  background: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 4px;
  display: flex;
  align-items: center;
  font-size: 1.1rem;
}

.search-bar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.filter-row {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.filter-row::-webkit-scrollbar {
  display: none;
}

.filter-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 20px;
  border: 1.5px solid var(--border-color);
  background: var(--card-bg);
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-family: inherit;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s;
}

.filter-pill i {
  font-size: 1rem;
}

.filter-pill:hover {
  border-color: var(--text-secondary);
  background: #fafafa;
}

.filter-pill.active {
  background: var(--p-primary-color, #6366f1);
  border-color: var(--p-primary-color, #6366f1);
  color: white;
}
</style>
