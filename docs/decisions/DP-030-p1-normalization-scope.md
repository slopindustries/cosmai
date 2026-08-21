# DP-030 — Scoping P1 normalization: fault-tolerant per record, deterministic by metadata only

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-21
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-21, brainstorming session — docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md)`
- Related Open Questions: [OQ-003](../open-questions/OQ-003-normalization-protocol.md) — partial. The provider protocol itself (input/output/error contract, `NormalizeContext`) remains open, carried into the `addon_api` 1.3 reconstruction; this packet answers only the five scope questions below.
- Affected contracts: [`PoC Contract 0.1`](../../contracts/experimental/POC-CONTRACT-0.1.md) §5 Normalization
- Affected acceptance tests: none yet — implementation is M4 (see Required changes)

## Decision question

P0-B built normalization against a provisional schema and one rule-based normalizer, and the
attacks on both left a specific record: determinism holds in a form stronger than the
contract requires but only for the normalizer P0 built; a single malformed record can abort
an entire run; a rule-based quality verdict has stated gaps a reviewer, not a test, currently
catches; the schema union grew from one member to three across three sources; and nothing
guarantees the order in which a run processes its members. This packet decides, for each of
those five, what P1's normalization contract requires and what it explicitly does not.

## Candidates

**Determinism (contract requirement or not):**

1. Require byte-identical determinism as part of the P1 contract, as `PoC Contract 0.1` §5
   currently does.
2. Exclude determinism from the contract requirement; preserve normalization-time metadata
   (add-on id and version, execution time, snapshot id) instead.

**Per-record failure handling:**

1. Skip and count a failing record — the add-on contract's existing promise, which
   `P1-INHERITED-DEFECTS.md` §1 measured does not hold above the add-on.
2. Missing-value substitution plus a per-record `normalize_error` note; the run continues and
   its summary aggregates the error-record count.
3. Abort the run on any record failure — the behavior actually measured in P0.

**Quality judgment:**

1. Inherit `normalizer.rule.baseline`'s rule-based `clean` verdict into P1.
2. Carry no rule-based quality judgment and no self-certified `clean` into P1.

**Schema scope:**

1. Redesign the normalized-record union from scratch for P1.
2. Inherit `Normalized Schema 0.3` (envelope plus `record_type` union); register new
   `record_type`s as roadmap candidates rather than committing them as contract work now.

**Member ordering:**

1. Require the host to guarantee normalizer execution or member order.
2. Do not require it, consistent with not requiring determinism.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Normalization-time metadata (add-on id and version, execution time, snapshot id) is enough to support a P1 reader who needs to know how a result was produced, without the contract requiring byte-identical determinism. | A P1 use case cannot be served without reproducible normalizer output, and no metadata substitute closes the gap. |
| H2: Missing-value substitution plus a per-record `normalize_error` note is enough to keep a normalize run alive across an unpredictable per-record failure. | A record failure exists that cannot be represented as a missing value plus a `{field, reason}` note without losing information a downstream reader needs. |
| H3: P1 does not need a rule-based `clean` or quality verdict to make normalized output usable. | A P1 milestone requires distinguishing "clean" from "not clean" records without a human reviewer or a later service performing that judgment. |
| H4: The `record_type` union stays a small, source-bounded set rather than growing without limit. | The number of `record_type` members approaches the number of sources — the failure condition DP-019's own falsification table already names. |

## Experiment

- Scope: this packet decides from P0-B evidence already recorded against `normalizer.rule.baseline@0.1`, `normalizer.obf.product@0.1`, the host's `_NormalizeRun.execute`, and three schema decisions (DP-019, DP-021, DP-028); it runs no new experiment.
- Environment and versions: as recorded in the cited attack reports and `project-state.md` §5.
- Input and fixture identity: `normalizer.rule.baseline@0.1`'s fixture-based mutation and differential runs; `normalizer.obf.product@0.1`'s real Open Beauty Facts rows; the surrogate-payload case (`{"code":"a\ud800"}`) that raised inside `domain.store.canonical_body`; a member-order reversal against `_NormalizeRun.execute`; `plan.md` §3.1, §3.4–§3.5, §4.4 (owner's raw notes, repository root, untracked); [the reconstruction spec](../superpowers/specs/2026-08-21-p1-reconstruction-design.md) §2.3.
- Procedure: as recorded in `P1-INHERITED-DEFECTS.md` §§1–2, §7, `project-state.md` §5's rule-baseline and schema hypotheses, and DP-019/DP-021/DP-028.
- Known limitations: all cited measurements are about P0's normalizers and host. This packet decides what P1's contract requires; it does not claim P1's rebuilt `addons`/`addon_host` have reproduced any of it yet.

## Evidence

`[측정]` `project-state.md` §5 records that `normalizer.rule.baseline@0.1`'s determinism held
across three independent attacks: the second killed 11 mutants and ran 16,000 differential
comparisons across hash seeds with zero divergence, and the third ran 4,000 more with zero
divergence. `[확인 사실]` [DP-019](DP-019-normalized-schema-0-1-and-results.md) D4 states this
is enforced structurally, not merely observed: `NormalizeContext` exposes no clock and no
random source, and the host canonicalizes and digests `body` on the way in.

`[확인 사실]` DP-019's own falsification table for its determinism claim (D4) names "a rule
whose output depends on locale, platform, or dictionary version" as the untested case. P0
built and measured only deterministic, rule-based normalizers; nothing measured a
probabilistic or learned provider against this claim.

`[측정]` `P1-INHERITED-DEFECTS.md` §1: a payload carrying a lone surrogate
(`{"code":"a\ud800"}`), emitted by a normalizer, raises `UnicodeEncodeError` inside
`domain.store.canonical_body`. One bad row ends the whole normalize run instead of being
skipped and counted, in both `normalizer.obf.product` and `normalizer.naver.blog`. The
finding is recorded as platform-level and outside every P0 packet's allowed files, and as
`[추론]` "the most consequential row in this file: it converts a data-quality event into an
availability event."

`[측정]` `P1-INHERITED-DEFECTS.md` §2: `normalizer.rule.baseline@0.1` has six stated gaps,
including that a rule reaching no verdict is subtracted into `rules_evaluated` and the
record is emitted `clean: true` regardless — `_coverage` cannot catch this because coverage
is computed by subtraction. `project-state.md` §5 records the same finding independently:
three review rounds established that `_coverage` cannot catch it, and "what the baseline
exposed was a schema and record problem, not a data-quality one."

`[측정]` `project-state.md` §5: the schema hypothesis was refuted in its strong form — a
blog document and a DataLab trend point share only identity, time, and provenance.
[DP-021](DP-021-schema-0-2-trend-points.md) adopted the weaker envelope-plus-per-type-body
form. A third source, an Open Beauty Facts product row, shared the same reduced overlap with
the other two, and [DP-028](DP-028-schema-0-3-product-records.md) answered it the same way —
a third union member, not a wider common body. `[추론]` "Two record shapes could be
coincidence; three is a pattern," with the recorded caveat that two of the three sources
share one provider, so what varies here is record shape, not provider count.

`[측정]` `P1-INHERITED-DEFECTS.md` §7: "The host path itself is unguarded... Reversing
member order in `_NormalizeRun.execute` leaves 112 of 113 tests green," found by
`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-F and carried by nothing until that
register existed.

