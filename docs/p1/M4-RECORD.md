# M4-RECORD — five add-ons, the platform gaps they found, and what M7 reconciled

M4's five per-source lanes (NAVER blog, NAVER DataLab, trend-radar, tubedepth, the
importer/obfuscation-normalizer pair) each ran in its own worktree and kept its own
batch report, originally under `.superpowers/sdd/2026-08-21-m2-m7-batch/` (gitignored,
machine-local) and now also committed at `docs/p1/lane-reports/` (B8,
`docs/agent-workflow/reviews/REVIEW-M2-M7.md` — copied, not moved, after a secret-shape
scan found nothing to redact); those five reports are the primary evidence and are not
reproduced here in full. This file consolidates them
into one per-addon summary (§Per-addon summaries), plus the **platform-gaps section**
M4x's task packet asked to be registered here (§Gap 1, §Gap 2 — the two architecture
gaps `collector.tubedepth.rest`'s own README and its finder's report named as blocking
live collection, and the platform mechanisms that close them), plus two M7-sweep
reconciliation notes the individual lane reports each flagged as needing a merged-tree
recheck (§Shared-infrastructure reconciliation, §Duplicated-helpers scan).

- M4x worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4x`, branch
  `p1/m4-platform-gaps`, cut from `dev` after `p1/m4-tubedepth` merged (`a87ff08`).
- Controlling evidence: `docs/p1/lane-reports/m4-tubedepth-report.md`
  ("Live verification, and two platform-level findings"; committed copy of
  `.superpowers/sdd/2026-08-21-m2-m7-batch/m4-tubedepth-report.md`, B8); `apps/addons/collector.tubedepth.rest/README.md`
  (same section, now updated); [DP-031](../decisions/DP-031-p1-collector-topology.md) D3
  and its 2026-08-21 addendum (why these two capabilities are owed to the two adapter
  targets DP-031 fixed).
- Full evidence and commit hashes: `docs/p1/lane-reports/m4x-platform-gaps-report.md`
  (committed copy of `.superpowers/sdd/2026-08-21-m2-m7-batch/m4x-platform-gaps-report.md`, B8).

## Per-addon summaries

Quoted by extraction from each lane's own report — full detail, concerns, and
deviations live in the source report named per section, not repeated here.

### `collector.naver.blog` + `normalizer.naver.blog`

- Worktree/branch: `.worktrees/m4-naver-blog`, `p1/m4-naver-blog`. Commit `e87a00e`.
- Tests: `[정정, 2026-08-21, m7-fixwave, B7]` "41 collector + 27 normalizer (68
  addon-specific), full apps suite 860 passed" was wrong, and self-contradictory:
  68 addon-specific over an 800-baseline lane suite implies 868, not 860. `[측정]`
  at `e87a00e`: `test_collector_naver_blog.py` collects 37, `test_normalizer_naver_blog.py`
  collects 25 — **62 addon-specific**, lane suite 862 (800+62). See B7,
  `docs/agent-workflow/reviews/REVIEW-M2-M7.md`. `[측정]` Re-derived again at this fix
  wave's own post-edit tree (B1 added two fixture tests to
  `test_normalizer_naver_blog.py`): 37 collector / 27 normalizer, **64 addon-specific**.
  Root guard 87 passed.
- **LIVE smoke: SUCCEEDED.** One real NAVER API Hub call through the full host-worker
  path (`JobRunner`+`addon_host`+`SocketTransport`), query `수분크림`/`sort=date`/
  `display=10` (same parameters as P0's own `test_naver_real_data.py`). Collect job
  `SUCCEEDED`, 1 raw envelope, **10 raw items**; normalize job `SUCCEEDED`, 10
  normalized results, 0 carrying `normalize_error`. `[등록, 2026-08-21, m7-fixwave,
  M-R6]` This `[측정]` carries no capture time, API version, sample hash, or usage
  basis — AGENTS.md §Evidence requires all four and this bullet (unlike the tubedepth
  live-verification block below, which does this correctly) does not name them. This
  batch's own commit date (2026-08-21, this file's header) is the only recoverable
  capture-time signal; the API version and usage basis were never captured and cannot
  be reconstructed after the fact. Registered as a gap, not fabricated.
- Deviation: DP-030 D2's per-record fallback distinguishes two failure shapes (payload
  not JSON/not an object → every derived field null; payload parses but lacks a usable
  `link` → keep every derivable field, null only `external_id`/`url`) — a local schema
  choice, not a contract deviation.

### `collector.naver.datalab` + `normalizer.naver.trend`

- Worktree/branch: `.worktrees/m4-naver-datalab`, `p1/m4-naver-datalab`. Commit
  `dfdd0e9`.
- Implementer choice: **one add-on, not two or three** — merges P0's
  `collector.naver.searchtrend` and `collector.naver.shoppinginsight` (which had
  already itself merged two of the three DataLab endpoints) into one add-on with three
  `mode`s (`search_trend`/`shopping_categories`/`shopping_keywords`), table-driven in
  `_MODES`. This is the reason §Duplicated-helpers scan below stays `SKIPPED` even on
  the fully merged tree.
- Tests: 74 addon-specific (`[정정, 2026-08-21, m7-fixwave, M-R1]` "39 collector, 26
  normalizer, 9 host-loading/conformance" was wrong component-by-component even
  though the 74 total was right: `[측정]` at the M4-naver-datalab lane's own commit
  (`dfdd0e9`), `test_collector_naver_datalab.py` collects 35, `test_normalizer_naver_trend.py`
  collects 33, and this lane's own host-loading/conformance file — its report names
  it explicitly, `apps/tests/test_naver_datalab_addon_layer.py` — collects 6 (35+33+6=74).
  The original "9" was `test_addon_conformance_m4.py`(5)+`test_addon_host_loading_m4.py`(4),
  files the *importer-obf* lane wrote, not this one — a cross-lane mixup, not a count
  error. `[측정]` Re-derived again at this fix wave's own post-edit tree (B1 added two
  fixture tests to `test_normalizer_naver_trend.py`): 35 collector / 35 normalizer / 6
  host-loading-conformance, 76 total. See M-R1, `docs/agent-workflow/reviews/REVIEW-M2-M7.md`.
  Full `apps` suite **872 passed, 2 failed** (same pre-existing pair; a historical
  count as of `dfdd0e9`, not re-derived here — the m7-fixwave report carries the
  current apps-suite total). Root guard 87
  passed, including the add-on layer-direction check —
  `tests/environment/test_p1_isolation.py`, not `test_addon_layer_direction.py`
  (M-C2, same review; that file scans only `experiments/integrated-p0/`).
- **LIVE smoke: SUCCEEDED across 2 endpoints.** Credential reuse confirmed
  `[확인 사실]` the NCP APIGW key pair is account-level (the already-provisioned
  `naver.blog` credential also authorized DataLab). Pass 1 — `search_trend` mode →
  `/search-trend/v1/search`: collect `SUCCEEDED`, 1 raw item; normalize `SUCCEEDED`, 1
  result, 0 errors. Pass 2 — `shopping_categories` mode → `/shopping/v1/categories`:
  collect `SUCCEEDED`, 1 raw item; normalize `SUCCEEDED`, 1 result, 0 errors.
  `shopping_keywords` was not separately live-tested (fixture/conformance coverage
  only).
- A bug the conformance run itself found and fixed: `_Mode` switched from a frozen
  `@dataclass` to `typing.NamedTuple` after `addon_kit.harness._load_entry` (which does
  not register a loaded module in `sys.modules` the way the real host does) raised
  `AttributeError` under `from __future__ import annotations`'s `KW_ONLY` resolution.

### `collector.trendradar.rest`

- Worktree/branch: `.worktrees/m4-trendradar`, `p1/m4-trendradar`. Commits `9273ded`,
  `efcfafc` (adds `apps/scripts/check-addons.sh`).
- Tests: 15 addon-specific (host-loading, `_Budget`, hour-bucket pagination, filters-echo
  refusal, full-scan pagination, 5 config-validation cases, conformance incl. cursor
  resume). Full `apps` suite **813 passed, 2 failed** (same pre-existing pair). Root
  guard 87 passed.
- **LIVE smoke: BLOCKED at the transport layer, not this add-on's logic — the same
  finding M4x (§Gap 1 below) later closed.** trend-radar's live instance
  (`127.0.0.1:8000`) speaks plain HTTP only; `domain.transport.SocketTransport` was
  HTTPS-only at the time this lane ran. `[측정]` collect job attempt outcome
  `RETRYABLE_FAILURE`/`PLATFORM_TRANSIENT`, `cause: SSLError`, before any HTTP request
  was framed. Raw item count: 0. **This lane's own finding is what M4x named and
  closed** (Gap 1's mechanism was written after and because of this measurement); no
  add-on code changed as a result — trend-radar is expected to reach the live target
  through the now-fixed transport, but that live re-run through trend-radar
  specifically was not re-taken after M4x closed the gap (tubedepth's own re-run,
  §Gap 1 Evidence, is the closure's live confirmation; see Commit 2 of this sweep's
  demo for whether trend-radar itself was exercised).
- No normalizer in this batch (RC-005 deferred, as instructed); Raw rows are
  browseable/exportable without one.
- `captured_at` filtering 500s on the live instance for every ISO 8601 encoding tried
  (read-only dependency, not investigated further); the collector avoids sending it as
  a request parameter and instead relies on `source`(+`board`) filtering plus the
  API's own `captured_at DESC` ordering and a stored per-table-per-source cursor.

### `collector.tubedepth.rest`

- Worktree/branch: `.worktrees/m4-tubedepth`, `p1/m4-tubedepth`. Commit `5ca9148`.
- `[가설]→[확인 사실]` Live instance measured running `1.0.3`, not the task's stated
  `v1.0.0` baseline; DP-031 D3's own "adapter follows a new tag that appears during the
  work" rule applied on measured evidence — the one behavior change that matters
  (1.0.3 requires an RFC 3339-offset `since`/`until`) needed no add-on change.
  `[정정, 2026-08-21, m7-fixwave, M-R5]` Not because "every timestamp this add-on
  constructs is already `Z`-suffixed" — `[측정]` `addons/collector.tubedepth.rest/handler.py`
  imports neither `datetime` nor `time` and constructs no timestamp at all; it
  round-trips the provider's own `since`/`until`/`fetched_at` values verbatim. The
  actual reason no change was needed: nothing in this add-on formats a timestamp, so
  there was no format for the offset requirement to break.
- Tests: full addon-specific suite + conformance (`CONFORMANT`: manifest, contract
  range, entry resolvability, kind-capability, cursor-resume) + host-loading, all part
  of the 818-passed full-suite run at the time (`[정정, 2026-08-21, m7-fixwave, M-R4]`
  `COSMA_DB_NAME=cosmai_test_5` — `apps/tests/conftest.py`'s `TEST_DATABASE` reads
  `COSMA_TEST_DB`, not `COSMA_DB_NAME`; the lane report carried both spellings and this
  record kept the inert one), same pre-existing 2-failure pair. Root guard 87 passed.
- Key-minting: succeeded live (not blocked) — `tubedepth key create` run against the
  live deployment's real database over its published port; minted key written directly
  to `~/.config/cosmai/env`, verified with two direct `curl` calls, never printed.
- **LIVE smoke, at this lane's own commit: `BLOCKED-live` at the transport layer.**
  `[측정]` Job `FAILED`, `error_class = PLATFORM_TRANSIENT`, `"no checked address for
  '127.0.0.1' accepted a connection"` — this lane is the one that **named** the two
  platform gaps M4x (§Gap 1, §Gap 2 below) closed: `SocketTransport` was HTTPS-only,
  and `domain.outbound.resolve` had no per-request path parameter for
  `GET /v1/artifacts/{digest}`.
