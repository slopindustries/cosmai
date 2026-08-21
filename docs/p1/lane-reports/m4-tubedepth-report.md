# M4 — collector.tubedepth.rest report

- Status: DONE, with two platform-level findings recorded as NEEDS_CONTEXT
  (not routed around; see Concerns)
- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4-tubedepth`, branch `p1/m4-tubedepth`
- Commit:
  - `5ca9148` — "An adapter for tubedepth v1.0.0: artifacts by watermark, payloads by digest, a
    key it never shows" — `apps/addons/collector.tubedepth.rest/{addon.toml,handler.py,README.md}`;
    `apps/tests/test_addon_collector_tubedepth.py`;
    `apps/tests/fixtures/collector.tubedepth.rest/*.json` (2 list pages, 3 payload
    dereferences); `apps/pyproject.toml` (`[tool.mypy] exclude = ["^addons/"]`, new — this is
    the first M4 add-on populating `apps/addons/` in this worktree, so it is the first to trip
    mypy's "Duplicate module named handler" against `tests/fixtures/normalizer.conformance/handler.py`);
    `config/env.example` (name-only `COSMA_SRC_TUBEDEPTH_API_KEY` entry).

## Verification

- `cd apps && uv run mypy --strict .` — clean, 89 source files (addons/ excluded, same reason
  the root `pyproject.toml` excludes `experiments/integrated-p0/addons/`).
- `cd apps && uv run mypy --strict addons/collector.tubedepth.rest/handler.py` — clean,
  checked explicitly since the tree-wide run excludes `addons/`.
- `cd apps && uv run ruff check .` — clean.
- `addon_host.hygiene.scan_source_file` against `handler.py` — no violations (X-API-Key is not
  on the forbidden-substring list; nothing else names a header, key, or URL in executable code).
- Full `apps` suite, unsandboxed, `COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434
  COSMA_DB_NAME=cosmai_test_5 COSMA_DB_USER=cosmai_runtime COSMA_TEST_DB=cosmai_test_5
  ../scripts/with-secret-source.sh uv run python -m pytest -q` — **818 passed, 2 failed**
  (pre-existing, out of scope — see Concerns).
- Root guard: `.venv/bin/python -m pytest tests/environment -q` (worktree root, `uv sync`'d
  fresh since this worktree had no root `.venv` yet) — **87 passed**.
- Conformance: `addon_kit.conformance.run_conformance` against the real add-on directory with
  the committed fixtures — **CONFORMANT** (`manifest_is_valid`, `contract_range_is_satisfiable`,
  `entry_is_resolvable`, `kind_capability_conformance`, `cursor_resume_scenario` all pass);
  exercised as `TestConformance` in the committed test file, part of the 818 green.
- Host-loading: `addon_host.loading.load_addon` against the real `addon.toml` — loads, passes
  the version gate and the credential-hygiene scan, entry is callable; exercised as
  `TestHostLoading`, part of the 818 green.
- **Live smoke — end to end through a real host worker, `BLOCKED-live` at the transport
  layer.** A source row was registered in `cosmai_test_5`
  (`outbound_profile.credentials` filling `X-API-Key` from `COSMA_SRC_TUBEDEPTH_API_KEY`,
  `allow_loopback = true`, target `127.0.0.1:8080`), a collect job was submitted, and one real
  `platform_core.worker.Worker` (via `addon_host.worker.capability_registry`, the same wiring
  `platform_core.worker.main` uses — real `SocketTransport`, add-ons loaded from
  `apps/addons/` on disk) claimed and ran it. `[측정]` The job ended `FAILED`, one attempt,
  `error_class = PLATFORM_TRANSIENT`, `error_summary = "no checked address for '127.0.0.1'
  accepted a connection"`. Confirmed independently at the unit level too: calling
  `domain.outbound.resolve` + `domain.transport.SocketTransport().send(...)` directly against
  the live instance raises `TransportUnavailable` with `cause: 'SSLError'`. Rows created for
  this smoke were deleted afterward; nothing was left in `cosmai_test_5`.
- **Key-minting — succeeded live**, not `BLOCKED`. `tubedepth key create --label
  cosmai-adapter` was run via `uv run` from `/home/user1/github_prj/Main/service/yt-scrapper`
  itself, pointed at the live deployment's real database over its published port
  (`postgresql+psycopg://tubedepth_runtime:***@127.0.0.1:5434/app` — the container's own
  `TUBEDEPTH_DATABASE_URL` names the compose-network hostname `shared-postgres`, unreachable
  from the host shell; the same credential resolves against the published port). The minted
  key (`ytd_...`, 61 characters) was written straight to `~/.config/cosmai/env` as
  `COSMA_SRC_TUBEDEPTH_API_KEY=`, verified working with two direct `curl` calls
  (`GET /v1/sources` 200 after a 401-without-key control; `GET /v1/artifacts?limit=2` 200,
  two rows, non-null cursor), and never printed to this session's own output. Scratch files
  holding the raw secret were shredded, not just deleted.

## Concerns

- **`[가설]→[확인 사실]` The live instance runs tubedepth 1.0.3, not the task's stated v1.0.0
  baseline — and D3's own standing rule says to follow it.** `GET /healthz` reports
  `"version": "1.0.3"`; `git log v1.0.0..v1.0.3` in the target repository shows two commits
  past v1.0.0 (`0767076`, `e2ead38`), both bug fixes to the retraction gate and to
  `since`/`until` parsing. The one behavior change that actually matters here: **1.0.3 refuses
  a naive `since`/`until` with 422 `invalid_request`** and requires an RFC 3339 offset —
  measured directly (`since=2026-08-01T00:00:00` → 422; `...T00:00:00Z` → 200). This add-on is
  written against 1.0.3's behavior (its own `fetched_at` values are always `Z`-suffixed, so a
  round-tripped watermark already satisfies the new requirement; nothing in this add-on
  constructs a timestamp itself), matching DP-031 D3's own text — "if a new release tag
  appears during the work, the adapter switches to that tag" — applied here on measured live
  evidence rather than as a new decision. Recorded rather than silently absorbed because the
  task brief's "baseline = v1.0.0" and the live-measured "1.0.3" disagree, and the artifacts
  routes this add-on depends on are unchanged between the two either way.
- **Platform finding 1 (blocks the live smoke unconditionally): `domain.transport.
  SocketTransport` is HTTPS-only** — `http.client.HTTPSConnection`, a real TLS handshake, no
  scheme other than `https` accepted by `domain.outbound.ALLOWED_SCHEMES`. tubedepth's live
  instance serves plain HTTP by its own documented design (`docs/api.md`: "There is no TLS
  here"). This is not specific to `collector.tubedepth.rest` — it would block a real collect
  through *any* add-on pointed at this exact deployment, for either of this add-on's declared
  endpoints, regardless of anything the add-on's own code does. Out of an M4 add-on's scope to
  repair (platform_core/domain is a different area; changing `ALLOWED_SCHEMES` or the
  transport's TLS-only assumption is a security-policy decision AGENTS.md reserves for the
  project owner, not a local implementation choice). Recommend an Open Question or a DP
  narrowing `p0-security.md`'s HTTPS-only rule for a named, loopback-only, `allow_loopback`
  deployment case — or accepting that this specific fixed adapter target (DP-031 D3) cannot be
  live-collected from until it is deployed behind TLS.
- **Platform finding 2 (blocks payload dereference specifically, under any transport):
  `domain.outbound.resolve` has no per-request path parameter.** Every approved endpoint's
  `path` is one fixed string, checked at profile-approval time (`OutboundProfile.path_of`);
  `params` only ever becomes a query string for `GET`, or a body for `POST` (DP-020 D2) — never
  a path segment. tubedepth's `GET /v1/artifacts/{digest}` needs the digest **in the path**,
  and a digest is only known at run time, from the previous page — it cannot be one of the
  paths an operator pre-approves the way `hosts`/`endpoints` are for every other endpoint this
  platform has hosted so far (confirmed by reading `domain/outbound.py`'s `resolve`/`path_of`
  in full, `DP-020-request-method-and-body.md`'s own D1/D2 framing of path as fixed and
  operator-approved versus params/body as the add-on's "question", and by grep across
  `domain/`, `addon_host/`, and every test file in `apps/tests/` for any path-templating
  mechanism — none exists). This is a second, independent gap from finding 1: it would still
  block dereference-by-content-address even against a hypothetical future HTTPS-enabled
  tubedepth deployment, and it would block *any* future add-on against an "item by ID in the
  path" REST API, not just this one. `collector.tubedepth.rest`'s `artifact_payload` endpoint
  and its `context.fetch("artifact_payload", {"digest": digest})` call are written to the
  contract's intended shape (a fixed endpoint name, the digest as "the question," matching how
  `params` already works for every other endpoint) on the expectation that a future platform
  capability makes the request correct; until one exists, this exact call is refused or
  misrouted by `domain.outbound.resolve`, independent of finding 1. This is the reason
  `tests/test_addon_collector_tubedepth.py`'s dereference-branch tests call `handler.run`
  directly against a hand-built `CollectContext` rather than through `domain.outbound` — the
  only way to test this add-on's own logic without depending on a platform capability that has
  not been decided. Recommend an Open Question: does the outbound contract gain a
  per-request path-parameter mechanism (bounded and validated the way `params`/`body` already
  are), or is a content-addressed/ID-in-path REST source out of scope for the adapter shape
  DP-008 D4 fixed?
- **Two pre-existing, out-of-scope test failures, confirmed unrelated to this task's diff.**
  `tests/test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag` (both cases):
  `REPO_ROOT = Path(__file__).resolve().parents[2]` resolves to the worktree's own root when
  run from inside `.worktrees/<name>/apps/`, and `SKIPPED_PARTS` includes `.worktrees` — but
  the worktree's own absolute path necessarily contains `.worktrees` as one of its own path
  segments, so the scan's `not any(part in SKIPPED_PARTS for part in path.parts)` is `False`
  for every file it looks at and both tests fail against an empty scan result. Nothing in this
  task's diff touches `domain/outbound.py` or this test file. A sibling M4 lane
  (`m4-importer-obf`, per its own batch report) independently reproduced the identical failure
  and recorded the same root cause; this task's own run — `818 passed, 2 failed`, both cases
  named above, stable across two full runs — confirms it a third time. Left unfixed: a
  different area (M2's outbound guard) owns the file, and repairing it was not part of this
  task's packet.
- **`apps/scripts/check-addons.sh` was not added here.** `m4-importer-obf`'s own report records
  adding one, independently, in that worktree, for the identical mypy-collision reason this
  task hit. Adding a second, near-identical copy here risks a needless conflict at M7's merge;
  this task instead verified its own add-on with the direct `mypy --strict
  addons/collector.tubedepth.rest/handler.py` invocation the (root, P0-era) `check-addons.sh`
  already models. M7 should reconcile whichever lane's `apps/scripts/check-addons.sh` lands
  first, or write one fresh against every M4 lane's merged `apps/addons/` tree.
- **The root `.venv` did not exist in this worktree until this task ran `uv sync` at the
  worktree root** (`git worktree`s do not share `.venv`, and `apps/.venv` is separate from
  it). Needed to run the root guard (`tests/environment`) at all; recorded since it is not
  obvious from the task brief that a second `uv sync` (outside `apps/`) is required.
