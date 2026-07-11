<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import {
  getHomeFeed,
  getMoodCategories,
  getMoodPlaylists,
  type HomeRow,
  type MoodGroup,
  type MoodChip,
  type DiscoverCard,
} from '../api/music'
import Button from 'primevue/button'
import { onImgError } from '../utils/imgFallback'

const emit = defineEmits<{
  (e: 'select', card: DiscoverCard): void
}>()

const rows = ref<HomeRow[]>([])
const moodGroups = ref<MoodGroup[]>([])
const loading = ref(false)
const refreshing = ref(false)
const error = ref(false)

// Selected mood chip (null = home feed)
const activeChip = ref<MoodChip | null>(null)
const chipsExpanded = ref(false)
const moodCards = ref<DiscoverCard[]>([])
const moodLoading = ref(false)

// Horizontal scroll element per row so the arrows can nudge them.
// NOTE: this is a plain (non-reactive) object on purpose. The template ref
// callback runs on every render; writing to a reactive ref there — and reading
// scrollState in the same template — creates a render→mutate→render loop that
// freezes the tab in production (dev's recursive-update guard masks it).
const scrollers: Record<number, HTMLElement | null> = {}
// Per-row scroll state: whether the row overflows and which edges it's at.
const scrollState = ref<Record<number, { overflow: boolean; atStart: boolean; atEnd: boolean }>>({})

// Only stash the element during render; scroll state is computed outside the
// render cycle (after load via nextTick, on @scroll, and on resize).
function setScroller(i: number, el: any) {
  scrollers[i] = (el as HTMLElement) ?? null
}

function updateScrollState(i: number) {
  const el = scrollers[i]
  if (!el) return
  // 1px tolerance for sub-pixel rounding.
  const overflow = el.scrollWidth - el.clientWidth > 1
  const atStart = el.scrollLeft <= 1
  const atEnd = el.scrollLeft >= el.scrollWidth - el.clientWidth - 1
  const prev = scrollState.value[i]
  // Skip the write when nothing changed so we never nudge reactivity needlessly.
  if (prev && prev.overflow === overflow && prev.atStart === atStart && prev.atEnd === atEnd) return
  scrollState.value[i] = { overflow, atStart, atEnd }
}

function updateAllScrollStates() {
  for (const i of Object.keys(scrollers)) updateScrollState(Number(i))
}

function scrollRow(i: number, dir: number) {
  const el = scrollers[i]
  if (el) el.scrollBy({ left: dir * el.clientWidth * 0.8, behavior: 'smooth' })
}

