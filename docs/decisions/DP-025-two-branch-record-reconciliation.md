# DP-025 — Reconciling two decision records that grew from the same commit

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-20
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-20)` — three questions put and answered before any of this was applied
- Related Open Questions: [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) — closed by this reconciliation
- Affected contracts: none directly; the identifiers every contract cites
- Affected acceptance tests: none

## Decision question

`agent/operating-model` and the uncommitted P0-B domain work both grew from `c0a266d` and
both wrote into the decision record without seeing each other. They collide three ways:

1. **Identifiers.** Both claimed `DP-011`–`DP-014` and `OQ-011`, for different decisions.
2. **A question answered twice.** `DP-012` (independent scraper services, `ACCEPTED_FOR_POC`)
   and `OQ-014` (whether acquisition leaves this service, `OPEN`) are the same question, dated
   the same day, one decided and one open — with the measurement on the open side.
3. **A completion claim measured against a superseded plan.** `project-state.md` declared
   P0-B's work packages complete against the execution plan as it stood before `DP-011`
   redefined the P0-B product scope and its 2026-08-26 boundary.

Which side yields on each?

## Candidates

1. Renumber the published side; keep the domain branch's numbers.
2. Renumber the unpublished side; keep the published numbers.
3. Merge both and record the collisions as known duplicates.

## Evidence

`[확인 사실]` No commit at or before `c0a266d` references `DP-011`–`DP-017` or
`OQ-011`–`OQ-012`. Nothing already recorded had to move either way.

`[측정]` The published side carries **31 references inside eleven pushed commit messages**.
The unpublished side carried **447 references, all in files that were not yet history**.

`[확인 사실]` `AGENTS.md` makes commit messages part of the decision record and forbids
rebasing or squashing a shared branch. A published number can be changed in files but not in
the messages that introduced it.

`[추론]` The two costs are not the same kind. Renumbering the unpublished side is one pass
over text that no reader has yet cited. Renumbering the published side would leave eleven
merged messages permanently naming decisions that no longer carry those numbers — a
contradiction inside the record that is supposed to be the authority.

## Decision

`[결정]` **D1 — The published side keeps its numbers; the unpublished side moves by seven.**
`DP-011`–`DP-017` → `DP-018`–`DP-024`, `OQ-011` → `OQ-013`, `OQ-012` → `OQ-014`. The whole
block moved rather than only the four colliding numbers, so adoption order is preserved
inside the moved set.

`[결정]` **D2 — `OQ-014` closes against `DP-012` rather than competing with it.** Its
measurement — roughly 250 source-specific lines per collector relocate rather than disappear,
and 165 identical lines between two collectors — is carried into `DP-012` as falsification
input, together with the fact that `DP-012`'s H1 premise about cadence separation is
unmeasured. The decision stands; its confidence does not rise.

`[결정]` **D3 — The completion claim states its basis.** `project-state.md` says P0-B is
complete *against the pre-`DP-011` plan*, and lists `DP-011`/`DP-012`'s scope — opportunity
card, sunscreen and toner canonicalization, deterministic trend baseline, scraper-service
adapter — as not started. Existing B0–B4 evidence is neither withdrawn nor promoted.

## Rejected alternatives

- **Renumber the published side.** Rejected: it buys tidier numbers at the price of a
  permanent contradiction between merged commit messages and the files they describe.
- **Merge both and record the duplicates.** Rejected: two live meanings for `DP-011` makes
  every citation in contracts, code comments, and reviews ambiguous, and the ambiguity grows
  with each new reference rather than staying fixed.
- **Withdraw the P0-B completion claim entirely.** Rejected: `DP-011` does not falsify the
  B0–B4 evidence, and blurring what was measured to express what was not yet started would
  lose both.

## Tradeoffs and risks

- Benefits: one meaning per identifier; one record per question; a completion claim a gate
  can read without knowing which plan it was measured against.
- Costs: the P0-B packets carry numbers seven higher than the order they were written in, and
  any external note written against the old numbers is now stale.
- Failure modes: a reference to an old number surviving somewhere unscanned. Checked —
  zero occurrences of `DP-011`–`DP-017` or `OQ-011`–`OQ-012` in their P0-B meaning remain,
  and every relative link in the repository's Markdown resolves.
- Reversibility: high for D1 and D3. D2 is reversible only by reopening `OQ-014`, which would
  require new evidence rather than a preference.

## Remaining uncertainty

- `DP-012`'s H1 — whether separating acquisition from consumption removes real pressure — is
  still unmeasured, and this packet does not measure it.
- Whether the P0-B evidence transfers to `DP-011`'s product scope at all is a P1 Entry Gate
  question, not one this reconciliation answers.

## Required changes

- Project State: version 0.9; the completion basis and the not-started scope table.
- Contract or schema: none. `CONTRACT-ADDON@1.3` cites the moved numbers and was updated.
- Acceptance tests: none. 1220 passed, 14 skipped after the renumbering.
- Migration or compatibility: none.
- Implementation handoff: the outbound approved-range defect found while evaluating this work
  is repaired separately on the same branch; it is not part of this decision.