- **Post-M4x re-run: LIVE SUCCESS.** Per §Gap 1/§Gap 2 Evidence below, one bounded
  `collect()` through the real host worker against the live instance (now `1.1.0`):
  5 `artifacts_list` pages, **224** `artifact_payload` dereferences (each a real
  plain-HTTP loopback request with a validated-and-substituted `{digest}`), **224 raw
  items**, watermark advanced, 224-item snapshot sealed.
- `apps/scripts/check-addons.sh` was deliberately **not** added a second time here
  (this lane verified with a direct `mypy --strict addons/.../handler.py` invocation
  instead) — reconciled below, §Shared-infrastructure reconciliation.

### `importer.local.jsonl` + `normalizer.obf.product`

- Worktree/branch: `.worktrees/m4-importer-obf`, `p1/m4-importer-obf`. Commit
  `1748019`.
- **Offline by design — no live smoke section, and none was expected.** This is the
  one M4 lane with no outbound network surface at all: the importer reads a local
  JSONL fixture file (an `input` profile), and the normalizer transforms already-
  imported rows. Verification is the full addon-specific + conformance + end-to-end
  test suite (`test_importer_local_jsonl.py`, `test_normalizer_obf_product.py`,
  `test_addon_conformance_m4.py`, `test_addon_host_loading_m4.py`,
  `test_importer_obf_end_to_end.py`), not a network measurement.
