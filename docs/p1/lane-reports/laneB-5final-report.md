# Lane B — M5 batch 5-final report: real wiring + live integration

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m5`, branch `p1/m5-dashboard`
- Commits: `13e46e4` (`git merge dev`, no conflicts), `7236dc8` (client layer reconciled against
  `apps/domain/api.py`), `e2afd95` (`CredentialForm` fix — no queryable configured status),
  `46e1bed` (collector-domain/data-browser/normalization screens wired for real), `56d5a3c`
  (`buildExportUrl` format-forcing fix), `ca6d4a2` (component tests rewritten against real
  shapes), `5dc0c08` (`docs/p1/M5-RECORD.md` batch 5-final section)
- Verification: `npm run build` clean; `npm test` 37/37 passed; `npm run lint` (oxlint) clean.
  Python no-regression gates: `mypy --strict` clean, `ruff check` clean, `apps` pytest suite
  (COSMA_TEST_DB=cosmai_test_2, port 5434) **605 passed, 2 failed** — the 2 failures are a
  pre-existing worktree-path bug in `test_outbound_transport.py`'s loopback-flag scan (its
  `SKIPPED_PARTS` list includes `.worktrees`, which matches every path when the checkout itself
  lives under `.worktrees/m5`, silently zeroing the scan), diagnosed and confirmed unrelated to
  any change in this batch (no Python touched). **Live smoke: PASS** — real API booted on
  `127.0.0.1:8100` against `cosmai_test_2`, seeded data, every wired route curl-verified
  field-by-field against the TypeScript types, and a 9/9-passing vitest run hit the real
  `api/client.ts` functions over the network with no mocks; all processes killed and ports
  confirmed closed afterward.
- Concerns:
  - Found and fixed 4 real client/backend shape mismatches by reading `apps/domain/api.py`/
    `apps/domain/export.py` directly instead of the plan's prose: (1) the raw-items page has no
    `matched` field; (2) `/export/results` accepts `jsonl` or `csv` identically to `/export/raw`,
    not CSV-only as the plan's own text implied; (3) normalize-run creation takes a normalizer
    **source id**, not an addon/version pair; (4) the credential route is genuinely write-only —
    no route anywhere can report whether a purpose is "configured," so that UI claim was removed
    rather than left resting on a mock.
  - Collect/import stay disabled with a visible note (`collect-now-button` /
    `collect-disabled-note`) — `apps/domain/api.py` never built those routes at all (M3 gap, not
    Lane B's).
  - `ConfigSchemaForm`'s field definitions remain a per-`addon_id` mock — no route exposes an
    add-on manifest's config schema yet (M3/`addon_host` territory); submitting it is still a
    no-op.
  - Bundle grew to ~589 kB / 179 kB gzip, still over Vite's warning threshold, unaddressed
    (consistent with every prior batch's note).
  - Seeded smoke-test rows remain in `cosmai_test_2` (disposable lane test DB); not cleaned up,
    per the record's own reasoning (the next pytest run resets that schema anyway).
  - Full detail — every mismatch's fix, the endpoint-to-screen wiring table, and the full smoke
    sequence — is in `docs/p1/M5-RECORD.md`'s "Batch 5-final" section.
