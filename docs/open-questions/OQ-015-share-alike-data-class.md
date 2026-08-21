# OQ-015 — Where share-alike-encumbered data sits in a three-class taxonomy

- Status: `OPEN`
- Priority: P1 — nothing in P0 publishes, so nothing in P0 triggers it
- Owner: Project team
- Owner decision: `CONFIRMED (Decision Packet)` — [DP-027](../decisions/DP-027-dataset-standard-and-share-alike.md) D4 decided not to answer this in P0 and to record it here instead
- Blocks: the first P1 artifact built on an ODbL source that leaves this organisation
- Related experiments: [`SRC-003`](../../experiments/source-probes/SRC-003-open-beauty-facts.md), open question 3
- Resolution Decision Packet: not created

## Question

`docs/conventions/data-handling.md` classifies every input as `public`, `local`, or
`private`. `[측정]` `SRC-003` found a case none of the three describes: Open Beauty Facts is
**redistributable, but only if everything downstream is published under the same terms**.

Which class does share-alike-encumbered data take, and does the taxonomy need a fourth?

## Why this cannot be decided yet

`[확인 사실]` The three classes answer *may this leave the machine*. ODbL asks a different
question — *what happens to everything derived from it when it does*. ODbL 1.0 §4.4 c and
§4.6 attach the share-alike obligation and the machine-readable-copy offer to the
**Derivative Database**, not to the import; §4.5 c puts internal use outside §4.4 entirely.
So the encumbrance is invisible until publication and total afterwards.

`[추론]` A class cannot be designed from one source. The taxonomy's other three each cover a
family — this would be a fourth defined by a single licence on a single candidate, and
`data-handling.md`'s own classes were derived from several. `[결정]` DP-027 D4: inventing a
fourth class at the end of a phase, on one source, is how a taxonomy acquires a category
nobody can apply.

`[확인 사실]` Nothing in P0 forces the question. P0 publishes no derived artifact, so OBF is
registered `local` — the conservative and reversible reading `naver-real-data/README.md`
already uses for a different reason.

## Scope

### Included

- Whether `public` / `local` / `private` gains a fourth class, gains a **flag orthogonal to
  the class**, or stays as it is with the obligation recorded per source.
- What the platform must refuse or warn about when an encumbered source's data reaches an
  export, a card, or a public surface.
- Whether the obligation is a property of the **source row**, of the **snapshot**, or of the
  **normalized result** — a normalized store mixing an encumbered source with an
  unencumbered one is the case that decides it.

### Excluded

- ODbL interpretation itself. `SRC-003` §"What the licence requires of derived output"
  settled that with citations and is not reopened here.
- Choosing a dataset. [DP-027](../decisions/DP-027-dataset-standard-and-share-alike.md) D2
  did that for P0.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: The obligation is orthogonal to the three classes and belongs on the source row as a flag, not as a fourth class. | A real source needs an encumbrance that changes whether the data may be *retrieved or processed at all*, which is what the classes decide — in which case it is not orthogonal. |
| H2: The obligation propagates with lineage, so a normalized result inherits the union of its sources' encumbrances. | Two sources' terms are mutually incompatible, so a store mixing them cannot be published under any single licence and the union is not a licence anyone can grant. |
| H3: The platform can refuse an encumbered publication mechanically, from the lineage it already stores. | Deciding whether an output is a "Produced Work" or a "Derivative Database" requires reading the output's meaning, which no stored lineage carries. |

## Alternatives

- **A fourth class, `share_alike`.** Explicit, and wrong if the property is orthogonal —
  a source can be `share_alike` and also carry personal data, and one field cannot say both.
- **A flag on the source row.** `[추론]` The most likely answer under H1, and the cheapest to
  add. It leaves "which of my snapshots are encumbered" as a join rather than a column.
- **Nothing in the platform; a recorded obligation per source.** What P0 does. Honest while
  nothing publishes, and it stops being honest the moment something does.
- **Refuse encumbered sources entirely.** Removes the question and most open data with it.

## Exit condition

A P1 artifact is about to be published from a store containing an encumbered source, and
the platform can say — from what it stores, not from a person's memory — that the artifact
carries an obligation and which one.

## Resolution

Not completed while status is `OPEN`. Resolution requires a Decision Packet.
