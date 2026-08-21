# Architecture Synthesis v0.1

- Status: `DRAFT_FOR_GATE`
- Date: 2026-08-19
- Work package: P0-B B5
- Evidence base: `experiments/integrated-p0/` at the revision this document is committed with
- Suite: **1192 passed, 14 skipped**; `ruff` and `mypy --strict` clean over 92 files

`[결정]` This document answers the P0 Charter's eight Architecture Questions and the eight
questions [`README.md`](README.md) sets for this package. Where the answer is "not proved",
it says so in those words. `[추론]` A synthesis that reported only what worked would be the
same document a project that measured nothing could write.

---

## Part 1 — The eight Architecture Questions

### 1. Did the P0-A platform boundary survive P0-B without material replacement?

**`YES`, with three implementation defects and no boundary change.**

`[측정]` `git diff --shortstat f83fe3c -- platform_core` is **7 files, +246 −36**. Every
change is inside a boundary P0-A had already drawn:

| Change | What it was |
|---|---|
| `jobs/runner.py` +71 | F2 — an exception from enlisted durable work escaped unclassified and stopped the worker. The classification boundary was right; `_settle` was outside it. |
| `jobs/store.py` +107 | B6 — `job.claim_conflict` used two statements and therefore two clocks. One statement now. |
| `jobs/registry.py` +31 | F3 — a registry seam so the worker can rebuild it per connection. |
| `worker.py` +27 | The same seam's other half. |
| `config.py` +16, `api/*` +30 | One recognised variable and two display strings. |

`[추론]` **No P0-A premise was invalidated.** The fence, the lease, the effect key, the
correlation rule, and the error classification all held under a real add-on, real data, and
a real credential. The three defects were defects in the *implementation* of premises that
themselves held, which is the distinction B4 asks for when deciding whether to set the P0-A
gate to `REOPENED`. **It is not reopened.**

`[측정]` The strongest single piece of evidence: reverting the F2 repair produces **91
failures and 111 errors**.

### 2. Can one Raw envelope preserve both REST and dataset inputs without semantic loss?

**`YES`, and since 2026-08-20 the test is closer to the question — not level with it.**

`[측정]` `raw_envelope` carries a REST response (`endpoint_ref`, `status`,
`response_headers`, `request_summary`) and a dataset file (`input_ref`, no status, no
headers) through the same table and the same completion transaction. Both produce
`raw_item` rows whose payload is the bytes as read — the JSONL importer deliberately stores
the **line as read** rather than a re-serialization, because `json.dumps` would reorder keys.

`[추론]` The envelope did need widening: `endpoint_ref` and `status` became nullable and
`input_ref` joined them ([DP-024](../decisions/DP-024-local-input-registry.md)). That is a
column becoming optional, not a second table — the hypothesis survives in the form that
matters.

`[확인 사실]` **The paragraph this replaces said the dataset half was self-authored.** It was,
until [TASK-007](../agent-workflow/task-packets/TASK-007-obf-dataset-end-to-end.md).

`[측정]` **A real external producer's rows now pass the same envelope, 2026-08-20.** Open Beauty
Facts nightly delta exports — 121 and 126 products, retrieved anonymously with recorded digests
— produce one `raw_envelope` and `raw_item` rows whose payloads are byte-identical to the
source lines, adding no column and no table beyond DP-024's. `[추론]` The envelope has now
carried three independently shaped inputs: a REST search response, a DataLab trend point, and a
crowd-contributed product row. That is the claim the question asks for.

`[측정]` **What stays unexercised is narrower than before, and one part of it is worse than
unexercised.** The importer's three skip counters were all zero on the delta the test checks
them for; the second delta's counters were not asserted. So partial-validity handling is still
proved on [SRC-002](../../experiments/source-probes/SRC-002-local-jsonl.md)'s deliberately
broken fixtures rather than on a real file. `[결정]` That is the right way round: fabricating a
bad line inside a real export to exercise the path would have been inventing Raw.

`[측정]` **Duplicate row identity within one file cannot be exercised by this test at all.** It
asserts `len(set(codes)) == len(codes)`, so a duplicate would fail the test rather than
exercise the path. That weakness the earlier paragraph named is retired by construction, not by
evidence.

`[확인 사실]` **The third weakness that paragraph named — embedded newlines inside quoted
strings — is still unexercised and is not retired.** `importer.local.jsonl` splits on lines and
its own docstring records the `[가설]` that one line is one record, false for a JSON string
containing a newline; such a line is counted malformed rather than joined. No real delta
contained one.

