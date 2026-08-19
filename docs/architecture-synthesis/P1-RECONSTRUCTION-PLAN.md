# P1 Reconstruction Plan

- Status: `DRAFT_FOR_GATE`
- Date: 2026-08-19
- Governing: [P0 Charter](../p0-charter.md), [DP-001](../decisions/DP-001-p0-lifecycle.md), [DP-005](../decisions/DP-005-two-part-pre-p1-execution.md)
- Inputs: [Architecture Synthesis v0.1](architecture-synthesis-v0.1.md), [P0 Artifact Disposition](P0-ARTIFACT-DISPOSITION.md), [`PoC Contract 0.1`](../../contracts/experimental/POC-CONTRACT-0.1.md)

## What "reconstruction" means here

`[확인 사실]` `AGENTS.md`: *"P0 code must not become a runtime or package dependency of P1."*
P1 is written against `PoC Contract 0.1` and the promoted acceptance scenarios. P0 stays
readable at a Git tag and is imported by nothing.

`[추론]` The reason is not hygiene. P0 optimised for observability and experimental clarity
over maintainability, and it carries a waiver (`SEC-006`), a trusted-code boundary
(DP-008 D10), and two open questions about its own seam. Porting it would carry all four
across a line where three of them stop being acceptable.

## Sequencing

`[결정]` The order below is driven by what is *decided* rather than by what is easy. Two
questions can change what P1 builds, and both are cheap to answer relative to the cost of
building the wrong thing.

### Phase 0 — Answer what would change the build (before any P1 code)

| # | Work | Why first |
|---|---|---|
| 0.1 | **Resolve [OQ-014](../open-questions/OQ-014-externalized-acquisition.md)** — does acquisition leave the service? | It rewrites `PoC Contract 0.1` §1 and decides whether P1 has collectors at all or only readers. Its minimum experiment is measurement, not construction: run the three collectors at realistic cadence and record scheduling contention and distance from the rate limit. `[측정]` H1 — that the two cadences genuinely differ — is currently **assumed**. |
| 0.2 | **Resolve [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) clause C** — how is an add-on held to a judgment nothing can check? | The mechanism that makes a judgment reportable is the same mechanism OQ-014's boundary contract needs. Settling it inside the current shape produces the vocabulary the boundary would be written in. |
| 0.3 | **Satisfy `SEC-006`** — narrow the agent sandbox, or record a P1-scoped decision that is not a waiver | [DP-023](../decisions/DP-023-sec-006-waived-for-p0.md) expires at the P1 Entry Gate. P1 runs against real sources and is not disposable. |
| 0.4 | ~~Write the add-on contract as a document~~ — **done 2026-08-19**, [`CONTRACT-ADDON-1.3.md`](../../contracts/experimental/CONTRACT-ADDON-1.3.md) | It existed only as code at `CONTRACT_VERSION = "1.3"`, and P1 cannot reconstruct from a package it is forbidden to import. |

`[결정]` **No P1 application code under `apps/` until Phase 0 closes and the P1 Entry Gate
accepts.** That is the charter's rule, and Phase 0 is what makes accepting it meaningful.

### Phase 1 — Rebuild the part that survived

| # | Work | Contract | Evidence it must reproduce |
|---|---|---|---|
| 1.1 | Job execution: table, lease, fence, effect key, correlation, error classification | [`CONTRACT-JOB-0.1`](../../contracts/experimental/CONTRACT-JOB-0.1.md) | JOB-001…008 |
| 1.2 | The completion-transaction boundary | `PoC Contract 0.1` §3 | A worker that lost its lease persists **neither** Raw nor cursor — proved at the store level, through an add-on, and across a killed process |
| 1.3 | Raw and provenance | §2 | The envelope is recorded before the add-on sees the bytes; payload is the bytes as read |
| 1.4 | Snapshot and verification | §4 | Tampering detected and *named*; an untampered control |
| 1.5 | Normalization, Schema 0.2 | §5 | Determinism; version coexistence; a rerun refused rather than doubled |

`[추론]` 1.1 and 1.2 are the highest-confidence items in the whole plan: reverting the F2
repair produces 91 failures and 111 errors, which is what a well-pinned boundary looks like.

### Phase 2 — Rebuild the part whose shape Phase 0 decided

| # | Work | Depends on |
|---|---|---|
| 2.1 | The acquisition seam — capability layer, or a boundary to an external service | 0.1, 0.2 |
| 2.2 | Outbound or input policy in whatever form 2.1 takes | 0.1, 0.3 |
| 2.3 | Credential resolution at the worker boundary | 0.3 |

`[측정]` **Budget for this being hard.** The outbound guard had four defects in one day — a
byte bound that counted elements, a write phase outside its own deadline, a dot-segment
redirect bypass, and a page limit enforced nowhere. Every one was found by an adversarial
review rather than by writing it carefully. `[결정]` P1 should plan an adversarial pass on
this component specifically, not as a general practice.

### Phase 3 — Operations

| # | Work | Contract |
|---|---|---|
| 3.1 | The four operator actions and their separation | §8 |
| 3.2 | Telemetry: transitions, error class and retryability, per-stage counters and durations | §8 |
| 3.3 | Redaction as a single point, with its key set pinned by contract | §8 |

`[결정]` Drop `claim_conflicts`. P0 recorded it as not a contention measure twice, once for
insensitivity and once for false positives.

### Phase 4 — Sources

| # | Work | Why last |
|---|---|---|
| 4.1 | Select a **real** dataset source and characterise it — [OQ-001](../open-questions/OQ-001-source-capability.md)'s open half | P0 substituted a self-authored file; the rights gate was never exercised a second time |
| 4.2 | Characterise rate limiting, deep pagination, redirects, and drift against a real provider | All four are `UNKNOWN` after P0 |
| 4.3 | Find a source that answers `200` with an error body, or record that the control has no subject | `accept_status` was built for a case no P0 source exhibits |

## What P1 must not reproduce

`[결정]` Carried verbatim from the synthesis so that this plan can be read alone:

1. `SEC-006` as a waiver.
2. Trusted in-process add-ons as the isolation boundary.
3. Selection records written after integration.
4. Digests taken after the rows were cleared.
5. Add-on judgments nothing can check.
6. Prose claims about controls, unverified by any test. **Nine instances in one session, none
   caught by the suite.** `[추론]` This is the failure shape P0's toolchain addressed least,
   and the one a reconstruction is most likely to repeat, because prose is the part that gets
   copied.

## Ownership and gates

- Phase 0 closes at the **P1 Entry Gate** ([template](P1-ENTRY-GATE-TEMPLATE.md)), which must
  accept the Architecture Synthesis, the disposition register, `PoC Contract 0.1`, and this
  plan.
- `main` moves only at accepted gates and Decision Packets.
- `[확인 사실]` One acceptance check is currently unmet: **the P0 archive tag does not exist**.
  Creating it is an operator action — this repository's convention is that commits, pushes,
  and tags happen when the owner asks.

## Estimate discipline

`[측정]` P0's one recorded timebox was **exceeded by ~24%** — a 2.5-hour box that ran 3h05m,
released by the owner rather than erased. `[결정]` This plan states no durations. The two
things it does state are the *order* and the *dependencies*, because those are what the
evidence supports; a schedule would be the kind of claim this project labels `[가설]` and
this one has no falsification condition attached.
