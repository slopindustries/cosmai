# DP-029 — What a P1 snapshot is, and which member wins when two observations collide

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-21
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-21, brainstorming session — docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md)`
- Related Open Questions: [OQ-004](../open-questions/OQ-004-snapshot-boundary.md) — resolved for P1 by this packet
- Affected contracts: [`PoC Contract 0.1`](../../contracts/experimental/POC-CONTRACT-0.1.md) §4 Snapshot
- Affected acceptance tests: none yet — implementation is M2 (see Required changes)

## Decision question

OQ-004 asks what exact data and metadata a sealed snapshot must materialize so a
normalization run can distrust future Raw-store state and still replay its original input.
P0-B answered part of this by measurement: a materialized snapshot survives a Raw purge that
a reference design does not. It left two further gaps open at the same boundary — which
observation wins when two rows share one `item_key`, and whether a manifest's identity is
independent of the reading cluster's collation — and both were carried unfixed into
[`P1-INHERITED-DEFECTS.md`](../architecture-synthesis/P1-INHERITED-DEFECTS.md) §5. This
packet decides P1's answer to all three, plus what P1 does about the copy a materialized
snapshot creates once an erasure obligation exists.

## Candidates

**Materialization (does a snapshot copy bytes or reference them):**

1. Materialized: member bytes copied into snapshot storage at seal time.
2. Reference: ordinals and row ids fixed at seal, bytes fetched from `raw_item` at read time.

**Same-`item_key` tie-break (which observation wins when two rows are sealed together):**

1. An explicit, monotonically increasing `bigint` sequence on `raw_item`; the maximum-sequence
   row wins.
2. `observed_at`, a source-stated observation time.
3. Status quo: `emitted_at` (transaction timestamp) with an unstated `uuid4` fallback on ties.

**Manifest member ordering (what "ordered by `item_key`" means across clusters):**

1. UTF-8 bytewise comparison, fixed regardless of column or database collation.
2. Leave the collation unfixed, as DP-019 D5 currently does.

**Erasure obligation (what a materialized snapshot owes a future deletion request):**

1. Design and implement a P1 deletion path across `raw_item`, `snapshot_item`, and
   `raw_envelope` together, now.
2. Route the obligation to the security recommendations register as an unimplemented,
   explicitly-scoped gap.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: A materialized snapshot is sufficient for replay across Raw-store evolution, including a purge, where a reference design is not. | An unmodified materialized snapshot fails to reproduce identical verified input after the Raw rows it drew from are deleted, or a reference design succeeds at the same step. |
| H2: An explicit sequence resolves a same-key tie without depending on how writes are grouped into transactions. | Two observations of one key, sealed with the sequence populated, select different members depending on whether the writes share one transaction or two. |
| H3: A fixed bytewise manifest ordering is independent of database or column collation. | Two clusters with different `item_key` collations, given identical Raw rows, produce different manifest digests under the bytewise rule. |

## Experiment

- Scope: OQ-004's own minimum experiment — TASK-005's Raw-store-evolution timeline (seal →
  additive migration → later collection superseding a sealed key → purge of every Raw row)
  and TASK-007/TASK-010's two-import tie-break scenario on real data — both already run in
  P0-B. This packet runs no new experiment; it reads and decides from that record.
- Environment and versions: P0-B development PostgreSQL cluster, `initdb --locale=C`; real
  Open Beauty Facts delta rows (TASK-007/TASK-010).
- Input and fixture identity: TASK-005's four-step Raw timeline; two OBF delta imports 59 ms
  apart, and the same two imports forced to equal `emitted_at` and re-sealed 12 times
  (TASK-007/TASK-010); a collation-only column alteration
  (`alter column item_key type text collate "und-x-icu"`) with no value changed
  (`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-D).
- Procedure: as recorded in OQ-004's "What P0-B measured" section and
  `P1-INHERITED-DEFECTS.md` §5.
- Known limitations: all cited measurements are about P0's implementation. This packet
  decides what P1 must reproduce; it does not claim P1's rebuilt `domain` module has been
  measured against these conditions yet.

## Evidence

`[측정]` TASK-005 drove a materialized sealed snapshot and a read-time re-query of
`raw_item` over one Raw timeline — at the seal, after an additive migration, after a later
collection superseding a sealed key, and after a purge of every Raw row. The sealed snapshot
replayed byte-identically at all four steps; the re-query design diverged at step three and
returned nothing at step four.