- Tests: full `apps` suite **880 passed, 6 skipped, 2 failed** (same pre-existing
  pair — this is also the lane that first identified and named that failure's root
  cause, see Commit 1(a) of this sweep). Root guard 87 passed.
- This lane wrote `test_addon_duplicated_helpers.py` (subject: `_day_after`) and
  `apps/scripts/check-addons.sh` / the `pyproject.toml` `addons/` mypy exclude for the
  first time — both reconciled below.
- F3 from `P1-INHERITED-DEFECTS.md` §3 ("no row updated in place") recorded as left,
  not repaired: `record_results` has no UPDATE path at all, so the coexistence claim is
  unfalsifiable through `DomainStore` without a store-level UPDATE method nothing else
  in this codebase needs.
- **`[등록, 2026-08-21, m7-fixwave, M-R7]`** `normalizer.obf.product`'s per-field
  fallback (DP-030 D2) needs a genuinely unanticipated field-extraction failure to
  test honestly, and no real payload shape this add-on's own tests produce fails —
  `apps/tests/test_normalizer_obf_product.py`'s `TestPerRecordFallback` discloses this
  directly and thoroughly in its own docstrings: a sentinel value
  (`_TRIGGER_BRANDS`) and a substitute `_brands` helper (`_broken_brands`) that fails
  only for that sentinel, used in place of an honestly-unreachable failure, with the
  reasoning written out at the point of use rather than assumed. This record did not
  mention that disclosure anywhere before this note.

