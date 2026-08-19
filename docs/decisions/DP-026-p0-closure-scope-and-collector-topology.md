# DP-026 — What ends P0, and where a collector lives

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-20
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-20)` — six questions put and answered before any of this was applied
- Amends: [DP-011](DP-011-p0b-product-and-delivery-scope.md) (delivery boundary), [DP-012](DP-012-independent-scraper-services.md) (which collectors the adapter pattern binds)
- Related Open Questions: [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md), [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) — closed by DP-012
- Affected contracts: `PoC Contract 0.1` §1, `CONTRACT-ADDON@1.3`
- Affected acceptance tests: none directly; changes what the P1 Entry Gate measures against

## Decision question

P0 is a disposable Architecture Discovery Prototype and P1 is a clean reconstruction from
accepted contracts. Ending P0 means holding the P1 Entry Gate, archiving by Git tag, and
merging to `main`. Three things blocked stating what "ending" means:

1. **Which standard ends P0?** `p0-charter.md`'s P0-B exit criteria contain no evidence
   card, no sunscreen/toner canonicalization, and no trend class. [DP-011](DP-011-p0b-product-and-delivery-scope.md)
   added all three on top of the charter, with a 2026-08-26 functional freeze.
2. **Does the NAVER acquisition move out?** DP-012 selects independent scraper services
   with a thin COSMAI adapter, and says the direct prototype "is evidence and reference
   code **until its P0 disposition is recorded**".
3. **Where do the external services run?** The answer changes whether the adapter is
   reachable at all.

## Candidates

1. Close P0 against the charter; move DP-011's product scope to P1.
2. Deliver DP-011's product scope inside P0-B by the 2026-08-26 freeze, then gate.
3. Prove one minimal card path in P0 and defer the rest.

## Evidence

`[확인 사실]` `p0-charter.md:131` lists twelve P0-B exit criteria. None mentions a card, a
trend class, or a product category. The charter's required flow (`:55`) has fourteen items
and item 7 asks for "one deterministic `rule-baseline@0.1` normalizer" — a normalizer, not a
product surface.

`[측정]` None of DP-011's product scope exists: no rule baseline, no trend evaluator, no
card, no product/ingredient/topic identity. Six days remained to the freeze when this was
decided.

`[측정]` [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) measured what
relocating acquisition buys: the three collectors are 235–292 lines each, 13–15% of it
source-independent plumbing, so **roughly 250 source-specific lines per source move rather
than disappear**. Two DataLab collectors share 165 identical lines.

`[측정]` The actually-exercised `CollectContext` surface across all four add-ons is six
members — `config_field`, `fetch`, `emit_raw`, `advance_cursor`, `log`, `cursor`. What makes
the NAVER handlers large is per-API body composition, enum and range validation the config
schema cannot express, status maps, nested-response unrolling, and hand-rolled date
arithmetic. All of that is what would move outward.

`[확인 사실]` The external collection services already exist and run on a **private network
or the same machine**. `domain/outbound.py` permits only `https` and
`check_resolved_addresses` refuses loopback, private, link-local, multicast, reserved, and
unspecified ranges — every resolved address must pass. `allow_loopback` covers loopback
alone and not RFC1918. **No adapter can reach them today.**

## Decision

`[결정]` **D1 — P0 closes against the charter.** The P1 Entry Gate measures
`p0-charter.md`'s P0-B exit criteria and its eight Architecture Questions. DP-011's product
scope — opportunity card, sunscreen and toner canonicalization, deterministic trend classes
— and its 2026-08-26 freeze move to **P1's first milestone**. P0's mission in `AGENTS.md` is
to "build evidence that allows the team to choose the architecture"; producing a product
decision is not that mission, and a gate that accepted an unbuilt product scope would be
recording a pass nothing supports.

`[결정]` **D2 — DP-012's topology binds new collectors, not the existing three.** The NAVER
collectors keep calling the source directly and receive `ARCHIVE_REFERENCE_ONLY`. This *is*
the P0 disposition DP-012 said it was waiting for, recorded rather than left implicit.
Collectors added from here — which already run as independent services — are integrated as
thin REST adapter add-ons under DP-012's read contract. The resulting architecture is a
**hybrid**, deliberately.

`[결정]` **D3 — The hybrid's cost is that P1 carries both seams.** A direct collector needs
the full outbound guard: host and path range, redirect revalidation, address range checks,
deadline, byte and page bounds. An adapter needs a narrower version of the same guard plus a
boundary read contract. P1 maintains **both**, so the add-on surface does not shrink — it
grows. This is the opposite of "keep only a minimal API contract in the add-on", and the
decision is taken with that stated rather than discovered later.

`[결정]` **D4 — Private-network egress is a P1 precondition, not a gate condition.** Since
the existing collectors are unchanged, nothing in P0 needs to reach a private address. The
policy change is a `SEC`-class decision and gets its own packet before P1 writes an adapter.
It does not block this gate.

## Rejected alternatives

- **Candidate 2 (deliver the product scope by 08-26).** Rejected: none of it exists, six
  days remained, and the execution plan's own stop rule says "an explicit blocker is
  preferable to an unsupported pass". Attempting it would put the gate's honesty at risk to
  protect a date.
- **Candidate 3 (one minimal card).** Rejected: it verifies DP-011's H1 cheaply but reopens
  the scope question at the gate, which is where scope questions are most expensive.
- **Rebuilding the NAVER collectors as external services now.** Rejected: P0 is archived and
  imported by nothing, so rewriting working code inside it buys no P1 property that writing
  the adapter in P1 does not. OQ-014's measurement says the source-specific work relocates
  rather than shrinks, so the rewrite would not even be smaller.

## Tradeoffs and risks

- Benefits: the gate measures a standard that was written before the work and that the work
  can actually meet; the direction for new collectors is settled and recorded; no working
  code is discarded in a phase that is being archived.
- Costs: D3's two-seam surface; DP-011's product scope slips by however long P1 Phase 0
  takes; the delivery window's dated critical path is superseded.
- Failure modes: P1 builds the adapter and finds the boundary read contract underspecified,
  because P0 never exercised one. Nothing here measures it.
- Reversibility: D1 and D2 are recorded decisions a later packet can revise. D3 is a
  consequence, not a choice, and changes only if D2 does.

## Remaining uncertainty

- **`accept_status` has no exercised subject.** None of the four add-ons calls it. An
  external service's "not ready yet" is plausibly a `202` or `404`, so an adapter would be
  the first add-on to need it — and the first to find out whether the contract is right.
- **One cursor stream per add-on** ([OQ-010](../open-questions/OQ-010-cursor-stream-read-back.md),
  `OPEN`). An adapter paging an external result set gets a single watermark.
- **Authentication headers are limited to `PROTECTED_HEADERS`' seven names.** `x-api-key`
  fits an internal service; nothing checks that it is the right choice.
- Whether P0-B's evidence transfers to DP-011's product scope at all remains a P1 Entry Gate
  question, as [DP-025](DP-025-two-branch-record-reconciliation.md) already recorded.

## Required changes

- Project State: the closure standard, DP-011's scope as P1's first milestone, and the
  hybrid topology.
- Contract or schema: `PoC Contract 0.1` §1 names DP-012 and the hybrid rather than
  describing OQ-014 as an open risk; `P0-ARTIFACT-DISPOSITION` resolves `addon_host/`'s
  `UNRESOLVED` for the OQ-014 half and rescopes the `domain/` row, which keeps
  `outbound.py` and `transport.py` because a direct collector still needs them.
- Acceptance tests: none. The P1 Entry Gate measures charter criteria.
- Migration or compatibility: none.
- Implementation handoff: private-network egress gets its own `SEC`-class packet before any
  adapter is written. The P1 reconstruction plan's Phase 0.1 is rewritten against this
  packet instead of asking to resolve an already-resolved question.
