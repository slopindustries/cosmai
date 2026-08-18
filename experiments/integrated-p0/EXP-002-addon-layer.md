# EXP-002 — Add-on layer: contract, host, and conformance

## Identity and status

- Experiment ID: `EXP-002`
- Type: `INTEGRATED_P0`
- Status: `RUNNING`
- Related Open Question or Decision Packet: [DP-008](../../docs/decisions/DP-008-addon-architecture.md); informs [OQ-003](../../docs/open-questions/OQ-003-normalization-protocol.md), [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md) H3, [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md)
- Owner: Project team
- Created at: 2026-08-18T09:00:00+09:00
- Last executed at: 2026-08-18T12:10:00+09:00

## Question

Can a collector and a normalizer be added to Cosmai without adding platform code —
and can that boundary be enforced by tests rather than by review?

This is work package B0 in [the execution plan](../../docs/p0-execution-plan.md). It runs
in parallel with B1 source exploration because it contains no source or decision semantics.

## Hypothesis

`[가설]` **H1.** The add-on contract can be fixed without a selected source, so the add-on
layer is blocked by neither OQ-001 nor OQ-002.

`[가설]` **H2.** Every outbound obligation in the [P0 Security Baseline](../../docs/conventions/p0-security.md)
can stay on the platform while a collector add-on still does useful work.

`[가설]` **H3.** A dependency-direction test is sufficient to keep the coupling loose in
practice — an add-on can be written against `addon_api` alone.

`[가설]` **H4.** A contract written in serializable shapes keeps subprocess isolation
reachable as a change to `addon_host` rather than a rewrite of the contract.

## Falsification condition

- **H1** is refuted if defining a context, capability, or manifest field requires knowing
  which provider was selected, or requires the decision consumer OQ-002 has not fixed.
- **H2** is refuted if a collector cannot do its work without composing its own URL, holding
  a credential, or opening its own socket. B0 can only test this against a synthetic source;
  the real test is B3, and a B0 pass does not discharge it.
- **H3** is refuted if a conforming add-on cannot be written without importing `platform_core`,
  or if the guard cannot separate a legitimate import from a violating one.
- **H4** is refuted if a capability or context member cannot be expressed without passing a
  live object that has no serialized equivalent.

## Exit condition

Stops at **6 hours of execution**, or when B0.1–B0.5 are complete, whichever comes first.
Faster is preferred. A timebox reduces scope; it does not turn missing evidence into a pass.

If the box expires mid-package, the incomplete package is recorded as unfinished with what
was and was not built, and the P1 Entry Gate inherits it as an explicit item rather than an
implied one.

## Scope

### Included

- `addon_api` contract, `addon_host` discovery/loading/version gate, `domain` source-registry
  and cursor tables, capability implementations including the platform outbound guard.
- Conformance suite, the `addon_kit` generator and its template at `addon_kit/template/`
  (outside the scanned `addons/` tree, so a template is never discovered), and a smallest
  conforming add-on.
- Operator surfaces for installed add-ons, source configuration, credential submission, and
  version state.
- `SEC-002`, `SEC-003`, and `SEC-004` against a synthetic registered source.

### Excluded

- Source selection, rights review, and any outbound request to a real provider — those are B1.
- Schema 0.x and `rule-baseline@0.1`'s actual rules — blocked by OQ-002 and belonging to B3.
- Subprocess isolation. DP-008 rejected it on cost and keeps it reachable; building it here
  would be the abstraction AGENTS.md warns about.
- Any claim that a real source can be collected. B0 has no real source.

## Inputs and provenance

| Input | Source or provider | Captured at | License or usage basis | Version or hash | Storage note |
| --- | --- | --- | --- | --- | --- |
| None | — | — | — | — | B0 introduces no external input. Every fixture is synthetic and written in this repository. |

`[확인 사실]` B0 acquires nothing. The first external input arrives in B1, and the agent
sandbox must be narrowed (`SEC-006`) before it does.

## Environment

- Code revision: `d714b3b` at start
- Runtime and dependency versions: Python 3.13.7, psycopg 3.3.4, pytest 8.x, mypy strict, ruff
- External service or database versions: PostgreSQL 18.4, repository-local cluster over a Unix socket (DP-006 D2)
- Relevant configuration with secrets removed: `config/env.example`; no credential is resolved in B0
- Reproduction command: `./scripts/with-database.sh .venv/bin/pytest -q`

`[측정]` The runtime moved from Python **3.13.15 to 3.13.7** at the start of B0. The
directory rename in DP-007 left `.venv` with shebangs pointing at the old absolute path, so
the environment could not run at all; recreating it selected a different patch release. Both
satisfy `requires-python = ">=3.13"`. Recorded because the P0-A gate's evidence was captured
on 3.13.15 and a future comparison should not read the difference as drift.

`[측정]` The same rename left stale `__pycache__` bytecode whose embedded `co_filename` still
named the old directory, so pytest reported test locations under a path that does not exist.
Cleared. No test outcome changed; only reported locations were wrong.

## Procedure

1. **B0.1** — `addon_api` (errors, boundary data, contexts, manifest); `addon_host`
   discovery, `importlib` loading by path, and the contract-version gate.
