# Cosmai operator dashboard

React + TypeScript + Vite (MUI, TanStack Query). Talks to the platform API at
`VITE_API_BASE` (default `http://127.0.0.1:8100`; must name a loopback host —
`src/api/client.ts`'s `apiBase()` refuses anything else, SEC-002).

Screens (`src/App.tsx`): Health, Jobs, Collectors (per-source status,
credentials, schedule, collect-now), Data Browser (raw items, plain-text
only — DP-033 D2), Normalize (seal/normalize/results), Downloads
(`/export/raw`, `/export/results`).

`npm run dev` — local dev server. `npm run build` — `tsc -b && vite build`.
`npm test` — vitest. `npm run lint` — oxlint.

`[정정, 2026-08-21, m7-fixwave, M-X7]` This file used to be the unmodified Vite
scaffold — accurate about neither this project's screens, API, nor test
setup. Replaced above.