`[측정]` Against OQ-004's own first alternative — a reference design fixing ordinals and row
ids at seal but fetching bytes at read — `ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-B
found it agrees with the materialized design at the seal, after the migration, and after the
later collection. Only the purge separates them: the reference design returns nothing once
its referenced rows are gone; the materialized one still replays.

`[측정]` On real Open Beauty Facts rows
([TASK-007/TASK-010](../agent-workflow/task-packets/TASK-010-obf-real-snapshot-normalized.md),
`ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md` F2): two imports 59 ms apart produced
distinct `emitted_at` values, `emitted_at desc` decided the tie, and all three overlapping
members were byte-identical to the later delta's lines — the known `uuid4` tie-break was
checked and did not produce this result. Forcing the two `emitted_at` values equal and
re-sealing 12 times dropped the decision to `id desc` on a `uuid4`, and **2 of the 3 keys
then selected the older payload.**

`[확인 사실]` `emitted_at` defaults to `now()`, which in PostgreSQL is the **transaction**
timestamp, not the statement's. So "the later import wins" holds per import transaction, not
per row, and nothing in DP-019 D5 or the tests states that two imports must be separate
transactions — a batching change could make member selection non-deterministic without any
test noticing.

`[확인 사실]` [DP-019](DP-019-normalized-schema-0-1-and-results.md) D5 orders manifest
members by `item_key` and fixes no collation.
`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT-R2.md` F-D found that changing only the column's
collation reorders every member a read-time selection returns, on a development cluster that
is `initdb --locale=C`. Real `item_key`s are URLs and `f"{title}|{period}"`, so this is where
a collation bites rather than a theoretical concern.

`[측정]` A purge of `raw_item` does not discharge an erasure obligation: `snapshot_item`
still holds the bytes and still verifies, and `raw_envelope` — the lossless original the
items were carved from — is untouched. Deleting one table leaves two further copies.

## Decision

`[결정]` **D1 — A P1 snapshot is materialized.** At seal time, member bytes are copied into
the snapshot's own storage rather than referenced from `raw_item`. Basis: TASK-005's
four-step replay measurement — the materialized design is the only one of the two tested
that replays byte-identically at every step, including after a purge; the reference design
this question names is narrower, matching the materialized design only through step three.

`[결정]` **D2 — A same-`item_key` tie is broken by an explicit, monotonically increasing
`bigint` sequence on `raw_item`, selecting the maximum-sequence row.** Basis: `emitted_at` is
a transaction timestamp rather than a per-row ordering, and ties forced onto the fallback
`uuid4` selected the older payload in 2 of 3 keys across 12 re-seals. This repairs
`P1-INHERITED-DEFECTS.md` §5(a).

`[결정]` **D3 — A manifest orders its members by UTF-8 bytewise comparison of `item_key`,
independent of any column or database collation.** Basis: DP-019 D5 left the ordering
collation unspecified, and a collation-only change — no value altered — reordered a manifest
and changed its digest on identical Raw. This repairs §5(b). It narrows DP-019 D5's ordering
rule; it does not reverse it — D5's "ordered by `item_key`" stands, and this packet fixes
only which comparison "ordered by" means.

`[결정]` **D4 — The erasure obligation stays undesigned in P1's initial contract and is
routed to [`SR-003`](../conventions/security-recommendations.md) in the security
recommendations register.** A materialized snapshot (D1) creates a second full copy of
member bytes beyond `raw_item`, and `raw_envelope` is a third; nothing in this packet's scope
deletes all three together, and reporting a `raw_item` delete alone as "erasure" would
overstate what P1 does.

## Rejected alternatives

- **Reference design (materialization candidate 2).** Rejected: TASK-005's own measurement
  falsifies it at the purge step, which is exactly the Raw-store-evolution case OQ-004's
  minimum experiment asked for.
- **`observed_at`-priority tie-break.** Rejected in the 2026-08-21 session: it would require
  every source to carry a comparable, source-stated observation-time field, which is a
  per-source contract obligation this packet is not prepared to impose project-wide.
- **Leaving the manifest collation unfixed.** Rejected: the repair costs nothing — pinning a
  comparison function, not a schema change — and DP-019 D5's own falsification table already
  names a locale-dependent result as the failure this packet found. Leaving a zero-cost fix
  undone has no stated benefit.

## Tradeoffs and risks

- Benefits: snapshot identity becomes reproducible across the two gaps P0-B measured — a
  same-key tie no longer depends on transaction batching, and a manifest digest no longer
  depends on which cluster's collation sealed it.
- Costs: materialization keeps the storage cost D1 was chosen despite — a snapshot duplicates
  member bytes rather than referencing them, and D4 leaves that duplication's cleanup path
  unbuilt.
- Failure modes: a reader could take D4's registration in `SR-003` as meaning P1 already
  deletes on request. `SR-003`'s "부재가 의미하는 것" column exists precisely to prevent that
  reading, and this packet does not weaken it.
- Reversibility: D2 and D3 are additive schema and ordering changes and are cheap to revisit.
  D1 is more structural — moving off materialization later means re-answering the purge case
  OQ-004 tested.

## Remaining uncertainty

- This decision does not cover a future rights-holder deletion request, nor the disposition
  question at the point of external publication
  ([OQ-015](../open-questions/OQ-015-share-alike-data-class.md)) — both stay with `SR-003`
  until a P1 packet designs the erasure path across `snapshot_item` and `raw_envelope`
  together.
- D1–D3 are evaluated against P0's implementation. Nothing here re-measures them against
  P1's rebuilt `domain` module; the Required changes below list what P1 must build to
  inherit the tested behavior rather than only the decision.

## Required changes

- Project State: mark [OQ-004](../open-questions/OQ-004-snapshot-boundary.md) `RESOLVED` and
  record this packet in §4 Accepted for P0.
- Contract or schema: `PoC Contract 0.1` §4 Snapshot should gain the tie-break and
  manifest-ordering rules explicitly in its next revision, where it currently states only
  "ordered by `(item_key)`" without a collation.
- Acceptance tests: none by this packet; sealed-snapshot tests covering D2 and D3 are M2
  implementation work.
- Migration or compatibility: `raw_item.seq bigint generated always as identity` (M2 domain
  migration); manifest-building code pinned to bytewise comparison.
- Implementation handoff: sealed-snapshot implementation using the sequence and bytewise
  ordering (M2); `SR-003`'s erasure path stays a registered, unimplemented candidate until a
  future packet designs it.