2. **B0.2** — `domain` source registry, `source_cursor`, Raw, and snapshot tables in
   `0002_domain.sql`.
3. **B0.3** — capability implementations, including the outbound guard that composes every
   request from a registered source profile.
4. **B0.4** — conformance suite, `addon_kit new` and its template at `addon_kit/template/`, and
   `addons/normalizer.conformance/`.
5. **B0.5** — operator surfaces.
6. Run `ruff`, `mypy --strict`, and the full suite after each package. Classify any failure as
   implementation, specification, assumption, evaluation, or goal before changing anything.

## Evidence collection

- Metrics and units: test counts and durations; guard pass/fail; type and lint cleanliness.
- Log or trace location: `var/log/platform.jsonl` when the platform runs.
- Output artifact location: `experiments/integrated-p0/evidence/<date>-<sha>/`, captured
  opt-in with `--capture-evidence=DIR` so a committed hash stays checkable.
- Integrity check or hash procedure: SHA-256 over each captured artifact, listed in the
  evidence directory's README, with `git diff <sha>..HEAD` empty over code paths.

## Observations

```text
[측정] 2026-08-18, B0.1 partial — addon_api complete, addon_host not started.
  Full suite: 570 passed, 2 skipped in 74 s (PostgreSQL 18.4, serial).
  Baseline before B0 was 520 passed, 2 skipped; no pre-existing test changed outcome.
  ruff clean; mypy --strict clean.
  New tests: 38 contract tests, 5 direction-guard tests, 5 serializability tests,
  2 added to the rescoped P0-A boundary guard.
```

```text
[측정] The P0-A boundary guard was rescoped from the whole experiment tree to
  platform_core/ and still passes, with a positive control asserting the scan root
  exists and contains both .py and .sql files. A guard over a missing directory
  would pass while reading nothing.
```

```text
[측정] A pre-existing test is intermittently flaky under parallel execution.
  test_job_002_shares_one_correlation_id_across_both_attempts failed once under
  `pytest -n 4` and passed on re-execution of the same command
  (570 passed, 133 s). Serial execution passed every time.

  Attribution was measured, not assumed: the working tree was stashed and the
  suite re-run under `-n 4` at revision d714b3b, where the same test failed the
  same way (1 failed, 519 passed). The flake predates B0 and is not caused by it.
```

```text
[측정] The P0-A evidence directory's own verifiable claim was already failing before
  B0 touched any code, and for two independent reasons.

  Its README said `git diff 07b0688..HEAD -- platform_core tests dashboard/src`
  "must be empty". Measured: it is not.

  (a) 07b0688 is two commits before 3b26f44, which added the directory, and is not
      the revision f83fe3c the directory is named for. Baseline and name never agreed.
  (b) The path list included experiments/integrated-p0/tests, which P0-B must add
      files to, so the claim could not survive P0-B by construction.
  (c) DP-007 changed two display strings under platform_core and dashboard/src,
      which broke the remaining form of the claim before B0 began.
```

```text
[추론] (c) is worth naming. DP-007 declined to rename the COSMA_ prefix on the
  stated grounds that the churn would "spend that claim on a cosmetic edit", and
  then spent it on two display strings for the same kind of reason. The packet's
  conclusion stands; its rationale was inconsistent with its own effect. Corrected
  in the evidence README rather than left for a later reader to find.
```

```text
[측정] One test failed on first execution: a version range with a trailing comma
  (">=1.0,") was expected to be refused and was accepted. Classified as an
  EVALUATION failure — the parser skips empty clauses deliberately, a trailing
  comma has one reading, and TOML and Python both accept one. The expectation was
  corrected and the tolerance is now asserted with its reason; ",," stays refused
  because it states no constraint at all.
```

```text
[측정] 2026-08-18, B0.1 + B0.2 + half of B0.4 complete.
  Full suite: 667 passed, 2 skipped in 55 s (PostgreSQL 18.4, serial).
  Baseline before B0 was 520 passed, 2 skipped. ruff and mypy --strict clean
  over 68 source files. platform_core gained one line and no dependency.

  New tests by area:
    addon_api contract            40
    addon_host                    43
    addon_kit + template          16
    domain (incl. atomicity)      34
    direction + serializability   10
    config (COSMA_ADDON_DIR)       2
```

```text
[측정] The atomicity the P0-A gate recorded as its first limitation now has direct
  evidence. A collection is four statements — envelope, items, cursor, fenced
  completion — inside one `connection.transaction()`, completion last.

  Interrupted after the writes and before completion: 0 raw_envelope rows,
  0 raw_item rows, no cursor, job still RUNNING with one open attempt.
  Lease taken by another worker before completion: the fence refuses, and Raw
  and cursor roll back with it.
  Both have positive controls: the same sequence with the lease still held
  commits, and 1 item plus a cursor are present.
```

```text
[측정] A correction found while writing those tests. A comment claimed the attempt
  row rolls back with the effect. It does not: `claim_next` commits before the
  collection transaction opens, so after an interruption the job is RUNNING with
  an open attempt and recovery is the platform's existing lease-expiry path.
  What one transaction buys is not an undone claim but an undone effect. The
  comment was wrong; the test now asserts the real state.
```

