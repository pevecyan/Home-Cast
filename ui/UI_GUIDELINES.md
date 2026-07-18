# Home-Cast UI Guidelines

How to build views and dialogs so the app stays visually consistent. Read this
before adding a new view, dialog, or form control. When in doubt, copy an
existing screen rather than inventing spacing/colors.

## Design tokens (CSS variables)

Never hardcode colors. Use the variables from [`src/style.css`](src/style.css);
they flip automatically for dark mode via the `.dark` class.

| Token | Use for |
| --- | --- |
| `--app-bg` | page background |
| `--card-bg` | cards, dialogs, sidebar |
| `--text-primary` | primary text, headings |
| `--text-secondary` | subtitles, descriptions, hints, icons |
| `--border-color` | borders, dividers, unselected control outlines |
| `--hover-bg` | hover state on buttons/rows |
| `--surface-dim` | active/selected fill (segments, chips, active nav) |
| `--subtle-bg` | faint alternate surfaces |
| `--placeholder-bg` / `--placeholder-color` | empty artwork placeholders |
| `--p-primary-color` (fallback `#6366f1`) | accent: active/selected, primary actions |

The accent must always be written `var(--p-primary-color, #6366f1)`.

## Spacing scale

Stick to this scale (px): **2, 4, 6, 8, 10, 12, 14, 16, 20, 24**. Don't use
values off it (no 5, 15, 18, 22…) except where a control's internal geometry
demands it.

- **View padding:** `16px` on the view root (`.some-view { padding: 16px }`).
- **Section gap** (between groups of controls): `24px`.
- **Control gap** (within a group / list of rows): `12px`.
- **Row internal gap** (label ↔ control): `16px`.
- **Card padding:** `12px 16px` for list rows, `14px 16px` for standalone cards.
- **Border radius:** `10px` inputs/buttons, `14px` cards, `999px` pills/chips,
  `8px` small thumbnails.

## Typography

| Role | Size / weight |
| --- | --- |
| Page title (`.page-title`) | `1.5rem` / `700` |
| Section label (uppercase) | `0.7rem` / `700`, `text-transform: uppercase`, `letter-spacing: 0.08em`, secondary color |
| Row name | `0.9rem`, primary |
| Row description / hint | `0.75rem`, secondary |
| Body / list item | `0.9rem` |
| Small meta | `0.8rem`, secondary |

Use `font-variant-numeric: tabular-nums` for times, durations, and numeric
readouts so digits don't jitter.

## View skeleton

Every top-level view follows this shape (see
[`views/SavedPlaylistsView.vue`](src/views/SavedPlaylistsView.vue),
[`views/AlarmsView.vue`](src/views/AlarmsView.vue)):

```vue
<template>
  <div class="xyz-view">
    <div class="header-row">
      <h1 class="page-title">Title</h1>
      <!-- add button, if any -->
      <Button icon="pi pi-plus" rounded text @click="..." />
    </div>
    <!-- loading / empty / content states -->
  </div>
</template>

<style scoped>
.xyz-view { padding: 16px; }
.header-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.page-title { font-size: 1.5rem; font-weight: 700; }
</style>
```

**Add/create buttons** use the PrimeVue icon button: `<Button icon="pi pi-plus"
rounded text />`. Row-level actions (play/edit/delete) use `rounded text
size="small"`, with `severity="danger"` for destructive ones.

Always provide **loading**, **empty**, and (where relevant) **error** states —
don't render a bare blank area.

## Forms: use the shared primitives

We have a small set of form primitives in
[`src/components/form/`](src/components/form/). **Use them instead of PrimeVue's
`InputSwitch`/`Slider` or ad-hoc markup** so every form matches Settings.

| Component | Purpose |
| --- | --- |
| `FormSection` | titled group; `label` renders the uppercase section header, slot holds controls (12px gap) |
| `FormRow` | one row: `name` + optional `desc` on the left, control in the slot. `stacked` drops the control below the label for full-width inputs (sliders, selects, chips) |
| `FormToggle` | the app's on/off switch (`v-model:boolean`). This is the ONLY toggle — never use PrimeVue `InputSwitch`/`ToggleSwitch` |
| `SegmentedControl` | mutually-exclusive segment buttons (`v-model`, `options: {label, value, icon?}[]`). Used for theme, repeat mode, etc. |

Example (from AlarmsView):

```vue
<FormSection label="Volume">
  <FormRow name="Set volume" desc="Adjust before playback starts">
    <FormToggle v-model="form.volumeEnabled" />
  </FormRow>
  <FormRow v-if="form.volumeEnabled" stacked>
    <div class="slider-row">
      <input v-model.number="form.volume" type="range" min="0" max="100" class="range grow" />
      <span class="slider-val">{{ form.volume }}%</span>
    </div>
  </FormRow>
</FormSection>
```

Native `<input type="range">` should carry `accent-color: var(--p-primary-color,
#6366f1)`. Native `<input type="time">` uses the `.time-input` styling
(border `1px solid var(--border-color)`, radius `10px`, `--surface-dim` bg).

**Dropdown lists** (pick-one from a data list): PrimeVue `Select` is acceptable
— it's the one PrimeVue input we keep, since we have no native equivalent.

### When to add a new primitive vs. inline styles

If you're about to write CSS that duplicates something already in Settings or
another view (a toggle, a chip row, a segmented picker), **extract or reuse a
primitive** in `components/form/` rather than copy-pasting. One-off layout glue
(a `.slider-row` flex wrapper) can stay local.

## Dialogs

```vue
<Dialog modal :closable="true" :closeOnEscape="true"
        :style="{ width: '90vw', maxWidth: '420px' }" header="…">
  <div class="body" style="display:flex; flex-direction:column; gap:24px">…</div>
  <template #footer>
    <Button label="Cancel" text @click="…" />
    <Button label="Save" :disabled="…" @click="…" />
  </template>
</Dialog>
```

- `maxWidth`: `400–440px` for forms/settings; `480px` for content (changelog).
- Body is a `24px`-gap flex column of `FormSection`s.
- Footer: secondary action `text`, primary action solid, disabled when invalid.

## Icons

`mdi` (Material Design Icons) for domain/content icons (`mdi mdi-alarm`,
`mdi mdi-radio`, `mdi mdi-playlist-music`). `pi` (PrimeIcons) for generic action
buttons (`pi pi-plus`, `pi pi-play`, `pi pi-trash`, `pi pi-pencil`). Speaker/
target icons come from [`utils/deviceIcon.ts`](src/utils/deviceIcon.ts) —
use it, don't re-derive.
