# OQ-013 — What an add-on is responsible for, and what holds a judgment nobody can check

- Status: `OPEN`
- Priority: P0-B — shapes every collector written from here, and the P1 add-on contract
- Owner: Project team
- Blocks: the repair shape for `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5; any fourth collector
- Related experiments: [EXP-003](../../experiments/integrated-p0/EXP-003-capability-layer.md)
- Related: [OQ-014](OQ-014-externalized-acquisition.md), which may dissolve the first clause entirely
- Resolution Decision Packet: not created

## Question

Two clauses, both surfaced by the same measurement and both about where an add-on's
responsibility ends:

1. **Source-independent code.** An add-on may import `addon_api` and nothing else local.
   Every add-on therefore carries its own copy of the plumbing that has nothing to do with
   its source. Is that duplication a cost worth paying for the portability the rule buys,
   or does a shared runtime layer belong in the contract?
2. **Unverifiable judgment.** Some decisions can only be made by the add-on — "this HTTP 200
   is actually a failure", "stop at this cursor", "February has 29 days". The platform
   cannot check any of them. What holds the add-on to a judgment no other layer can see?

## Why this surfaced

`[측정]` Measured on 2026-08-19 against the three committed collectors:

| Add-on | total non-blank lines | source-independent plumbing |
|---|---|---|
| `collector.naver.shoppinginsight` | 292 | 46 (**15%**) |
| `collector.naver.searchtrend` | 282 | 37 (**13%**) |
| `collector.naver.blog` | 235 | 36 (**15%**) |

`[측정]` The two DataLab collectors share **165 textually identical non-blank lines**. The
independent reviewer measured the same duplication at **70%** of the smaller distinct
code-line set.

`[확인 사실]` The duplication is required, not accidental.
`tests/environment/test_addon_layer_direction.py` fixes `ALLOWED_IMPORTS["addons"] =
{"addon_api"}`. `addon_kit` exists and may import `addon_api`, but it is a generator and
harness — build-time only — and no add-on imports it at runtime. An add-on author has
nowhere to put a shared helper, so writing it twice is the only conforming option.

`[추론]` The rule that guarantees an add-on's portability also guarantees its duplication.
That is not a defect in the rule; it is the rule's price, and until now the price was not
measured.

`[측정]` The second clause is where the mutation review found silence. `_MONTH_LENGTH` is
duplicated across both DataLab collectors; making February accept 31 days is **GREEN in both
copies**. `[추론]` Nothing outside the add-on knows how long February is, so nothing outside
the add-on can notice.

`[추론]` The contrast is the useful part. The add-on responsibilities the platform *can*
adjudicate — which host, which path, which method, which headers, how many bytes, how long —
were moved to the platform by [DP-018](../decisions/DP-018-credential-parts-and-attachment.md) and
[DP-020](../decisions/DP-020-request-method-and-body.md). Four defects were found in that code
in a single day and **every one was caught RED**. The defects that stayed silent are all in
the judgments that never left the add-on. The distinguishing property is not how much
responsibility an add-on carries but whether anything can check it.

## Scope

### Included

- Whether a runtime layer between `addon_api` and `addons/*` should exist, and what it costs.
- How an add-on-only judgment is made visible to the platform — declared, reported, or
  reconstructed — and what the platform does when it is absent.
- Which of B5's GREEN clauses are repaired by tests and which need a contract change.

### Excluded

- The duplication inside `addon_host/capabilities.py` between `_CollectRun` and
  `_NormalizeRun`. `[확인 사실]` That is host code, ~610 and ~256 lines, and no change to
  add-on responsibility affects it. It is a test-placement repair, tracked in B5's first half.
- `job.claim_conflict` (B6), which is `platform_core` and unrelated.
- Whether acquisition should leave this service at all — that is [OQ-014](OQ-014-externalized-acquisition.md).

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: The 13–15% duplication is an acceptable price in a disposable prototype, and recording its size is worth more than removing it. | A defect is traced to the two copies drifting apart, or a fourth add-on makes the share materially larger. |
| H2: A shared runtime layer would cost more than it saves, because it re-creates the coupling `addon_api`'s emptiness exists to prevent. | A shared layer is written that no add-on can use to reach the platform, and the layer-direction guard still proves it. |
| H3: An add-on's judgment can be made checkable by requiring it to be *declared*, without the platform having to reproduce the judgment. | A judgment is found that cannot be expressed as a declaration the platform can hold the add-on to. |
| H4: Every silent-in-both-copies defect is a judgment clause, and every caught defect is a platform-adjudicable one. | A platform-adjudicable clause is found to be GREEN in both copies, or a judgment clause is found to be RED. |

## Alternatives

- **Record the cost, repair only the tests.** No structural change; the duplication becomes
  measured evidence about the layer rule. Chosen as the interim position below.
- **Promote `addon_kit` to a runtime library.** Removes the duplication and weakens the
  property that an add-on depends on the contract alone.
- **Widen `addon_api` with utilities.** Same effect through the contract package, at the cost
  of a contract that is no longer only a contract.
- **Require judgments to be declared and reported.** Extends the second clause rather than
  the first: the add-on still decides, but a decision it never reports is a refusal.
- **Generate the shared code.** `addon_kit` already generates skeletons; generating the
  helpers keeps the import rule and moves the duplication to a place with one source.

## Minimum experiment

- Write a fourth collector against a different source and measure whether the
  source-independent share holds near 13–15% or grows.
- For one judgment clause — the HTTP-200-that-is-a-failure decision — express it as a
  declaration the platform can enforce, and mutate the add-on to *omit* the report. The
  mutation must go RED without the platform reproducing the judgment.
- Positive control: the same mutation against today's code must be GREEN, so the experiment
  shows the change is what caught it.

## Interim position

`[결정]` **A + C**, decided 2026-08-19.

- **A — record, do not restructure.** The duplication stays. Its size, its cause, and the
  fact that the layer rule requires it are recorded here as evidence about the architecture,
  which is what P0 exists to produce. B5's add-on half is repaired by extending the tests to
  every add-on rather than by removing the duplicate code — notably the credential-literal
  scan, which `[측정]` covers two of three collectors and leaves `collector.naver.blog`
  scanned by nothing.
- **C — narrow the unverifiable judgments.** Where an add-on makes a decision no layer can
  check, require it to *report* the decision, and make an unreported decision a refusal
  rather than a silent success. This does not move the judgment to the platform; it makes the
  absence of a judgment detectable.

`[추론]` Restructuring was rejected because it would convert the question P0 is meant to
answer — what the layer rule costs — into a settled fact, discarding the most expensive
evidence a disposable prototype can produce. This is a decision to keep measuring, not a
decision that the duplication is good.

`[결정]` Reinforced 2026-08-19 by [OQ-014](OQ-014-externalized-acquisition.md). With the
add-on layer's intended disposition now concrete — a thin reader over a boundary rather than
a place where source-specific acquisition lives — removing the duplication would be work
spent on code the target architecture replaces. `[추론]` Clause C is the opposite case: the
mechanism that makes an add-on report a judgment nothing can check is the same mechanism a
boundary contract needs, so it is the one part of this question worth building now. P0
remains an experiment stage; neither clause authorises building the target.

## Exit condition

The team can state whether an add-on may import anything but the contract, at what contract
version any shared layer lands, and what the platform does when an add-on-only judgment is
not reported. The B5 GREEN clauses are each classified as test-placement or contract gap.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution requires a Decision Packet,
and a `CONTRACT_VERSION` rise if the add-on contract gains a declaration or a shared layer.
