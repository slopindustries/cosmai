# DP-010 — Durable work inside the completion transaction

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-18
- Owners: Project team
- Supersedes: one clause of [DP-008](DP-008-addon-architecture.md) D1 — "`platform_core` gains no new dependency and is not modified by this work". Every other DP-008 decision stands.
- Related Open Questions: [OQ-006](../open-questions/OQ-006-job-concurrency.md) H1
- Affected contracts: `CONTRACT-JOB@0.1`'s durable-effect surface
- Affected acceptance tests: `JOB-008`, and the new `ACQ`/`RAW` atomicity scenarios

## Decision question

A collection writes a Raw envelope, its items, and a cursor — several statements across
several tables, with no single key to collide on. The job runner executes a handler and
*then* completes the attempt, in a separate transaction. How does a multi-statement
durable effect become atomic with the completion that fences it?

## Evidence and reasoning

`[확인 사실]` The [P0-A Completion Gate](../../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md)
records this as the first of nine things it does not claim, in its own words:

> Every duplicate-suppression result rests on one row and one primary-key conflict. A
> P0-B acquisition or normalization effect spans several statements and probably several
> tables, where the question becomes transactional. This is the sharp form of OQ-006 H1
> **and the largest gap P0-A leaves.**

`[추론]` So this is not a boundary being crossed. It is the work P0-A recorded as
unfinished, and the runner's arrangement — handler, then completion, two transactions —
is precisely *why* it was unfinished.

`[확인 사실]` The scenario that decides the shape: a worker stalls past its lease, another
worker reclaims the job and starts from the un-advanced cursor, and the first worker then
commits. Both workers' rows are present and nothing distinguishes them. The platform's
existing answer to duplicate delivery is an idempotent key, and `raw_item` has none —
what duplicate policy it should carry is an open contract question that must not be
answered by implication here.

`[추론]` Therefore the completion must be **inside** the transaction and **last**. A
refusal that arrives after the writes have committed is too late; inside, it discards
them.

### Why DP-008 D1's wording was wrong

`[확인 사실]` D1 says `platform_core` "is not modified by this work". `[추론]` That
sentence was broader than the principle behind it. The principle is that `platform_core`
stays **source-neutral** — which is what the rescoped boundary guard enforces and what
DP-005 actually requires. A transaction boundary knows nothing of sources, Raw, or
normalization; a synthetic handler benefits from it identically. The wording forbade a
change the principle permits.

### Why not the alternatives

- **Run the whole handler inside a transaction.** A collector fetching twenty pages would
  hold a database transaction open across all of that network I/O. Rejected on that cost.
- **Let the capability layer complete, and let the runner's later completion be refused.**
  `platform_core` would be untouched, but every successful domain job would report
  `completion.accepted == False` — telemetry saying "the fence refused" about a job that
  succeeded. Rejected: a record that is false is worse than a record that is missing.
- **Drop atomicity and let duplicates happen.** Honest about at-least-once delivery, but
  it answers `raw_item`'s open duplicate-policy question by implication. Rejected.

## Decision

`[결정]` **Generalize the durable effect from one row to a callable that runs inside the
completion transaction.**

- `JobContext.enlist_durable_work(work)` registers a `Callable[[], None]`.
- The runner runs enlisted work after the handler returns, then the fenced completion,
  both inside `JobStore.durable_scope()`.
- A refused completion unwinds the scope, so a worker that lost its lease persists
  nothing. The refusal is still **returned as a value**, not raised — `run_once`'s
  contract is unchanged.
- **A handler that enlists nothing takes exactly the path it always did**: one statement,
  one transaction. P0-A's evidence is unaffected, and a test asserts that.

`[결정]` This does not change what a durable effect *means*. `apply_effect` remains the
one-row form and remains correct; this is the same idea at the size the gate said P0-B
would need.

`[결정]` DP-008 D1's principle is restated: **`platform_core` stays source-neutral.** It
is not frozen. A change to it must be generic, must leave the boundary guard green, and
must be recorded.

## Tradeoffs and risks

- **Benefit:** the largest gap P0-A recorded now has a mechanism and evidence. A collector
  cannot half-write a collection, and a reclaimed worker cannot write at all.
- **Cost:** `platform_core` is modified after the P0-A gate certified it. The gate's
  evidence concerns behaviour the change preserves — a handler enlisting nothing follows
  the original path — but the certified revision is no longer the current one, and the
  evidence README already records that this was true before this change for other reasons.
- **Failure mode:** a handler that enlists work doing something slow puts it inside the
  transaction. The mechanism does not prevent that; the authoring guide says to fetch
  first and enlist only the writes.
- **Reversibility:** full inside disposable P0. The parameter has a default that changes
  nothing, so removing it is removing an unused argument.

## Remaining uncertainty

- Whether enlisted work is the right shape for normalization's result-writing, which has
  a sealed input and different failure semantics. Untested until B3.
- `raw_item`'s duplicate policy remains open, and this decision deliberately does not
  answer it.
- OQ-006 H1 now has a mechanism but not yet a measurement at scale — one host, few
  workers, small effects.

## Required changes

- **Project State:** record the DP-010 decision and DP-008 D1's restatement.
- **Contract:** `CONTRACT-JOB@0.1`'s durable-effect section gains the enlisted form.
- **Acceptance tests:** `tests/test_durable_scope.py`, 9 scenarios, including the
  reclaimed-worker case and its positive control.
- **Implementation handoff:** the add-on capability layer uses `enlist_durable_work` for
  Raw and cursor writes; the authoring guide states that a handler fetches first and
  enlists only its writes.
