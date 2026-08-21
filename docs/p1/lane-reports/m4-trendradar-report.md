# M4 — collector.trendradar.rest report

- Status: DONE, with one unresolved architecture concern (live smoke did not succeed — see Concerns)
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4-trendradar`, branch `p1/m4-trendradar`
- Commits:
  - `9273ded` — "An adapter for trend-radar: buckets under the cap, filters verified by echo, no credential to hold" —
    `apps/addons/collector.trendradar.rest/{addon.toml,handler.py,README.md}` (new collector);
    `apps/tests/fixtures/public/collector.trendradar.rest/` (9 real captured response
    shapes + `runs`/`sources`, provenance in `MANIFEST.md`); `apps/tests/test_collector_trendradar.py`
    (15 tests); `apps/pyproject.toml` (`[tool.mypy] exclude = ["^addons/"]`, new).
  - `efcfafc` — "Add apps/scripts/check-addons.sh, mirroring the root's per-addon check script" —
    the explicit-path checker the exclude above needs so add-ons stay checked somewhere.
- Verification:
  - `cd apps && uv run mypy --strict .` — clean, 89 source files (`addons/` excluded, see
    below).
  - `cd apps && uv run mypy --strict addons/collector.trendradar.rest/handler.py` — clean.
  - `cd apps && ./scripts/check-addons.sh` — `collector.trendradar.rest  ok`.
  - `cd apps && uv run ruff check .` — clean.
  - `apps/tests/test_collector_trendradar.py` — **15 passed** (host-loading, `_Budget`,
    first-run hour-bucket pagination, no-new-bucket skip, multi-page catch-up, filters-echo
    refusal, full-scan pagination + a non-`board` table, source discovery, 5 config-validation
    cases, conformance incl. cursor resume).
  - Full `apps` suite, unsandboxed, real DB (`COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434
    COSMA_DB_NAME=cosmai_test_4 COSMA_DB_USER=cosmai_runtime COSMA_TEST_DB=cosmai_test_4
    ../scripts/with-secret-source.sh uv run python -m pytest -q`) — **813 passed, 2 failed**
    (both pre-existing and out of scope — see Concerns).
  - Root guard: `.venv/bin/python -m pytest tests/environment -q` — **87 passed**.
  - **LIVE smoke (unsandboxed), through the real host worker**: registered
    `trendradar-smoke` (`outbound_profile.hosts=["127.0.0.1"]`, `port=8000`,
    `allow_loopback=true`, endpoints `runs`+`records_rank_snapshot`), created one collect
    job, ran it through `Worker`+`capability_registry(SocketTransport(), ...)` against
    `cosmai_test_4`. **Did not collect.** Attempt outcome `RETRYABLE_FAILURE` /
    `PLATFORM_TRANSIENT`, `error_summary`: `"no checked address for '127.0.0.1' accepted a
    connection"`, `error_detail.cause`: `"SSLError"`. `raw_item` count for the source: **0**.
    Source row, job, job_attempt, and any raw rows deleted afterward (`cosmai_test_4` is
    shared sequentially across every M2-M7 lane). Root cause and why it is not fixed here:
    first Concern below.

## Concerns

- **The platform's outbound guard cannot reach trend-radar at all — measured, not just
  read.** `domain/outbound.py`'s `resolve()` builds every request URL as
  `f"https://{host}:{profile.port}{path}"` unconditionally (`ALLOWED_SCHEMES = {"https"}`,
  `p0-security.md`: "허용 HTTPS scheme"), and `domain/transport.py`'s `SocketTransport`
  always does a TLS handshake (`http.client.HTTPSConnection` + `context.wrap_socket`) —
  there is no HTTP-only code path anywhere in `domain`. `[측정]` trend-radar's live
  instance (`shared-db-trend-radar-dashboard-1`, port 8000) speaks plain HTTP only:
  `curl http://127.0.0.1:8000/api/v1/health` succeeds (`200`), `curl -k
  https://127.0.0.1:8000/api/v1/health` fails with `SSL routines::wrong version number`.
  Running the real collect job end-to-end (above) confirms this is load-bearing, not
  theoretical: the attempt failed with `cause: SSLError` before any HTTP request was
  even framed, and would fail identically on every retry — `allow_loopback` only relaxes
  the *address-range* check (`check_resolved_addresses`), never the scheme. DP-031 D3
  fixes **both** adapter targets as plain HTTP (`http://127.0.0.1:8000` and
  `http://127.0.0.1:8080` for tubedepth), so `collector.tubedepth.rest` will hit the
  identical wall. **Not fixed here**: changing `ALLOWED_SCHEMES`/`SocketTransport` is a
  `domain` (M2) change and, per AGENTS.md, touches "security or privacy policy" —
  a consequential direction requiring an Open Question and an owner decision, not a
  silent fix inside an M4 add-on task. Recorded as a finding for the orchestrator/owner:
  the two P1 adapter targets DP-031 fixed are unreachable through the platform as built,
  and someone has to decide whether the outbound guard gains a scoped HTTP allowance
  (e.g. gated the same way `allow_loopback` gates the address check) or whether the two
  targets need a TLS-terminating proxy in front of them instead. This add-on's own logic
  (pagination, cursor, filters-echo) is verified correct against the fixtures and the
  conformance suite; what is unverified is the platform's ability to carry its requests
  to the live target at all.
- **Two pre-existing, out-of-scope test failures**, identical to what M4's
  `importer.local.jsonl`/`normalizer.obf.product` lane independently found and reported
  (`m4-importer-obf-report.md`): `tests/test_outbound_transport.py::
  TestLoopbackIsOnlyReachableByFlag` computes `REPO_ROOT = Path(__file__).resolve().parents[2]`,
  which lands on the worktree's own root when run from `.worktrees/<name>/apps/`, and then
  skips every file whose `path.parts` contains `.worktrees` — which is every file, since the
  worktree's own absolute path contains that segment. Both cases fail with an empty scan
  result. Confirmed structural (not caused by this task's diff, which never touches
  `domain/outbound.py` or this test file) and already flagged by a sibling lane; not
  repaired here — out of this task's area (M2's outbound guard) and someone else's file.
- **`captured_at` filter 500s on the live trend-radar instance** (every ISO 8601 encoding
  tried). `service/trend-radar` is read-only to this project; not investigated further or
  fixed there. This is the reason the collector never sends `captured_at` as a request
  parameter — see `handler.py`'s module docstring and the fixture `MANIFEST.md` for the
  exact reproduction. A practical consequence rather than a blocker: the collector still
  achieves bounded, incremental, per-bucket collection by filtering on `source`(+`board`)
  and relying on the API's own `captured_at DESC` ordering plus its own stored cursor.
- **Cursor granularity extends the spec's literal text by one level** (per-table-per-source
  rather than per-table), a local representation choice inside the one declared stream —
  does not reopen OQ-010. Documented in both `handler.py`'s module docstring and the
  add-on's `README.md`.
- **No normalizer in this batch**, as instructed (RC-005 deferred); Raw rows are
  browseable/exportable without one.
- **`apps/pyproject.toml`'s `addons/` mypy exclude and `apps/scripts/check-addons.sh` are
  new, shared infrastructure**, not scoped to this one add-on. First hit here (this add-on's
  `handler.py` collided with `tests/fixtures/normalizer.conformance/handler.py` in mypy's
  module namespace); a sibling M4 lane (`m4-importer-obf`) independently hit and fixed the
  same collision the same way in its own worktree. Both fixes will need reconciling (they
  should be identical or near-identical) when M7 merges every M4 lane's `apps/addons/*` into
  one tree.