async function loadHome(force = false) {
  // Only show the full-page spinner on the initial load, not on a forced
  // refresh (the button shows its own spinner and existing content stays).
  if (force) refreshing.value = true
  else loading.value = true
  error.value = false
  try {
    const [home, moods] = await Promise.all([
      getHomeFeed(force),
      getMoodCategories(force).catch(() => [] as MoodGroup[]),
    ])
    rows.value = home
    moodGroups.value = moods
    // If a mood chip is open, refresh its cards too.
    if (force && activeChip.value) {
      moodCards.value = await getMoodPlaylists(activeChip.value.params, true).catch(() => moodCards.value)
    }
    await nextTick()
    updateAllScrollStates()
  } catch {
    if (!force) error.value = true
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function refresh() {
  loadHome(true)
}

async function selectChip(chip: MoodChip | null) {
  if (!chip) {
    activeChip.value = null
    moodCards.value = []
    return
  }
  if (activeChip.value?.params === chip.params) {
    // toggle off
    activeChip.value = null
    moodCards.value = []
    return
  }
  activeChip.value = chip
  moodLoading.value = true
  try {
    moodCards.value = await getMoodPlaylists(chip.params)
  } catch {
    moodCards.value = []
  } finally {
    moodLoading.value = false
  }
}

const allChips = () => moodGroups.value.flatMap(g => g.chips)

function iconFor(kind: string) {
  if (kind === 'artist') return 'mdi mdi-account-music'
  if (kind === 'song') return 'mdi mdi-music-note'
  if (kind === 'album') return 'mdi mdi-album'
  return 'mdi mdi-playlist-music'
}

onMounted(() => {
  loadHome()
  window.addEventListener('resize', updateAllScrollStates)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', updateAllScrollStates)
})

defineExpose({ reload: refresh })
</script>

<template>
  <div class="discover">
    <!-- Refresh Discover (bypasses the server cache) -->
    <div class="discover-toolbar">
      <Button
        icon="pi pi-refresh"
        rounded
        text
        size="small"
        :loading="refreshing"
        title="Refresh discover"
        @click="refresh"
      />
    </div>

    <!-- Mood / genre chips -->
    <div v-if="allChips().length" class="chips-wrap">
      <div class="chips" :class="{ expanded: chipsExpanded }">
        <button
          v-for="chip in allChips()"
          :key="chip.params"
          class="chip"
          :class="{ active: activeChip?.params === chip.params }"
          @click="selectChip(chip)"
        >
          {{ chip.title }}
        </button>
      </div>
      <button class="chips-toggle" @click="chipsExpanded = !chipsExpanded">
        <i :class="chipsExpanded ? 'mdi mdi-chevron-up' : 'mdi mdi-chevron-down'"></i>
        {{ chipsExpanded ? 'Show less' : 'More' }}
      </button>
    </div>

    <!-- Loading home -->
    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading…</span>
    </div>

    <div v-else-if="error" class="empty-state">
      <i class="mdi mdi-cloud-off-outline"></i>
      <p>Couldn't load discover feed</p>
      <button class="retry" @click="loadHome()">Retry</button>
    </div>

    <!-- Selected mood: a single grid of playlists -->
    <div v-else-if="activeChip" class="mood-section">
      <div class="row-header">
        <h2 class="row-title">{{ activeChip.title }}</h2>
        <button class="clear-mood" @click="selectChip(null)">
          <i class="mdi mdi-close"></i> Back to Discover
        </button>
      </div>
      <div v-if="moodLoading" class="loading"><div class="spinner"></div></div>
      <div v-else class="card-grid">
        <div
          v-for="(card, i) in moodCards"
          :key="`${card.kind}:${card.playlistId || card.videoId || card.browseId}:${i}`"
          class="card"
          @click="emit('select', card)"
        >
          <div class="card-thumb-wrap">
            <img v-if="card.thumbnail" :src="card.thumbnail" class="card-thumb" alt="" @error="onImgError" />
            <div class="card-thumb placeholder img-fallback" :style="{ display: card.thumbnail ? 'none' : 'flex' }">
              <i :class="iconFor(card.kind)"></i>
            </div>
          </div>
          <div class="card-title">{{ card.title }}</div>
          <div v-if="card.subtitle" class="card-sub">{{ card.subtitle }}</div>
        </div>
      </div>
    </div>

    <!-- Home feed: horizontal carousels per row -->
    <template v-else>
      <section v-for="(row, i) in rows" :key="row.title" class="feed-row">
        <div class="row-header">
          <h2 class="row-title">{{ row.title }}</h2>
          <div v-if="scrollState[i]?.overflow" class="row-nav">
            <button class="nav-btn" :disabled="scrollState[i]?.atStart" @click="scrollRow(i, -1)"><i class="mdi mdi-chevron-left"></i></button>
            <button class="nav-btn" :disabled="scrollState[i]?.atEnd" @click="scrollRow(i, 1)"><i class="mdi mdi-chevron-right"></i></button>
          </div>
        </div>
        <div class="row-scroller" :ref="el => setScroller(i, el)" @scroll="updateScrollState(i)">
          <div
            v-for="(card, j) in row.items"
            :key="`${card.kind}:${card.playlistId || card.videoId || card.browseId}:${j}`"
            class="card"
            :class="{ 'card-artist': card.kind === 'artist' }"
            @click="emit('select', card)"
          >
            <div class="card-thumb-wrap">
              <img v-if="card.thumbnail" :src="card.thumbnail" class="card-thumb" :class="{ round: card.kind === 'artist' }" alt="" @error="onImgError" />
              <div class="card-thumb placeholder img-fallback" :class="{ round: card.kind === 'artist' }" :style="{ display: card.thumbnail ? 'none' : 'flex' }">
                <i :class="iconFor(card.kind)"></i>
              </div>
              <div v-if="card.kind === 'song' || card.kind === 'playlist'" class="play-badge">
                <i class="mdi mdi-play"></i>
              </div>
            </div>
            <div class="card-title">{{ card.title }}</div>
            <div v-if="card.subtitle" class="card-sub">{{ card.subtitle }}</div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.discover {
  margin-top: 8px;
  min-width: 0;
  max-width: 100%;
}

.discover-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 4px;
}

/* Chips */
.chips-wrap {
  margin-bottom: 16px;
  max-width: 100%;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 40px; /* ~1 row collapsed */
  overflow: hidden;
  transition: max-height 0.25s ease;
}
.chips.expanded {
  max-height: 600px;
}

.chips-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 4px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-family: inherit;
  font-weight: 600;
  cursor: pointer;
}
.chips-toggle:hover { color: var(--text-primary); }
.chips-toggle i { font-size: 1rem; }

