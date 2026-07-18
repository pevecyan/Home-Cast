# Frontend (ui/)

Vue 3 + TypeScript SPA, PrimeVue components, Pinia stores, Vite.

**Before building any view, dialog, or form control, read
[UI_GUIDELINES.md](UI_GUIDELINES.md).** It defines the design tokens, spacing
scale, view skeleton, and the shared form primitives in
[`src/components/form/`](src/components/form/) (`FormSection`, `FormRow`,
`FormToggle`, `SegmentedControl`). Reuse those instead of PrimeVue
`InputSwitch`/`Slider` or ad-hoc markup so screens stay visually identical.

## Layout
- `api/` — thin axios wrappers, one file per backend area, typed request/response.
- `stores/` — Pinia stores hold state + actions; views stay thin.
- `views/` — routed pages (registered in `router/index.ts` + nav in `App.vue`).
- `components/` — reusable pieces; `components/form/` are the shared form primitives.

## Checks
- Typecheck: `npx vue-tsc --noEmit -p tsconfig.app.json`
- Build: `npm run build` (note: the terser minify step fails on Node 18 with a
  `crypto is not defined` error — this is environmental and unrelated to app
  code; compilation/transform succeeding is the signal that your changes are OK).