## Decision

`[결정]` **D1 — Deterministic normalization is excluded from the P1 contract requirement.**
Normalization-time metadata (add-on id and version, execution time, snapshot id) is
preserved in `normalized_result` to support a reader instead. `[확인 사실]` P0 measured the
strong form to hold — for the deterministic, rule-based normalizers it built, and only for
those.

`[확인 사실]` **Correction, 2026-08-21 (fix-wave repair of `REVIEW-GATE-M0` F15).** The owner's
own words at `plan.md` §3.1 are, in full: *"결정적 정규화: 불가능. 단지 정규화 당시의 메타데이터
정보로 보조하도록."* ("Deterministic normalization: not possible. Only have it assisted by
normalization-time metadata.") That sentence does not itself mention LLM- or ML-based
normalizers; an earlier revision of this paragraph attributed that rationale to the owner at
`plan.md` §3.1, which the source does not say. The LLM/ML rationale is the design session's own
gloss, recorded in [the reconstruction spec](../superpowers/specs/2026-08-21-p1-reconstruction-design.md)
§2.3's P1-처리 column for item 3.1: *"정규화 시점 메타데이터(애드온 버전, 실행 시각, snapshot
id)로 보조. 향후 LLM/ML 정규화기 고려."* ("Assisted by normalization-time metadata... future
LLM/ML normalizers considered.")

`[측정]` P0 measured deterministic, rule-based normalization holding in a **strong** form —
byte-identical across interpreters and hash seeds, structurally enforced by `NormalizeContext`
exposing no clock and no random source (see Evidence above). `[확인 사실]` The owner's "불가능"
is recorded here as the owner's own assessment, not as a measurement this project made; this
packet does not reconcile the two statements, because the decision below does not depend on
which one is more accurate — a contract that required byte-identical determinism would foreclose
a normalizer whose output is not reproducible by construction, whether or not the one normalizer
P0 actually measured needed to be that kind. `[결정]` The owner declined to promote determinism
to a P1 contract requirement; that decision stands either way this tension is read.

`[결정]` **D2 — Record-level fault tolerance is a P1 requirement.** On a record's
normalization failure, the run substitutes missing values for that record's fields, writes
`normalize_error {field, reason}` to the record's `notes`, and continues; the run summary
aggregates the error-record count. This is `P1-INHERITED-DEFECTS.md` §1's repair at the
contract-requirement level — a single malformed row must not end the run. It does not by
itself assert that P1's rebuilt `domain.store.canonical_body` (or its successor) has
implemented the guard; that implementation is named in Required changes.

