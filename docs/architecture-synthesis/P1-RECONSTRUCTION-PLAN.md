# P1 Reconstruction Plan

- Status: `DRAFT_FOR_GATE`
- Date: 2026-08-19
- Governing: [P0 Charter](../p0-charter.md), [DP-001](../decisions/DP-001-p0-lifecycle.md), [DP-005](../decisions/DP-005-two-part-pre-p1-execution.md)
- Inputs: [Architecture Synthesis v0.1](architecture-synthesis-v0.1.md), [P0 Artifact Disposition](P0-ARTIFACT-DISPOSITION.md), [`PoC Contract 0.1`](../../contracts/experimental/POC-CONTRACT-0.1.md)
- Updated 2026-08-21 from the owner's selection criteria (spec:
  [`2026-08-21-p1-reconstruction-design.md`](../superpowers/specs/2026-08-21-p1-reconstruction-design.md))
  and [DP-029](../decisions/DP-029-p1-snapshot-identity.md) through
  [DP-034](../decisions/DP-034-p1-credential-entry.md).

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

`[결정]` **Phase 0 closure, 2026-08-21, item by item** — added without changing the table
above, which stays as the original record of why each item was first:

- **0.1** — [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) is `RESOLVED`.
  [DP-012](../decisions/DP-012-independent-scraper-services.md) answered it, accepted the same
  day on another branch; [DP-026](../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
  D2 bound that answer to collectors added after P0's closure; and
  [DP-031](../decisions/DP-031-p1-collector-topology.md) narrows DP-026 D2 for P1: a source
  judged light (NAVER) collects in-process, and only a heavy periodic source (trend-radar,
  tubedepth) keeps the external-service-plus-adapter shape.
- **0.2** — [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) clause C stays
  `OPEN` and is **not** resolved by this update; P1 carries it forward rather than closing it.
  `CONTRACT-ADDON-1.3.md` already states the same silence OQ-013's interim position (A + C)
  recorded — "Judgments only an add-on can make are checked by nothing" — and P1 reconstructs
  that text as written. This item is reopened only if a falsification condition in OQ-013's own
  hypothesis table is met during M3/M4 implementation, not on a schedule.
- **0.3** — Phase 0.3 is closed by its second branch: a P1-scoped decision that is not a waiver.
  [DP-034](../decisions/DP-034-p1-credential-entry.md) D3 moves `SEC-006`, off DP-023's expiring
  waiver, into [`security-recommendations.md`](../conventions/security-recommendations.md)
  `SR-005` as an independent, P1-scoped decision that the waiver does not extend — exactly the
  "record a P1-scoped decision that is not a waiver" branch this row named. `[확인 사실]`
  `SEC-006` itself remains unimplemented and registered as `SR-005`, not satisfied; an earlier
  revision of this row said "`SEC-006` is satisfied," which this correction repairs.
- **0.4** — unchanged from the 2026-08-19 record in the table above: done.

### M1–M7 — 2026-08-21, replacing Phases 1–4 below

`[결정]` The owner's selection criteria (`plan.md`, formalized in
[the reconstruction spec](../superpowers/specs/2026-08-21-p1-reconstruction-design.md) §9)
replace this plan's Phase 1–4 structure with seven build milestones. Phase 0 above is
unchanged by this — it is not part of what these milestones replace. The Phase 1–4 tables
below stay as the original record; each now carries a one-line pointer to where its work
landed.

