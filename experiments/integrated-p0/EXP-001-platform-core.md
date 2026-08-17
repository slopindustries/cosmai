# EXP-001 — Source- and normalization-independent platform core

## Identity and status

- Experiment ID: `EXP-001`
- Type: `INTEGRATED_P0`
- Status: `RUNNING`
- Related Open Question or Decision Packet: OQ-005, OQ-006, OQ-007; [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md), [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md)
- Owner: Project team
- Created at: 2026-08-17T00:00:00+09:00
- Last executed at: in progress, 2026-08-17

The hypothesis, falsification condition, exit condition, and timebox below were fixed before the status became `RUNNING`. Any later revision is appended with its reason rather than overwriting the original boundary.

This is the P0-A integrated experiment required by [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md) and work package A1 of the [P0 Execution Plan](../../docs/p0-execution-plan.md). Its outcome feeds the P0-A Completion Gate.

## Question

Can a platform core that has no selected source, no acquisition model, and no normalization semantics produce execution, recovery, operator, and safety evidence that is interpretable on its own — that is, evidence P0-B can build on rather than evidence that only becomes meaningful once a domain exists?

## Hypothesis

Two claims from [Project State](../../docs/project-state.md) section 5 are in scope. They are not independent: H2 is the mechanism H1's execution claim depends on, so they share one experiment rather than being split.

`[가설]` **H1** — A source- and normalization-independent platform core can expose useful execution, recovery, operator, and safety evidence before P0-B introduces the domain pipeline.

`[가설]` **H2** — PostgreSQL job tables with at-least-once processing and idempotent platform effects are sufficient for P0 concurrency.

H2 restates OQ-006's H1 and H2 at the platform level. OQ-006's H3 (whether collector and normalizer jobs need separate state and retry policy) is **not** in scope; it cannot be tested without the domain.

## Falsification condition

**H1 is refuted if** any of the following is observed:

- a required platform behavior cannot be specified or tested without naming a source, an acquisition step, a Raw payload, a snapshot, or a normalized result;
- the platform surfaces built here cannot be exercised by a synthetic handler without that handler imitating a collector, importer, Raw payload, snapshot producer, or normalizer;
- an operator scenario in the `OPS` family cannot be completed without direct database inspection **and** the missing capability turns out to be domain-shaped rather than platform-shaped.

**H2 is refuted if** any of the following is observed:

- two workers hold conflicting active ownership of one job;
- an injected duplicate delivery produces a durable effect that the recorded idempotency boundary cannot detect or reconcile;
- a tested interruption leaves work permanently stranded, or reaches a state with no documented recovery or finalization path;
- retry exhaustion does not reach an observable terminal state.

A refutation of H2 does not automatically refute H1; it may instead mean the platform needs a different concurrency mechanism. The distinction is recorded in Interpretation, not assumed.

## Exit condition

The experiment stops at whichever comes first:

- every P0-A exit criterion in the [P0 Charter](../../docs/p0-charter.md) has a `PASS`, `FAIL`, or `NOT RUN` result with linked evidence; or
- the timebox below is exhausted.

**Timebox: 1 working day (8 hours), 2026-08-17.**

Timebox exhaustion reduces scope; it does not convert missing evidence into a pass. The pre-declared descope order is:

1. reduce the number of `OPS` scenarios to three;
2. fix the dashboard at three screens with no metrics visualisation;
3. defer the formal evidence run and record the gate as `CONDITIONAL GO`.

The following are never descoped, because the gate is meaningless without them: parallel-claim and duplicate-delivery evidence, the secret-store location and loopback guards, and the boundary guard test.

## Scope

### Included

- PostgreSQL runtime connection, migration mechanism, and source-neutral transaction foundations
- Handler-neutral job creation, claim, lease, attempt, retry scheduling, terminal state, interruption, and recovery
- API and worker process lifecycle, health, configuration validation, and safe shutdown
- A source-neutral operator surface for platform health, generic job state, correlated logs and metrics, failure inspection, and safe retry
- Structured logging, metrics, correlation identifiers, redaction, loopback binding, and the repository-external secret-store location guard at application startup
- Deterministic synthetic handlers and failure injectors for success, retryable failure, permanent failure, duplicate execution, interruption, and invalid configuration
- Replayable `JOB`, platform `OPS`, and platform `SEC` acceptance evidence

### Excluded

Every item below is deferred to P0-B and must be absent from this experiment's implementation **and** from its acceptance claims. This list is copied from the P0-A Completion Gate's deferred-domain inventory so that the inventory is maintained from the first commit rather than reconstructed at the gate.

- REST and dataset candidate exploration or selection
- Source rights decision, source fixture, or outbound request
- Source registration semantics or concrete host policy
- Collector or dataset-importer interface, test double, or implementation
- Raw response, Raw record, observation identity, or duplicate semantics
- Snapshot, manifest, or Raw-to-result lineage
- Normalized Schema 0.x, provider protocol, test double, or rules
- Acquisition- or normalization-specific dashboard behavior
- `ACQ`, `RAW`, `SNP`, or `NRM` pass claim

Additionally excluded: `credential_ref` resolution and authorization semantics (OQ-007 assigns these to P0-B); OQ-006 H3; production topology, scale targets, and polished UX.

## Inputs and provenance