`[결정]` **D3 — Rule-based quality judgment and self-certified `clean` are not carried
forward.** `normalizer.rule.baseline` is not inherited into P1 (`plan.md` §3.4, §3.5).
Basis: its `clean: true` verdict cannot be trusted where a rule reaches no verdict, and three
independent P0 review rounds could not make `_coverage` catch that case by test rather than
by manual review.

`[결정]` **D4 — `Normalized Schema 0.3` (envelope plus `record_type` union) is inherited.**
New `record_type`s are registered as roadmap candidates
([`RC-005`](../roadmap-candidates.md), covering the trend-radar rank/review family and the
YouTube video family) rather than committed as contract work in this packet.

`[결정]` **D5 — The host's member-order guarantee is not required.** Consistent with D1: a
contract that does not require determinism has no basis to require a fixed processing order
either, and `P1-INHERITED-DEFECTS.md` §7 already measured that P0's host does not guarantee
one.

## Rejected alternatives

- **Requiring determinism at the contract level (determinism candidate 1).** Rejected: it
  would hold every future normalizer, including an anticipated LLM- or ML-based one, to a
  property P0 measured only for deterministic rule logic — and DP-019's own falsification
  condition for that claim (a locale-, platform-, or dictionary-dependent rule) was never
  tested.
- **Skip-and-count without a value substitute (per-record candidate 1).** Rejected: this is
  the add-on contract's existing promise, and `P1-INHERITED-DEFECTS.md` §1 measured that it
  does not hold above the add-on — a failure below the normalizer still aborts the run. The
  gap is closed by making the record-level fallback (D2) a contract requirement, not by
  restating a promise already measured broken.
- **Inheriting `normalizer.rule.baseline` (quality candidate 1).** Rejected: three review
  rounds recorded stated gaps a test cannot catch, and the owner's session answer (`plan.md`
  §3.4–3.5) declined quality judgment as a P1 requirement independent of that measurement.
- **Redesigning the schema union from scratch (schema candidate 1).** Rejected: three
  sources across two providers already fit the envelope-plus-union shape without forcing a
  wider common body; discarding a union that measured evidence supports, to redesign against
  no new evidence, has no stated benefit.
- **Requiring host member order (ordering candidate 1).** Rejected in the 2026-08-21 session
  as unnecessary (`plan.md` §4.4), and requiring it would be inconsistent with D1's decision
  not to require determinism.

## Tradeoffs and risks

- Benefits: P1's normalization contract does not foreclose a future non-deterministic
  provider; a single malformed record degrades a run instead of aborting it; the contract
  does not carry forward a quality claim P0's own reviews could not make a test enforce.
- Costs: P1 ships with no automated quality signal on normalized records at all — `clean`
  and "not clean" become entirely a human or downstream-service judgment, with no baseline
  to fall back on. Reproducibility becomes a metadata trail rather than a guarantee; a reader
  who needs byte-identical replay must reconstruct it from `add-on id/version + execution
  time + snapshot id`, not obtain it as a contract property.
- Failure modes: a future normalizer whose output silently drifts (a dictionary update, a
  platform change) is invisible under D1 unless something outside this contract watches the
  metadata trail — nothing in this packet assigns that watching to anyone.
- Reversibility: D1 and D5 are contract *omissions*, not prohibitions — a later packet can
  add a determinism or ordering requirement for a specific normalizer without contradicting
  this one. D3 is similarly reversible: nothing here forbids a future quality baseline, only
  declines to inherit this one. D4 already anticipates growth through RC-005; D2 is the
  costliest to reverse, since downstream readers would come to depend on the
  missing-value/`notes` shape.

## Remaining uncertainty

- D1 does not cover a future contract that requires reproducible normalization results — if
  a P1 milestone needs byte-identical replay as a property rather than a metadata trail, this
  decision must be revisited, not silently overridden.
- The union-growth falsification condition DP-019 stated — the number of `record_type`
  members approaching the number of sources — remains in force. Accepting an `RC-005`
  candidate must re-check it, not assume D4 already cleared it.
- D3's absence of a quality signal is not evaluated against any specific P1 milestone's
  needs; if one turns out to require distinguishing clean from suspect records, this
  decision is what blocks it until revisited.

## Required changes

- Project State: record OQ-003 as partially addressed by this packet (protocol itself stays
  open) and this packet's D1–D5 in §4 Accepted for P0.
- Contract or schema: `PoC Contract 0.1` §5 should drop "Determinism is required" as a
  blanket normalizer obligation and state D1's metadata-preservation requirement, D2's
  per-record fault-tolerance requirement, and D5's non-requirement of member order in its
  next revision.
- Acceptance tests: none by this packet; per-record fault-tolerance tests (D2) and the
  removal of any determinism-only acceptance criterion are M4 implementation work.
- Migration or compatibility: none — Schema 0.3 (D4) is already additive; no existing
  normalizer's `output_contract_version` changes.
- Implementation handoff: M4's normalizer add-ons implement D2's missing-value/`notes`
  fallback and D1's normalization-time metadata fields; `RC-005` stays the landing point for
  any new `record_type` design.