| Milestone | Work | Parallelization |
|---|---|---|
| M1 | `platform_core`, plus DB provisioning and migration on the shared PostgreSQL server ([DP-032](../decisions/DP-032-p1-database-placement.md)) | — |
| M2 | `domain`, including DP-029's three changes: materialized snapshots (D1), the `raw_item.seq` tie-break (D2), and bytewise manifest ordering (D3); and [DP-030](../decisions/DP-030-p1-normalization-scope.md)'s schema/envelope carry-forward (D4) and per-record fault-tolerance error contract (D2 — the `notes`/`normalize_error` shape), which land in `domain`'s data model here even though each normalizer's own fallback is M4 work | after M1 |
| M3 | `addon_api`, `addon_host`, `addon_kit`, plus the conformance suite, against [`CONTRACT-ADDON-1.3.md`](../../contracts/experimental/CONTRACT-ADDON-1.3.md) and [DP-008](../decisions/DP-008-addon-architecture.md); [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) clause C is carried open here, not resolved | partial parallel with M2 |
| M4 | four collector add-ons — `collector.naver.blog`, one or two NAVER DataLab collectors (`[확인 사실]` count honestly stated as one or two — [DP-031](../decisions/DP-031-p1-collector-topology.md) D2 leaves it to the implementer), `collector.trendradar.rest`, and `collector.tubedepth.rest` (the latter two are the thin REST adapters DP-031 D3 fixes under DP-012's read contract) — plus one importer (`importer.local.jsonl`) plus three normalizers rebuilt at Schema 0.3 (`document`, `trend_point`, `product`), each implementing [DP-030](../decisions/DP-030-p1-normalization-scope.md) D2's per-record fallback | worktree-parallel, one per add-on |
| M5 | dashboard: six screens, on MUI, React Router, and TanStack Query ([DP-033](../decisions/DP-033-p1-operator-surface.md) D1, D4) | parallel with backend from M2 |
| M6 | scheduler and streaming downloads ([DP-033](../decisions/DP-033-p1-operator-surface.md) D3, D5) | parallel with M4 and M5 |
| M7 | integrated demonstration, an issue/PR consistency check, merge to `main`, `v0.1.0` tag, against [the reconstruction spec](../superpowers/specs/2026-08-21-p1-reconstruction-design.md) §9, this gate's own record, and [DP-026](../decisions/DP-026-p0-closure-scope-and-collector-topology.md)'s closure scope | serial |

`[확인 사실]` An earlier revision of the M4 row said "five add-ons," which was internally inconsistent with the one-or-two NAVER DataLab count it also named ("five *or six*"), and no milestone row named a normalizer at all despite the spec requiring three rebuilt (`spec:199-201`) and DP-030:216 assigning its central contract requirement to "M4's normalizer add-ons." This repair names the normalizer count explicitly and gives M2, M3, and M7 the contract or Decision Packet references isolation check 2 below requires.

`[결정]` Correspondence to the phases this replaces: **Phase 1 → M1, M2**. **Phase 2 → M3,
M4.** **Phase 3 → M5, M6.** **Phase 4 is absorbed into M4** — the two adapters and the
rebuilt NAVER collectors are where a real REST source and real dataset behavior are next
exercised, which is what Phase 4 asked for; it is not a separate milestone under this
replacement.

`[결정]` [`P1-INHERITED-DEFECTS.md`](P1-INHERITED-DEFECTS.md) becomes P1 requirements in two
places this plan now names explicitly, and stays a reproduction-forbidden reference for the
rest:

- §1 (one malformed row aborts a normalize run) is repaired as a contract requirement by
  [DP-030](../decisions/DP-030-p1-normalization-scope.md) D2 — missing-value substitution plus
  a per-record `normalize_error` note, run continues. Implementation is M4 (each normalizer's
  fallback) together with wherever `domain.store.canonical_body`'s successor and the host's
  `_NormalizeRun.execute` land (M2/M3) — the finding was platform-level, not add-on-level, and
  the repair must be too.
- §5 (same-`item_key` tie-break decided by a transaction timestamp; manifest ordering
  collation-dependent) is repaired as a contract requirement by
  [DP-029](../decisions/DP-029-p1-snapshot-identity.md) D2 (the `raw_item.seq` sequence) and D3
  (bytewise manifest ordering). Implementation is M2.
- §2 (rule-baseline's six stated gaps — moot, since `normalizer.rule.baseline` is not carried
  forward per DP-030 D3), §3–§4 (`normalizer.obf.product` and the dataset evidence record's
  weak assertions), §6 (zero Korean sunscreen/toner rows), §7 (contract and harness gaps), and
  §8 (paths P0 never tested) are **not** resolved by this plan. They are what M1–M7 must not
  reproduce, each checked at the milestone that rebuilds the code they were found in — not a
  repair queue this plan schedules.

### Phase 1 — Rebuild the part that survived

`[확인 사실]` Superseded 2026-08-21 by **M1, M2** above; retained here as the original record,
which M1–M2 inherit rather than restate.

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

`[확인 사실]` Superseded 2026-08-21 by **M3, M4** above; retained here as the original record.
Phase 0's own resolutions (0.1, 0.3) are recorded above, not repeated in this table's
"Depends on" column.

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

`[확인 사실]` Superseded 2026-08-21 by **M5, M6** above; retained here as the original record.
[DP-033](../decisions/DP-033-p1-operator-surface.md) widens 3.1's four operator actions to six
screens and adds Raw read access; 3.3's redaction-as-a-single-point stays unchanged.

| # | Work | Contract |
|---|---|---|
| 3.1 | The four operator actions and their separation | §8 |
| 3.2 | Telemetry: transitions, error class and retryability, per-stage counters and durations | §8 |
| 3.3 | Redaction as a single point, with its key set pinned by contract | §8 |

`[결정]` Drop `claim_conflicts`. P0 recorded it as not a contention measure twice, once for
insensitivity and once for false positives.

### Phase 4 — Sources

`[확인 사실]` Superseded 2026-08-21 by absorption into **M4** above; retained here as the
original record. 4.1's "select a real dataset source" is already answered by
[DP-027](../decisions/DP-027-dataset-standard-and-share-alike.md) (Open Beauty Facts); 4.2 and
4.3 are what `collector.trendradar.rest` and `collector.tubedepth.rest` exercise against real
running services for the first time.

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

`[결정]` **Adversarial review by milestone, 2026-08-21** — named because these are exactly the
components P0 measured defects in, per `docs/agent-workflow/README.md`'s worker/attacker
separation, applied per milestone rather than only at M7:

- **M2 owns the snapshot-seal review** — item 4 above, plus
  [DP-029](../decisions/DP-029-p1-snapshot-identity.md) D2's sequence tie-break and D3's
  bytewise manifest ordering, the two repairs `P1-INHERITED-DEFECTS.md` §5 named.
- **M4 owns the outbound-guard review** — item 1 above's enforcement level, now
  [`SR-001`](../conventions/security-recommendations.md) and
  [`SR-004`](../conventions/security-recommendations.md), plus the narrower guard the two
  adapters need under [DP-031](../decisions/DP-031-p1-collector-topology.md) D4 (REST-only
  exchange, no scraper-database read).
- **M1 and M5 jointly own the secret-path review** —
  [DP-034](../decisions/DP-034-p1-credential-entry.md) D1–D2's write-only credential entry: the
  API write endpoint at M1, the dashboard's collector-domain credential field at M5. The
  falsification condition is DP-034's own H1: any response body, log line, or error message
  found to carry a plaintext credential value rather than a `credential_ref` name.

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
