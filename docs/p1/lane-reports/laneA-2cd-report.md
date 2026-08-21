# Lane A — M2 batches 2c/2d report (outbound guard, credential attachment, domain API, credential write)

- Status: DONE
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m2`, branch `p1/m2-domain`
- Commits:
  - `0a2c20f` — batch 2c: "Rebuild the outbound guard and credential attachment, structure
    unchanged (SR-001)" — `apps/domain/outbound.py`/`transport.py` copy-adapted verbatim
    (one import change), P0's outbound/transport/credential test suites carried over
    (120 tests total), the M1 `credential_ref` over-redaction exception added and registered.
  - `85c18e5` — batch 2d: "Rebuild the domain API surface, the raw-item browser, and the
    credential write path" — `apps/domain/api.py` (new), the raw-item pagination route, the
    `POST /sources/{id}/credentials` write path (DP-034), and `docs/p1/M2-RECORD.md`.
- Verification summary: `mypy --strict` and `ruff check` clean across `apps/` (51 source
  files, both batches); full apps pytest suite — **579 passed**, 0 failed, unsandboxed
  against `cosmai_test` (the shared docker DB container was found stopped mid-session and
  restarted; unrelated to this work, noted below).

Full deviations ledger, scenario table, and M3-deferred route list are in
`docs/p1/M2-RECORD.md`; only the essentials are repeated here.

## Concerns

- **Route scope decision (batch 2d.1).** `apps/domain/api.py` does not implement
  `POST /sources/{id}/collect` or `/import` — both would create a job dispatched through
  `addon_host.registration.HANDLER_PREFIX`, which has no P1 implementation yet, so the job
  could never be claimed. `POST /snapshots/{id}/normalize` *is* implemented per the batch
  brief's literal instruction, despite sharing the identical eventual-dispatch gap (it also
  creates a job that stays `PENDING` until M3). I could not find a technical distinction
  between normalize and collect/import that justifies including one and excluding the other,
  so I followed the literal brief and flagged the inconsistency explicitly in both
  `apps/domain/api.py`'s docstring and `docs/p1/M2-RECORD.md` rather than resolving it myself.
- **`apps/domain/api.py`'s placement is provisional.** P0 put the equivalent module in
  `addon_host/api.py`; nothing M2 built needs `addon_api`, so this batch placed it at
  `domain.api` instead (a permitted import direction). M3 must decide whether to import
  `extend_with_domain` from here or move the routes into `addon_host.api` and retire this
  file. Named in both the module docstring and M2-RECORD.
- **`HANDLER_PREFIX = "addon:"` is mirrored, not imported**, since `addon_host` doesn't exist
  yet. M3 must keep it in sync or supersede the module.
- **`test_snapshot_survives_migration.py` was not copy-adapted** (batch 2b territory, restated
  in M2-RECORD for completeness) — it depends on a per-test cloned-database model and a
  withholdable second migration directory, neither of which this tree has by design.
- **The shared docker container (`tubedepth-postgres`) was found stopped** partway through
  batch 2d (exited cleanly, status 0, cause unknown — plausibly another parallel lane).
  Restarted it (`docker start tubedepth-postgres`); all tests subsequently passed. Flagging in
  case another lane hit the same interruption.
- Batch 2c's `TestTheInstalledCollectorRunsThroughThePlatform` (P0's real-socket collector
  test through `JobRunner`+`addon_host`+`collector.naver.blog`) was deliberately omitted, not
  stubbed — it needs M3 (`addon_host`) and M4 (the add-on) infrastructure that doesn't exist
  in this tree.