| Input | Source or provider | Captured at | License or usage basis | Version or hash | Storage note |
| --- | --- | --- | --- | --- | --- |
| Synthetic job payloads | Generated in-test by `platform_core.handlers` | n/a | Project-authored, no third-party rights | Deterministic from test fixtures | Not persisted outside the disposable local cluster |
| Synthetic secret-store fixtures | Generated in-test under `tmp_path` | n/a | Project-authored | n/a | Never written inside the working tree |

This experiment consumes no external data, makes no outbound request, and uses no real credential. Data class is `public` throughout, which is why the evidence directory is committed.

## Environment

- Code revision: recorded at execution time in each evidence directory
- Runtime and dependency versions: Python 3.13 (pinned by `.python-version`), dependencies resolved by `uv.lock`; Node and PostgreSQL supplied either by the optional Nix shell or by the host
- External service or database versions: PostgreSQL as resolved locally; exact version recorded per evidence run
- Relevant configuration with secrets removed: repository-local cluster at `var/postgres` with `listen_addresses = ''`, Unix socket only, no role password ([DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D2). Operator surfaces bind to loopback by default.
- Reproduction command: `./scripts/with-database.sh uv run pytest`

## Procedure

Executed as six vertical slices. The order is deliberate: the Execution Plan's A2.1–A2.6 is a component list, and following it literally would build the least uncertain surfaces (API, dashboard) before the most uncertain one (concurrency).

1. **S0 — Foundation.** Record [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md); write [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md); draft the `JOB` and `SEC` acceptance scenarios; create the module layout, database launcher, and boundary guard.
2. **S1 — Execution skeleton.** Configuration validation, structured logging with the redaction boundary and correlation identifiers, database connection and migrations, and job create/claim/execute/terminal with a synthetic success handler. The log schema and the redaction boundary are built together here; adding redaction later would make the `SEC` evidence retrospective.
3. **S2 — Failure surface.** Retry scheduling, attempt records, retry exhaustion, permanent failure, lease acquisition and expiry, and interruption injected both before and after a durable effect.
4. **S3 — Concurrency.** Two worker processes against one database: claim exclusivity under `FOR UPDATE SKIP LOCKED`, duplicate delivery, and idempotent `platform_effect` behavior. **This is the decision point for H2.** If H2 is refuted here, the experiment stops and reports rather than continuing to S5.
5. **S4 — Safety.** Secret-store location guard on the application startup path, loopback binding default, invalid-configuration rejection as a non-retryable configuration failure, and redaction verified across logs, errors, and API responses.
6. **S5 — Operator surface.** Operator HTTP API first, then the `OPS` scenarios written against the failures S2 and S3 actually produced, then the minimal dashboard, then worker lifecycle and safe shutdown.
7. **S6 — Evidence and gate.** Formal evidence run, this record's Observations and Result, the gate record, and an adversarial review of every `PASS` claim before the gate is signed.

Concurrency, retries, failure injection, and cleanup are specified per scenario in `tests/acceptance/`. Lease durations are configurable and set short in tests so that expiry is observed without real elapsed time.

## Evidence collection

- Metrics and units: job state transition counts, attempt counts, claim conflicts observed (count), duplicate durable effects observed (count), retry exhaustion latency (ms), lease recovery latency (ms)
- Log or trace location: `experiments/integrated-p0/evidence/<YYYY-MM-DD>-<sha7>/platform.jsonl`
- Output artifact location: `experiments/integrated-p0/evidence/<YYYY-MM-DD>-<sha7>/`
- Integrity check or hash procedure: each evidence directory contains `ENVIRONMENT.md` recording the code revision, tool versions, and reproduction command. Structured logs use `.jsonl` rather than `.log` because `.gitignore` excludes `*.log` and the evidence must be reviewable from the repository.

## Observations

Record direct experimental outcomes as `[측정]`. Include input size, environment, execution time, units, and error bounds or known limits.

```text
[측정] not yet executed
```

## Interpretation

```text
[추론] not yet available
```

## Result

- Outcome: `SUPPORTED | REFUTED | INCONCLUSIVE` — not yet determined
- Falsification condition met: `NOT TESTED`
- Exit condition met: `NO`
- Known limitations: to be recorded

## Impact and next action

- Uncertainty reduced: to be recorded
- New uncertainty discovered: to be recorded
- Proposed next experiment: P0-B B1 source exploration, after the P0-A Completion Gate is accepted
- Proposed contract change: to be recorded
- Proposed Decision Packet update: [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) is proposed for acceptance at the gate together with the evidence showing whether each of its choices held

## Artifacts

- Experiment record: this file
- Code: `experiments/integrated-p0/platform_core/`, `experiments/integrated-p0/dashboard/`, `scripts/with-database.sh`
- Fixture or retrieval procedure: synthetic, generated in-test; no external retrieval
- Logs, metrics, traces, or screenshots: `experiments/integrated-p0/evidence/<YYYY-MM-DD>-<sha7>/`
- Output and hashes: recorded per evidence directory in `ENVIRONMENT.md`
- Data class and retention responsibility: `public`; synthetic only; retained in the repository as gate evidence, with disposition decided by the P0-B artifact disposition register

## Completion checklist

- [ ] The hypothesis is falsifiable.
- [ ] The falsification and exit conditions were fixed before interpreting the result.
- [ ] Inputs, rights, environment, versions, and hashes are recorded.
- [ ] The procedure is replayable without relying on undocumented session context.
- [ ] Observations and interpretations use the project evidence labels correctly.
- [ ] Secrets, restricted inputs, and raw conversations are absent.
- [ ] The result includes limitations and a concrete next action.
