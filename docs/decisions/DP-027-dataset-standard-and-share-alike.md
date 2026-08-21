# DP-027 — What the charter's "one dataset" asks for, and what ODbL asks back

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-20
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-20)` — the question was put with the measurement in hand and with the alternative that keeps the stricter reading
- Extends: [DP-026](DP-026-p0-closure-scope-and-collector-topology.md) D1, which moved DP-011's product scope to P1 without saying what that leaves the dataset check measuring
- Related Open Questions: [OQ-001](../open-questions/OQ-001-source-capability.md) — its dataset half, [OQ-015](../open-questions/OQ-015-share-alike-data-class.md) — opened by this packet
- Affected contracts: [`PoC Contract 0.1`](../../contracts/experimental/POC-CONTRACT-0.1.md) §Provenance and security
- Affected acceptance tests: none

## Decision question

[TASK-002](../agent-workflow/task-packets/TASK-002-real-dataset-source-probe.md) profiled
both named dataset candidates and returned `NO-GO` on both. Its worker then flagged the
assumption that could invert its own result:

> **If the intended reading is that any real external dataset closes the charter's dataset
> half regardless of category, `SRC-003` is a `CONDITIONAL GO` and this packet answered the
> wrong question.**

So: does `p0-charter.md`'s *"One REST source and **one dataset** complete the end-to-end
flow"* bind on **category**, or only on the dataset being real?

## Candidates

1. Category-independent. Any real external dataset closes the charter's half.
2. Category-bound. Both candidates stay `NO-GO`; find a third.
3. Open Beauty Facts restricted to sunscreens worldwide, dropping the country filter.

## Evidence

`[측정]` Independently reproduced by the orchestrator against the live API on 2026-08-20,
after the worker reported them:

| Filter | `count` |
|---|---|
| `countries_tags_en=south-korea` | 36 |
| `countries_tags_en=south-korea&categories_tags_en=sunscreen` | **0** |
| `countries_tags_en=south-korea&categories_tags_en=toner` | **0** |
| `categories_tags_en=sunscreen` | 579 |

`[확인 사실]` The charter's exit criteria and its eight Architecture Questions mention no
product category. The nearest question is *"Can one Raw envelope preserve both REST and
dataset inputs without semantic loss?"* — a question about **shape**, not about subject.
Sunscreen and toner enter through [DP-011](DP-011-p0b-product-and-delivery-scope.md), and
[DP-026](DP-026-p0-closure-scope-and-collector-topology.md) D1 moved DP-011's scope to P1.

`[추론]` The category check therefore stopped binding on P0 the moment DP-026 was accepted.
The B1 candidate table still reads against "the selected card" because it predates DP-026,
not because the charter requires it.

`[측정]` The worker tested row identity in a way that could fail rather than in a way that
would pass. A plain repeat capture 36 minutes apart returned byte-identical results with
nothing edited — no information. It then resolved 121 delta-export products against the live
API 23 hours later: 121/121 resolved, 121/121 `created_t` identical, and **3 with `rev` and
`last_modified_t` advanced under an unchanged `code`** — one from rev 2 to rev 12. Identity
survives real content change, measured rather than asserted.

`[확인 사실]` ODbL 1.0 §4.5 c: *"Use of a Derivative Database internally within an
organisation is not to the public and therefore does not fall under the requirements of
Section 4.4."* The share-alike obligation, the attribution notice, and the
machine-readable-copy offer all attach on **publication**, not on import.

## Decision

`[결정]` **D1 — The charter's dataset half is category-independent.** It asks for one real
external dataset completing the end-to-end flow: rights recorded, Raw lossless, replay
idempotent, snapshot sealed, normalization versioned. What the rows are *about* is DP-011's
question and DP-011 is P1's.

`[추론]` The reading is not merely permissive; it is the one that makes the charter's own
question answerable. Open Beauty Facts product rows are a *further* shape from NAVER blog
documents and DataLab trend points than a Korean cosmetics dataset would be, so they test
"one Raw envelope without semantic loss" harder, not more softly.

`[결정]` **D2 — Open Beauty Facts is `CONDITIONAL GO` and is P0's dataset source.** The
conditions are the ones `SRC-003` measured and they are recorded, not waived:

- **Zero Korean sunscreen and zero Korean toner rows.** P0 gains no product-relevant
  evidence from this source, and no gate claim may imply otherwise.
- **Ingredient completeness is 26.5% database-wide.** No threshold exists in this repository
  to judge that against, which is `SRC-003`'s open question 1.
- **The API silently ignores unknown query parameters**, returned an nginx HTML 500 on a
  query it had already answered twice, delivers a field as present-and-empty in one response
  and absent in the next, and its delta exports cannot express deletion. An importer is
  written against a source that behaves this way, not against a well-behaved one.

`[결정]` **D3 — P0 publishes nothing built from it, so no share-alike attaches.** ODbL §4.5 c
puts internal use outside §4.4 entirely. `[결정]` This is a **constraint P1 inherits, not a
problem P0 solved**: the first time a card, an export, or a public dashboard is built on OBF
data, the attribution notice, the ODbL licensing of the normalized store, and the
machine-readable-copy offer all attach at once. The P1 Entry Gate must carry this as an
inherited obligation rather than as a closed item.

`[결정]` **D4 — `data-handling.md` gains no new class in P0.** `public`, `local`, and
`private` have no slot for "redistributable, but only if you publish everything downstream",
which `SRC-003`'s open question 3 found. Inventing a fourth class at the end of a phase, on
one source, is how a taxonomy acquires a category nobody can apply. The gap becomes
[OQ-015](../open-questions/OQ-015-share-alike-data-class.md). OBF is registered `local` for
P0, which is the conservative and reversible reading `naver-real-data/README.md` already
uses.

## Rejected alternatives

- **Candidate 2, category-bound.** Rejected: it holds P0 to a standard DP-026 already moved
  to P1, and the plan's two named candidates are exhausted — so it buys a stricter gate at
  the price of an unbounded search, with the deadline paid by the search.
- **Candidate 3, sunscreens worldwide.** Rejected: it keeps the *appearance* of product
  relevance without the substance. 579 sunscreens with no Korean rows is not closer to
  DP-011's market than 73,464 products are; it is the same distance with a filter on top,
  and a filter that suggests relevance it does not have is worse than no filter.

## Tradeoffs and risks

- Benefits: the charter's dataset half closes on measured evidence; the Raw envelope
  hypothesis gets a genuinely different input shape; the deadline survives.
- Costs: P0 ends with **no product-relevant dataset evidence at all**, and P1 starts its
  source selection from scratch for the product question.
- Failure modes: a gate reader takes "the dataset half is closed" to mean the dataset is
  useful for the product. D2 exists to make that misreading cost something.
- Reversibility: high. A better dataset re-registers as a new source; nothing in the
  contracts names OBF.

## Remaining uncertainty

- No ingredient-completeness threshold exists to judge 26.5% against.
- The attribution notice's correct name is unsettled: the provider's terms page names Open
  Food Facts while the data page on the same host names Open Beauty Facts. Recorded in
  `SRC-003`; it matters only when P1 publishes.
- The execution plan calls KHISS "a downloadable Korean cosmetics CSV". `[측정]` It is not
  downloadable — no attachment, no preview, no `distribution` in its catalogue JSON. The
  plan's own premise for that row is wrong as measured, and the row stays as written with
  `SRC-004` recording the measurement beside it.

## Required changes

- Project State: the dataset half of hypothesis 3 and its selected source; the inherited
  ODbL obligation.
- Contract or schema: `PoC Contract 0.1`'s limitation *"No real dataset source exists"* is
  answered and must be rewritten with the conditions from D2 rather than deleted.
- Acceptance tests: none by this packet. The importer is TASK-006.
- Migration or compatibility: none.
- Implementation handoff: an importer for OBF is written against a source that ignores
  unknown parameters, returns HTML on error, and cannot express deletion. Those are
  requirements, not surprises.
