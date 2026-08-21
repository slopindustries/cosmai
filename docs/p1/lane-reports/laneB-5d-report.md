# Lane B — M5 batch 3 (5d) report: normalization management + downloads, UI complete

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m5`, branch `p1/m5-dashboard`
- Commits: `d951689` (extract shared mock source list), `e25f097` (normalization-management
  screen + tests), `dd7eba8` (`buildExportUrl` pure module), `f16d520` (download screen),
  `ed11068` (download screen + buildExportUrl tests), `a1efdac` (docs/p1/M5-RECORD.md updated)
- Verification: `npm run build` (`tsc -b && vite build`) — clean, 0 TypeScript errors.
  `npm test` (`vitest run`) — 34 passed, 0 failed (21 prior + 13 new). `npm run lint` (`oxlint`)
  — clean, no findings (fixed one warning found mid-batch: a component file also exporting plain
  functions/types breaks Fast Refresh — moved `buildExportUrl`/`curlLine` to their own module).
- Concerns:
  - All six DP-033 D1 screens now have a complete UI; every remaining backend interaction is
    either a real client function with no live route yet (credential write, raw items — from
    batch 5b/5c), local mock data for a route shape nothing has fixed yet (source list,
    snapshots, normalizers, normalize results, seal, create-run), or, for the download screen,
    no network call by design (it only builds and displays a URL — M6 serves the actual route).
    Full enumeration is in `docs/p1/M5-RECORD.md`'s batch 5d section.
  - Seal-snapshot and create-run POSTs are local mocks rather than real-but-unwired client
    functions, unlike batch 5b/5c's credential/raw-item calls — no route shape for either exists
    in this batch's brief or the plan (P0's reference shape exists but was not re-fixed for P1),
    so writing a real client function would have meant guessing Lane A's/M2's design.
  - Bundle grew to ~548 kB / 166 kB gzip (from ~530 kB / 162 kB), still one chunk, still over
    Vite's 500 kB warning threshold — unaddressed, consistent with prior batches' notes.
  - Batch 5-final (wiring + live integration pass) is explicitly out of scope for this batch, per
    the dispatch.