`[측정]` **And one malformed shape is not merely unexercised — it aborts the run.** A payload
carrying a lone surrogate (`{"code":"a\ud800"}`) is emitted by the normalizer and then raises
`UnicodeEncodeError` inside `domain.store.canonical_body`, so **one bad row ends the whole
normalize run instead of being skipped and counted**. Measured 2026-08-20 in
[`ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md);
`normalizer.naver.blog` has the same exposure and it predates both. `[확인 사실]` It is
unguarded at `domain/store.py:132`. Carried in
[`P1-INHERITED-DEFECTS.md`](P1-INHERITED-DEFECTS.md). An earlier revision of this section said
only that malformed-row handling was unexercised on real data, which read as milder than what
was measured.

### 3. Where are the correct transaction and idempotency boundaries?

**Answered, and this is P0's strongest result.**

`[결정]` [DP-010](../decisions/DP-010-durable-work-in-the-completion-transaction.md): all
domain durable work is enlisted into the transaction that completes the attempt, with the
fenced completion **last**. A worker that lost its lease persists neither Raw nor cursor.

`[측정]` Proved three ways, each with a positive control so the assertion can fail:
`test_domain_store.py::TestCollectionIsAtomic` at the store level;
`test_capabilities.py::TestACollectionIsAtomicThroughAnAddOn` through a real add-on;
`test_job_interruption.py::test_job_005_*` across a killed process.

`[측정]` **The boundary is asked of the connection, not of the wiring.** F3 found that H2a
rested on a fixture's docstring: on its own autocommit connection the `DomainStore` still
never commits, and Raw survived a refused completion anyway — *"never commits"* and *"is
inside the fence's transaction"* are different properties. The repair asks
`transaction_status` at the moment of writing.

`[결정]` Idempotency sits on two keys: `platform_effect`'s primary key for platform effects,
and `normalized_result`'s unique index on (run, item) for normalization. A rerun is a
duplicate, not a version.

### 4. Does the job state machine support independent collection and normalization recovery?

**`YES`, structurally and by test.**

`[결정]` [DP-019](../decisions/DP-019-normalized-schema-0-1-and-results.md) D6: normalization
is a **separate job** started by an operator naming a sealed snapshot. Collection never
starts normalization.

`[추론]` Independence follows from that rather than from a recovery mechanism: a
normalization failure cannot touch Raw because Raw was sealed before it began, and a
collection failure cannot leave a half-normalized result because normalization has not
started. `[측정]` `test_normalizer_capability.py` fails normalize jobs — miscounting,
orphaned lineage, wrong return type, tampered input — and Raw is untouched in every case.

`[측정]` Two deliberate buttons on the dashboard, not one, and
`test_operator_loop.py` drives the four acts separately. One button that did both would be
this rule quietly broken.

### 5. Does the sealed snapshot protect reproducibility from Raw-store evolution?

**`YES` for tampering; `YES, NARROWLY` for evolution since 2026-08-20; and two new identity gaps.**

`[측정]` Tampering is detected: `test_a_tampered_snapshot_fails_the_run_before_the_add_on
sees_a_byte`, with an untampered control. The manifest digest and per-member digests are
both checked, and `problems` names which failed. Two real captures were sealed with
recorded manifest digests.

`[확인 사실]` **The paragraph this replaces said Raw-store evolution was never exercised.** It
was not, until [TASK-005](../agent-workflow/task-packets/TASK-005-snapshot-evolution-that-discriminates.md).

`[측정]` **It is exercised and it discriminates.** An additive migration, a later collection
superseding a sealed key, and a purge of every Raw row: the sealed snapshot verifies and
replays byte-identically at all four steps, while a re-query design replays different bytes at
step three and nothing at step four. Four mutations of the seal and read are killed by the
discrimination class's own control, so the experiment is not decorative.

`[측정]` **Narrowly, because against the design [OQ-004](../open-questions/OQ-004-snapshot-boundary.md)
actually names — references to append-only Raw rows, fixed at seal — only the purge separates
the two.** A materialized snapshot beats a re-query at the migration and the supersession; it
beats a reference design only when the referenced rows are gone.

`[측정]` **A purge does not discharge an erasure obligation.** After deleting every `raw_item`,
`snapshot_item` still holds the bytes and `raw_envelope` holds the lossless original. So a
snapshot's persistence has a cost, and whatever discharges an erasure obligation, it is not one
`delete`.

`[측정]` **The new gap, found 2026-08-20 on real data.** Which member wins when two observations
of one key are sealed together is decided by `emitted_at`, which defaults to `now()` — a
**transaction** timestamp. So "the later import wins" holds per import transaction, not per row,
and nothing states that two imports must be separate transactions. Forcing a tie and re-sealing
twelve times drops the decision to `id desc` on a `uuid4`, and two of three keys then selected
the *older* payload. `[결정]` Recorded in OQ-004 as a contract question for P1 rather than
repaired in P0, and it is an explicit unresolved item for the P1 Entry Gate.

`[확인 사실]` **A second identity gap belongs beside it and this answer previously omitted it.**
DP-019 D5 orders snapshot members by `item_key` and fixes no collation, so two clusters
differing only in locale seal **different manifest digests from identical Raw**. Found by the
same review that established the discrimination above, and carried in DP-019 and OQ-004.

`[확인 사실]` Both gaps, and the erasure cost above, are registered in
[`P1-INHERITED-DEFECTS.md`](P1-INHERITED-DEFECTS.md) §5.

### 6. Which component and process boundaries are useful rather than ceremonial?

**Useful:**

- `[측정]` **`platform_core` ← `domain`.** The one-way rule caught real mistakes: the
  boundary guard refused domain vocabulary in `platform_core` **five times** this session,
  each time correctly, including an MVCC "snapshot" in a SQL comment.
- `[측정]` **`addons/* → addon_api` only.** It forced three defects into the open that a
  shared helper would have hidden, and it is what makes an add-on's dependencies auditable.
- `[측정]` **The capability layer.** The add-on names an endpoint or an input; the platform
  owns the destination. An independent security review could not route a request outside the
  approved grant.
- `[측정]` **The operator-approved profile as the grant.** `[declares]` is a request and the
  source row is the permission. This is the single structure that makes "an add-on cannot
  widen its own allowlist" checkable rather than asserted.

**Ceremonial or costly:**

- `[측정]` **The add-on layer rule buys portability and pays duplication.** 13–15% of each
  collector is source-independent plumbing, duplicated because the rule forbids sharing it;
  165 identical lines between two collectors. Recorded as
  [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) rather than removed.
- `[측정]` **Duplicated guards in the *host* were a real defect source**, not a style issue:
  seven guard clauses were GREEN in at least one of their two copies. Two of them are now one
  shared helper; the rest are tested per copy.
- `[추론]` **`_UNBOUND_KINDS` was useful and is now empty.** Refusing a capability *by name
  with a reason* is what made both `normalizer` and `importer` land as deliberate work rather
  than as silent gaps.

### 7. Which dashboard actions and telemetry are actually needed?

`[측정]` Four actions, one per act of the operator loop: **collect, seal, normalize, read**.
`test_operator_loop.py` drives exactly these and nothing else was needed to run the pipeline.

`[측정]` Telemetry that earned its place: `correlation_id` on every line concerning a job
(I5 — and B6 was the one line that violated it); job state transitions; error class with
retryability; the attempt number; `envelope_count` and `item_count` per source; snapshot
`verifies` **as its own column**, because a screen that said only "sealed" would make a
tampered input look ready to run.

`[측정]` Telemetry that did **not** earn its place: `claim_conflicts`. `EXP-001` already
recorded it as *"not a usable contention measure"*, and B6 found it also reported conflicts
that never happened. It is fixed, and it is still not a contention measure.

### 8. Which normalized fields survive contact with both real sources?

**Only the envelope. The strong hypothesis is refuted, and a third real source confirmed it.**

`[측정]` Recorded in `project-state.md` §5 on 2026-08-19 and carried here as the charter
asks. Against a blog document and a DataLab trend point the **only** overlap is identity,
time, and provenance — the fields any record needs to *be* a record. There is no common
domain meaning between *"someone wrote this"* and *"people searched this much"*.

`[결정]` [DP-021](../decisions/DP-021-schema-0-2-trend-points.md) adopts the weaker form:
one schema carries a common **envelope** (`schema_version`, `record_type`, `external_id`,
provenance) and a per-type **body**, as a discriminated union. Schema 0.2 adds `trend_point`
beside `document`.

`[측정]` **A third real source arrived on 2026-08-20 and did not rescue the strong form.** An
Open Beauty Facts product row — barcode, name, brand tags, revision timestamps — shares with a
blog document and with a trend point exactly what those two share with each other: identity,
time, provenance. Nothing else. `[결정]`
[DP-028](../decisions/DP-028-schema-0-3-product-records.md) therefore answered it the way
DP-021 answered the second source, with a third union member rather than a wider common body,
and Schema 0.3 is 0.2 plus `product`.

`[추론]` This is the most valuable negative result P0 produced, and it would have been
expensive to discover in P1: a single flat normalized table across these sources would
have been mostly null columns with a type discriminator smuggled in as a convention.
`[추론]` **Two record shapes could have been a coincidence of pairing; three is a pattern** —
with the caveat that two of the three come from one provider, so what varies across them is
record shape, not provider. `[가설]` The union's cost is that it grows one member per source shape,
which is bounded only if source shapes are few — falsified by a P1 source set where the member
count approaches the source count, and that is the question this answer hands forward rather
than closes.

`[확인 사실]` **What no source has yet tested is the question's own word "survive".** All three
answers compare *schemas* at the point of normalization. No P0 evidence says which fields stay
correct, populated, or meaningful over time, because no source was normalized twice across a
real content change and compared. `[측정]` The nearest thing is three Open Beauty Facts
`code`s that appear in both captured deltas, whose normalized bodies were never diffed against
each other. `[확인 사실]` Those same three `code`s were separately measured by
[SRC-003](../../experiments/source-probes/SRC-003-open-beauty-facts.md) as having advanced
`rev` and `last_modified_t` against the live API 23 hours later — a **different comparison**,
and no artifact states that the delta-to-delta pair shows the same advance. An earlier revision
of this sentence spliced the two measurements into one claim.

---

## Part 2 — Assumptions: validated, invalidated, unresolved

| Hypothesis (`project-state.md` §5) | Outcome |
|---|---|
| A source-independent platform core can expose useful execution, recovery, operator, and safety evidence before the domain exists | **Validated.** P0-A's gate evidence held through P0-B; the platform boundary survived. |
| PostgreSQL job tables with at-least-once processing and idempotent effects are sufficient for P0 concurrency | **Validated within P0's scale.** 200 jobs × 4 processes; `[측정]` load-sensitive at that size, which is a measurement about the machine as much as the design. |
| One Raw envelope can represent both REST responses and dataset rows without loss | **Validated for the shapes tested**, with the dataset half self-authored. |
| A materialized snapshot plus manifest and hashes is sufficient for replay despite Raw-store change | **Half validated.** Tampering detected; Raw-store *evolution* never exercised. |
| One small `Normalized Schema 0.x` can express useful common meaning across the first two sources | **Refuted in its strong form.** See Question 8. |
| A rule baseline can expose schema and quality problems before ML or LLM providers | **Not tested.** No quality baseline was built; the normalizers extract, they do not judge. |

---

## Part 3 — Shortcuts that must not be reproduced

`[결정]` Each of these was the right call for a disposable prototype and is a defect in
anything durable.

1. **`SEC-006` is waived, not satisfied** ([DP-023](../decisions/DP-023-sec-006-waived-for-p0.md)).
   The agent sandbox was never narrowed; outbound safety rests entirely on the application
   guard. That guard had **four** defects in one day. P1 gets no such waiver.
2. **In-process add-ons are trusted code** (DP-008 D10). Isolation is contractual and
   test-enforced, not enforced by the operating system. `[추론]`
   [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) is the live proposal to
   replace it with a process boundary.
3. **The source selection record was written after the integration.** B1 places selection
   before implementation; it happened the other way round and the matrix says so.
4. **One capture's digest was lost.** A scenario cleared the tables before the hash was
   written down. `[추론]` The procedural lesson — take the digest while the rows exist — is
   recorded with the evidence.
5. **Judgments only an add-on can make are unchecked by anything**
   ([OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) clause C).
   `_MONTH_LENGTH` was GREEN in both copies until 2026-08-19.
6. **Documentation drifted from the code nine times in one session.** Every instance was a
   prose claim the code did not deliver, and none was caught by a test. `[추론]` This is the
   single most repeated failure shape in P0 and the one least addressed by the current
   toolchain.

---

## Part 4 — If the team started again with current evidence

`[결정]` **Keep the platform core's shape.** The job table, the lease and fence, the effect
key, the completion transaction, and the correlation rule all survived contact and are the
part of P0 that earned promotion to a contract.

`[결정]` **Keep the capability layer's *direction*** — the add-on names, the operator's
profile decides — and **re-examine its seam**. The evidence for the direction is strong; the
evidence about *where* to cut is the 13–15% duplication and the unverifiable-judgment
problem. [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) proposes cutting at a
service boundary instead, which would convert a contractual trust boundary into a process one
— the thing DP-008 wanted and could not afford.

`[결정]` **Adopt the discriminated-union normalized schema from the start.** Question 8's
refutation is the finding most likely to be re-discovered expensively.

`[추론]` **Do not start P1 by porting P0.** P0 code must not become a P1 dependency, and the
areas with the most P0 investment — the outbound guard, the capability layer — are also the
areas whose *shape* is still under an open question.

---

## Part 5 — What is ready for `PoC Contract 0.1`

`[결정]` Under the project owner's decision of 2026-08-19, the eight domain contract families
B2 named are folded into `PoC Contract 0.1` rather than written as separate interim
documents. Ready, with the evidence named:

| Area | Source of truth | Readiness |
|---|---|---|
| Job, error, state, correlation | [`CONTRACT-JOB-0.1.md`](../../contracts/experimental/CONTRACT-JOB-0.1.md) | **Ready.** Already versioned and executed. |
| Add-on contract | [`CONTRACT-ADDON-1.3.md`](../../contracts/experimental/CONTRACT-ADDON-1.3.md) | **Ready.** Written 2026-08-19 to close the gap M5 found; `addon_api` remains the authority and the document says so. |
| Raw and provenance | `0002_domain.sql`, DP-024 | **Ready.** |
| Snapshot | `0002_domain.sql`, DP-019 | **Ready for tampering; unproved for store evolution.** |
| Normalization | DP-019, DP-021, `0003_normalized_result.sql` | **Ready as 0.2**, with the strong hypothesis recorded as refuted. |
| Outbound / source policy | `domain/outbound.py`, DP-018, DP-020 | **Ready**, with `SEC-006` waived and rate-limit behaviour `UNKNOWN`. |
| Local input policy | DP-024, `domain/inputs.py`, `0004_input_profile.sql` | **Ready as a mechanism**, untested against a real dataset. |
| Credential scope | DP-018, `secret-setup.md` | **Ready for the header case.** OQ-009 H1's query-parameter and signed-request cases remain open. |
| Operations | OQ-005, `test_ops.py`, `test_dashboard.py` | **Ready.** |

---

## Part 6 — P0-B exit criteria

| Criterion | Status |
|---|---|
| One REST source and one dataset complete the end-to-end flow | **Met, with a stated substitution.** REST is real; the dataset is a structural stand-in ([SRC-002](../../experiments/source-probes/SRC-002-local-jsonl.md)). |
| Source rights or permitted experimental use are recorded | **Met.** [SRC-001](../../experiments/source-probes/SRC-001-naver-api-hub.md); redistribution explicitly `NO`. |
| Identical input replay demonstrates the chosen idempotency behavior | **Met.** Unique index; refused rather than doubled, against real data. |
| Changed source content creates a traceable new observation or version | **Partially met.** Two captures produce two envelopes, two snapshots, two digests. `[측정]` No test asserts what happens to the *overlap* between two captures of a moving source. |
| Parallel worker claims do not corrupt job state or create uncontrolled duplicate effects | **Met.** JOB-007; load-sensitive at 200×4. |
| Collection and normalization failures can be recovered independently | **Met.** DP-019 D6 plus `test_normalizer_capability.py`. |
| A sealed snapshot replays the same normalizer input and detects tampering | **Met for tampering.** Replay across Raw-store evolution is unproved. |
| Different normalizer or schema versions can coexist for the same Raw lineage | **Met.** `TestVersionsCoexist` — two add-on versions and two output-contract versions. |
| The dashboard identifies what ran, its input, state, failure, and retry action without database inspection | **Met.** OPS-001, OPS-002, SEC-004, and the operator loop over real data. |
| Required platform and domain `SEC` scenarios pass within the declared local boundary | **Met for SEC-001…004 as scenarios.** `SEC-006` as a *requirement* is **waived**, not passed. The two numbering schemes are reconciled in `p0-security.md`. |
| Every Architecture Question is answered with evidence or an explicit unresolved blocker | **Met** — Part 1. |
| Architecture Synthesis, disposition register, `PoC Contract 0.1`, and reconstruction plan accepted | **Pending the P1 Entry Gate.** |

---

## Unresolved blockers carried to the P1 Entry Gate

1. `SEC-006` — waived for P0 and expiring at that gate (DP-023).
2. No real dataset source characterised — `OQ-001` stays `OPEN` for that half.
3. Snapshot replay across Raw-store evolution — unproved.
4. Rate limiting, deep pagination, redirects, drift, and the `200`-with-an-error-body case —
   all **unobserved against a real source**.
5. [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) and
   [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) — the add-on seam is
   deliberately unsettled, and OQ-014 may change what P1 builds.
6. ~~The add-on contract has no document under `contracts/experimental/`.~~ **Closed 2026-08-19** — [`CONTRACT-ADDON-1.3.md`](../../contracts/experimental/CONTRACT-ADDON-1.3.md).