```text
[측정] A pre-existing P0-A test failed once the domain tables existed:
  test_job_001_writes_no_table_beyond_the_three_and_the_migration_ledger
  asserted the database holds exactly four tables.

  Classified as a SPECIFICATION failure. The encoded claim was a true statement of
  the P0-A boundary and DP-008 D5 supersedes it deliberately. Restated rather than
  deleted: under P0-A a domain side channel would have appeared as an unexpected
  table, because none existed; now that they exist the signal is an unexpected
  *row*, and a platform scenario must leave every domain table empty. Stronger
  evidence for the same claim.
```

```text
[측정] Repo-wide ruff broke when the add-on template landed: the template file was
  named handler.py but nearly every meaningful line is a substitution token, so it
  is not Python. Renamed to .tmpl. No lint exclusion was needed, which is the test
  that the diagnosis was right rather than the symptom being suppressed.
```

```text
[측정] The contract was tightened once. `[declares].endpoints` on an importer parsed
  and was then ignored, because ImportContext has no `fetch`. Now refused at load.
  `needs_credential` and `streams` stay legal for an importer and that is recorded
  as deliberate: the platform may need a credential to open a protected input, and
  an importer holds a cursor. CONTRACT_VERSION stayed at 1.0, with the reason
  recorded at the constant: the tightening is breaking under the project's own rule,
  and was made in place only because no add-on existed to break.
```

## Interpretation

```text
[추론] H1 is holding so far. addon_api names no provider, no schema, and no decision
  consumer, and it was written before any source exists. This is support, not proof:
  the contract has not yet met a real source, and B3 is where H1 could still fail by
  requiring a field that only a chosen provider could have supplied.
```

```text
[추론] H4 is testable now rather than at the moment someone tries to collect the
  promise. Every boundary type has an explicit JSON form and a test asserts the
  registry covers every boundary dataclass, so adding a type without one fails here.
  What remains untested is whether the capabilities' call/return shapes survive the
  same treatment, which is B0.3's to show.
```

```text
[추론] H2 and H3 remain untested. Both need a real add-on and, for H2, a real source.
  Nothing in B0.1 is evidence for either.
```

## Result

- Outcome: `INCONCLUSIVE` — the experiment is `RUNNING` and this section is not final.
- Falsification condition met: `NOT TESTED`
- Exit condition met: `NO`
- Known limitations:
  - No add-on has been loaded, so the contract has only been exercised by its own tests.
  - No source exists, so every security scenario B0 can run uses a synthetic registered source.
  - The runtime patch version differs from the P0-A gate's environment.

## Impact and next action

- Uncertainty reduced: what an add-on declares, what each kind may be granted, and how a
  version mismatch fails are now fixed and tested rather than described.
- New uncertainty discovered: whether `domain` can stay free of `addon_api` without the
  translation in `addon_host` becoming pure ceremony. The direction guard forbids the
  dependency today; B0.2 is where that judgement is tested.
- **Open finding F16 — an intermittent parallel-execution flake in P0-A code.**
  `[확인 사실]` The [P0-A Completion Gate](PLATFORM-CORE-GATE-2026-08-17.md) records the suite
  passing "sequentially and under `-n 4`", which is now known to be a claim about the runs that
  were observed rather than a stable property.
  `[추론]` The most likely mechanism is that a runner claims a job left behind by an earlier
  test sharing the same database, since `claim_next` takes the next available job rather than a
  named one. That is an inference from the shape of the assertion — a correlation-id set with
  more than one member — and has not been confirmed.
  Not fixed here. It is P0-A code, outside B0's scope, and it needs its own classification
  before anyone changes a test or a fixture. Routed to [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md),
  whose H2 is exactly about whether the claim model is sufficient, and it must be resolved
  before the P1 Entry Gate rather than carried silently.
- Proposed next experiment: none. B0 continues.
- Proposed contract change: none yet. `addon_api` is at `CONTRACT_VERSION = "1.0"`.
- Proposed Decision Packet update: none yet.

## Artifacts

- Experiment record: this file
- Code: `experiments/integrated-p0/addon_api/`, `tests/environment/test_addon_layer_direction.py`,
  `tests/environment/test_addon_contract_is_serializable.py`,
  `experiments/integrated-p0/tests/test_addon_api_contract.py`
- Fixture or retrieval procedure: synthetic only; the manifests under test are literals in the test file
- Logs, metrics, traces, or screenshots: none captured yet
- Output and hashes: none captured yet
- Data class and retention responsibility: `public`; no external or personal data is involved

## Completion checklist

- [x] The hypothesis is falsifiable.
- [x] The falsification and exit conditions were fixed before interpreting the result.
- [x] Inputs, rights, environment, versions, and hashes are recorded.
- [x] The procedure is replayable without relying on undocumented session context.
- [x] Observations and interpretations use the project evidence labels correctly.
- [x] Secrets, restricted inputs, and raw conversations are absent.
- [ ] The result includes limitations and a concrete next action. — pending completion