## Shared-infrastructure reconciliation

Every M4 lane independently hit the same collision — `apps/addons/` gaining a second
add-on makes two `handler.py` files collide in mypy's single module namespace
("Duplicate module named handler") — and independently converged on the same two
fixes: `apps/pyproject.toml`'s `[tool.mypy] exclude = ["^addons/"]` and
`apps/scripts/check-addons.sh` (mirroring the repository root's own per-addon checker;
`m4-tubedepth` alone verified with a direct `mypy --strict addons/<id>/handler.py`
invocation instead of re-adding the script, and flagged the reconciliation as owed to
whichever lane's merge landed first or to a fresh write against the merged tree).

`[측정]` At merge, both converged rather than conflicted: `apps/pyproject.toml` carries
exactly one `exclude = ["^addons/"]` entry (not one per lane), and exactly one
`apps/scripts/check-addons.sh` exists, functionally identical to every lane's own
description of what it wrote (iterate `addons/*/`, run `ruff check` + `mypy --strict
--no-incremental` per add-on directory, one add-on at a time). `cd apps &&
./scripts/check-addons.sh` against the fully merged 8-addon tree — **all eight `ok`**:
`collector.naver.blog`, `collector.naver.datalab`, `collector.trendradar.rest`,
`collector.tubedepth.rest`, `importer.local.jsonl`, `normalizer.naver.blog`,
`normalizer.naver.trend`, `normalizer.obf.product`.

## Duplicated-helpers scan

`apps/tests/test_addon_duplicated_helpers.py` scans the installed `apps/addons/` tree
for every add-on declaring a module-level `_day_after` helper and, when two or more
exist, runs the same five-case arithmetic suite against each of them (a regression
guard against divergent copies of duplicated logic). `m4-importer-obf` wrote it against
an empty worktree (fewer than two implementations present) with the guard's own class
docstring predicting it would "re-activate automatically once M7 merges every M4
lane's add-ons into one `apps/addons/`."

`[측정]` 2026-08-21, run against the fully merged 8-addon tree
(`COSMA_DB_PORT=5434 COSMA_TEST_DB=cosmai_test`): **5 passed, 1 skipped** — the guard
class (`TestEveryCopyOfTheDayAfterArithmetic`) still parametrizes to exactly one
add-on (`collector.naver.datalab`) and `test_the_arithmetic_was_found_in_more_than_one_add_on`
remains `SKIPPED`. `[추론]` This is not the unmerged-worktree gap the prediction
above expected — the merge itself is complete (verified: `grep -rn _day_after
apps/addons/` finds exactly one definition, in `collector.naver.datalab/handler.py`).
The predicted second copy never materializes because it was designed out: P0 held
`_day_after` in *two* separate add-ons (`collector.naver.searchtrend` and
`collector.naver.shoppinginsight`), but `m4-naver-datalab`'s own implementer choice
(§Per-addon summaries above) merged both of those into the single `collector.naver.datalab`
add-on before this guard ever ran against a merged tree — so the duplication this
guard was written to catch was eliminated by a design decision one lane over, not
reproduced by the merge. The guard remains correct and ready (it will activate the
moment a second add-on defines `_day_after`); recorded here as a verdict rather than
left as an unresolved prediction, per this sweep's task packet.

## Gap 1 — plain HTTP for loopback

`domain.transport.SocketTransport` was HTTPS-only (`http.client.HTTPSConnection`, a
real TLS handshake, no other scheme accepted). tubedepth's live instance serves plain
HTTP by design (its own `docs/api.md`: "There is no TLS here"), so no live collect
through the real host worker could reach it.

**The mechanism.** `domain.outbound.OutboundProfile` gains a `scheme` field
(`"https"` unless a profile states `"http"`). `domain.outbound.resolve` grants
`"http"` only when the profile's `allow_loopback` is also set — the same flag that
already admits a loopback address into `check_resolved_addresses` at all, rather than
a second flag that could disagree with it. That is the validation half, and it is
testable with no socket, the way every other rule in `domain/outbound.py` is.

`domain.transport.SocketTransport` holds the transport half: before it will speak
plain HTTP, it checks that every address `resolve_addresses` actually resolved is
itself loopback (`_refuse_http_off_loopback`), independent of what the profile
claims. A hostname that resolves to loopback once and something else the next time is
exactly the rebinding hole this module's own docstring already refuses to create for
TLS; this is the same discipline with no certificate to fall back on. `SocketTransport`
picks `http.client.HTTPConnection` or `HTTPSConnection` per request based on
`PreparedRequest.scheme`; every other property (one hop, no redirect followed, one
deadline for the whole request, credential attachment, header stripping) is unchanged
for the plain-HTTP path.

**What it does not cover — recorded as a deviation, not silently absorbed.**

- `scheme` is a profile-wide setting, not per-endpoint. A source needing HTTP for one
  endpoint and HTTPS for another is not representable; every fixed adapter target this
  platform has hosted so far speaks one scheme for every route it serves, so this was
  not a reduction against a named uncertainty.
- **`[정정, 2026-08-21, B4 fix wave]`** The paragraph originally here claimed
  depth-in-defense at 2 — refusal "at `resolve`" and again at the transport. `[측정]`
  that is false of `resolve`: `resolve`'s check (`domain/outbound.py`) is `scheme ==
  "http" and not profile.allow_loopback` — a claim about the *profile's configuration*,
  not about any address. `resolve` performs no DNS lookup and no address check at all,
  so `OutboundProfile.from_row({"hosts": ["evil.example.com"], "scheme": "http",
  "allow_loopback": True, ...})` passed to `resolve` produces a plain `PreparedRequest`
  for `http://evil.example.com`, not a `Refusal`. Depth is 1, not 2, and it lives
  entirely at the transport. `domain/transport.py`'s own docstring on
  `_refuse_http_off_loopback` (quoted verbatim) says as much: *"`domain.outbound.resolve`
  already refused a plain-HTTP request unless the profile set `allow_loopback` — but
  that is a claim about the profile, made before any name was resolved. This is the
  claim checked against what `getaddrinfo` actually returned, which is the only place
  either half of the belt-and-suspenders rule can be checked against reality... a
  non-loopback address is never blocked by [`check_resolved_addresses`] at all... so
  without this, a source with `allow_loopback = true` and `scheme = "http"` in its
  profile could ask for a request to a hostname resolving anywhere public, and there
  would be no `SocketTransport`-level check left to refuse it."* Not a live egress hole
  — `_refuse_http_off_loopback` does hold, order-independent, and is itself real and
  well tested (see `test_outbound_transport.py`) — but the claim that a public host with
  `scheme: "http"` is "refused at `resolve`" is not true of the code, and this record
  said it was. See B4, `docs/agent-workflow/reviews/REVIEW-M2-M7.md`. No code change;
  this paragraph is corrected, not the mechanism.
- A redirect from a plain-HTTP endpoint is not specially handled: `check_redirect`
  still only allows `ALLOWED_SCHEMES = {"https"}`, so any redirect off a loopback-HTTP
  endpoint is refused outright rather than re-validated as a same-scheme hop. Untested
  because tubedepth's target routes do not redirect; recorded as a known gap for a
  future loopback target that does.
- Nothing about `p0-security.md`'s HTTPS-only policy changed for a non-loopback
  destination. This is a narrow, named exception for the one case DP-031 D3 already
  created a private-network egress precondition for — not a general HTTP allowance.

## Gap 2 — path parameters

`domain.outbound.resolve` had one fixed path per `endpoint_ref`; `params` only ever
became a query string (`GET`) or a body (`POST`, DP-020). tubedepth's dereference
route needs `digest` **in the path** (`GET /v1/artifacts/{digest}`), known only at run
time from the previous page, so it could not be one of the paths an operator
pre-approves the way every other endpoint's path is.

**The mechanism.** An approved path may carry a `{name}` placeholder. The profile
declares one validation regex per placeholder in the endpoint's `path_params` — read
and checked at profile construction (`_read_endpoints`/`_read_path_params`): every
placeholder needs exactly one declared regex and every declared regex needs a matching
placeholder, or the row is refused with a `ValueError` when it is written, not on the
add-on's first `fetch`. The add-on supplies the value through `fetch`'s **existing**
`params` channel — no signature change to `addon_api.context.Fetch` was needed, since
`params: Mapping[str, str] | None` already carried exactly this shape; `collector.
tubedepth.rest`'s own `context.fetch(_ARTIFACT_PAYLOAD, {"digest": digest})` call
(written before this gap closed, to the contract's *intended* shape) needed no change
at all. `resolve` validates the value against the declared pattern, substitutes it into
the path, and only then runs the **same** segment-by-segment `comparable_segments`
containment every approved path has always been checked with — now against the path a
template actually resolved to, which is what makes a traversal attempt fail two
independent controls rather than one: the declared regex refuses it as a value, and
(separately, provable with a deliberately permissive regex) the containment check would
refuse it as a path even if the regex had not.

**What it does not cover — recorded as a deviation, not silently absorbed.**

- Validation is exactly as strong as the profile's own declared regex, and no
  stronger. A profile author who declares `path_params: {"digest": "^.*$"}` gets no
  help from the regex layer; the containment check (dot-segment / encoded-separator
  refusal) is what still stands between that value and a request, and it is a **weaker**
  guarantee than a tight regex — it catches `..` and `%2e`/`%2f`, not an arbitrary
  extra path segment that contains neither (a value like `foo/bar` with no dots would
  pass containment and change the request's shape). tubedepth's own `digest`
  declares `^[0-9a-f]{64}$`, which admits no such value; a future template endpoint's
  safety depends entirely on its own operator writing an equally tight pattern.
- A template placeholder consumes its name out of the `params` a query string would
  otherwise use; it does not add a new parameter-count or type-shape check beyond the
  regex. `allowed_parameters` (when a profile sets one) is checked against what remains
  after template names are consumed, so a profile that lists `allowed_parameters`
  without also listing its own template names is unaffected — the template name is
  never subject to that check at all, by design (it is not a query parameter).
- The redirect range a templated endpoint grants uses the **literal** `{name}` text as
  the approved segment (`OutboundProfile.approved_paths()` returns the unsubstituted
  template). A real redirect's concrete segment can never textually equal `{digest}`,
  so a redirect from a templated endpoint is refused by `check_redirect` unconditionally
  — untested against tubedepth (its routes do not redirect) and worth a follow-up if a
  future templated endpoint's target does.

## Evidence

- `apps/tests/test_outbound_policy.py`: `TestScheme` (scheme validation, no socket),
  `TestPathTemplates` (substitution, regex refusal, the traversal test split across
  the validation and containment layers per the P0 one-control-per-test style, missing
  parameter, template-free endpoints unaffected), `TestPathTemplateDeclaration`
  (read-time refusal of a malformed `path_params` declaration).
- `apps/tests/test_outbound_transport.py`: `TestPlainHttpForLoopback` (a real plain-HTTP
  stub server reached over loopback; credential stripping still applies; a hand-built
  request to a non-loopback address refused by the transport even with `allow_loopback`
  set on the profile; the existing HTTPS path unaffected).
- `[측정]` Full `apps` suite, at this task's own diff: 1003 passed, 2 pre-existing
  failures unrelated to this diff (`test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag`,
  both cases — `REPO_ROOT`'s `.worktrees` path-segment collision when run from inside a
  worktree, first recorded by `m4-tubedepth-report.md` and reproduced identically here,
  confirmed by re-running the same two cases before this task's diff). `mypy --strict`
  and `ruff check` clean on the whole `apps/` tree. Root guard: 87 passed.
  **`[정정, 2026-08-21, m7-fixwave, M-R2]`** These 2 failures are pre-existing only up
  to the M7 sweep commit — its own worktree-scan narrowing (the `.worktrees` exclusion
  matching `path.relative_to(REPO_ROOT).parts`, cited under "What HELD" in
  `docs/agent-workflow/reviews/REVIEW-M2-M7.md`) fixes both. `[측정]` re-derived on
  this fix wave's own tree: `TestLoopbackIsOnlyReachableByFlag` — **3 passed, 0
  failed**. No `docs/p1/*.md` document previously recorded that these 2 failures were
  closed (`grep -rn 1082 docs/` found nothing before this correction), leaving a reader
  of this section believing the tree was still red.
- `[측정]` Live smoke, 2026-08-21: one bounded `collect()` through the real host worker
  against the live tubedepth instance (`127.0.0.1:8080`, now `1.1.0` — moved again since
  `m4-tubedepth-report.md`'s `1.0.3` finding, artifacts-feed surface unchanged).
  **SUCCEEDED**: 5 `artifacts_list` pages, 224 `artifact_payload` dereferences (every
  one a real plain-HTTP loopback request with a validated-and-substituted `{digest}`),
  224 Raw items, watermark advanced, and `domain.store.seal_snapshot_from_raw` sealed a
  224-item snapshot. Full detail in the task report named above.

## Required changes recorded elsewhere

- `apps/addons/collector.tubedepth.rest/README.md` — the "Live verification, and two
  platform-level findings" section is replaced with "Live verification" (unchanged
  facts) plus "M4x — the two platform gaps this add-on named, closed" (the mechanism
  and the live-smoke result), and a new "The operator-approved outbound profile"
  section giving the exact profile shape that now reaches the target.
