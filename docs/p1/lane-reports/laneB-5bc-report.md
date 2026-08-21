# Lane B — M5 batch 5b/5c report (frontend halves, mock-first)

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m5`, branch `p1/m5-dashboard`
- Commits: `7e23281` (credential-write + raw-item API client functions), `b96a756`
  (CredentialForm + ConfigSchemaForm components), `a083d89` (collector-domain + data-browser
  screens implemented), `768e56f` (21 vitest tests, 11 new), `95d18bb` (docs/p1/M5-RECORD.md
  updated)
- Verification: `npm run build` (`tsc -b && vite build`) — clean, 0 TypeScript errors.
  `npm test` (`vitest run`) — 21 passed, 0 failed (10 from batch 5a + 11 new). `npm run lint`
  (`oxlint`) — clean.
- Concerns:
  - Found and fixed a real bug during this batch: `ConfigSchemaForm`'s `<form>` needed
    `noValidate` — MUI's `required` prop sets the native `required` HTML attribute, and without
    `noValidate` the browser's (and jsdom's) own constraint validation silently cancels the
    `submit` event on an empty required field before the component's own `onSubmit`/validation
    ever runs. Caught by the "blocks submission" test rendering no error text at all.
  - Per the controller ruling, no client function exists yet for a source list/detail read
    (`GET /sources` or equivalent) — no shape for it exists in the plan, so `CollectorDomainScreen`
    and `DataBrowserScreen` use local hardcoded mock arrays for which domains/sources exist,
    their status, their config schema, and which credential purposes are configured. The two
    routes the brief *did* fix (`POST /sources/{id}/credentials`, `GET /sources/{id}/raw/items`)
    are real client functions, just unwired to any live backend — batch 5d's job.
  - Bundle grew from batch 5a's ~521 kB to ~530 kB gzip-161.89kB, still one chunk, still over
    Vite's 500 kB warning threshold — unaddressed, same as noted in the 5a report.
  - Full detail — every unwired endpoint listed individually, the DP-033 D2 plain-text control
    described as evidence, and the noValidate bug writeup — is in `docs/p1/M5-RECORD.md`
    (worktree, "Batch 5b/5c" section).