.chip {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  color: var(--text-primary);
  font-size: 0.8rem;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.chip:hover { background: var(--hover-bg); }
.chip.active {
  background: var(--p-primary-color, #6366f1);
  border-color: var(--p-primary-color, #6366f1);
  color: #fff;
}

/* Row */
.feed-row {
  margin-bottom: 24px;
  min-width: 0;
  max-width: 100%;
}

.row-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.row-title {
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.01em;
}

.row-nav { display: flex; gap: 6px; }

.nav-btn {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  color: var(--text-primary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.nav-btn:hover:not(:disabled) { background: var(--hover-bg); }
.nav-btn:disabled { opacity: 0.35; cursor: default; }
.nav-btn i { font-size: 1.2rem; }

.row-scroller {
  display: flex;
  gap: 14px;
  overflow-x: auto;
  scroll-snap-type: x proximity;
  padding-bottom: 4px;
  scrollbar-width: none;
}
.row-scroller::-webkit-scrollbar { display: none; }

/* Card */
.card {
  flex-shrink: 0;
  width: 150px;
  cursor: pointer;
  scroll-snap-align: start;
}
.card-grid .card { width: auto; }

.card-thumb-wrap {
  position: relative;
  margin-bottom: 8px;
}

.card-thumb {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 10px;
  object-fit: cover;
  display: block;
}
.card-thumb.round { border-radius: 50%; }

.card-thumb.placeholder {
  background: var(--placeholder-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--placeholder-color);
  font-size: 1.8rem;
}

.play-badge {
  position: absolute;
  right: 8px;
  bottom: 8px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--p-primary-color, #6366f1);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transform: translateY(6px);
  transition: opacity 0.15s, transform 0.15s;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
.card:hover .play-badge { opacity: 1; transform: translateY(0); }
.play-badge i { font-size: 1.3rem; }

.card-title {
  font-weight: 600;
  font-size: 0.85rem;
  line-height: 1.25;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.card-artist .card-title { text-align: center; }

.card-sub {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 2px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.card-artist .card-sub { text-align: center; }

/* Mood grid */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 16px;
}

.clear-mood {
  display: flex;
  align-items: center;
  gap: 4px;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 0.8rem;
  font-family: inherit;
  cursor: pointer;
}
.clear-mood:hover { color: var(--text-primary); }

/* Loading / empty */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 16px;
  color: var(--text-secondary);
}

.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid var(--border-color);
  border-top-color: var(--p-primary-color, #6366f1);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.empty-state {
  text-align: center;
  padding: 48px 16px;
  color: var(--text-secondary);
}
.empty-state i { font-size: 3rem; color: var(--placeholder-color); }
.empty-state p { margin-top: 8px; font-size: 0.9rem; }

.retry {
  margin-top: 12px;
  padding: 6px 16px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
  background: var(--card-bg);
  color: var(--text-primary);
  cursor: pointer;
  font-family: inherit;
}
.retry:hover { background: var(--hover-bg); }
</style>
