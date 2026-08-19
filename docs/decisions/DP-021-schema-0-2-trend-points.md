# DP-021 — Normalized Schema 0.2: a second record type, and what that says about H5

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project team
- Extends: [DP-019](DP-019-normalized-schema-0-1-and-results.md) D1. Nothing in DP-019 is withdrawn.
- Narrows: [OQ-003](../open-questions/OQ-003-normalization-protocol.md) H2
- Bears on: `project-state.md` §5 — *"One small `Normalized Schema 0.x` can express useful common meaning across the first two sources"*
- Affected contracts: `NormalizedResult.body`

## Decision question

The two DataLab APIs — Search Trend and Shopping Insight — return **time series**:
`results[].data[]` of `{period, ratio}`. Schema 0.1 is a **document** record: a title, an
excerpt, an author, a published date. A ratio for a week has none of those, and a blog post
has no ratio.

So: does one schema hold both, and if so, how?

## What this makes measurable, and the answer

`project-state.md` §5 hypothesis 5 says one small Schema 0.x can express **useful common
meaning** across the first two sources. `[측정]` Against a document and a trend point, that
is **false as stated**, and the measurement is worth recording because the pairing is close
to the worst case the hypothesis will ever face:

| Field | Blog document | Trend point |
|---|---|---|
| identity | the post's URL | a series name and a period |
| time | when it was published | which interval it measures |
| text | title, excerpt, author | none |
| magnitude | none | a ratio relative to the window's maximum |

`[추론]` The overlap is **identity, time, and provenance** — and none of those is domain
meaning; they are the fields any record needs in order to be a record. There is no common
*beauty-trend* meaning to be had between "someone wrote this" and "people searched this much",
and a schema that manufactured one — a shared `score`, a shared `topic` — would be inventing
the very thing OQ-002 has not decided.

`[결정]` So H5 is recorded as **refuted in its strong form and useful in a weaker one**: one
schema can carry a common *envelope*, and cannot carry common *content*. This packet adopts
the weaker form, and the Architecture Synthesis should carry the refutation rather than
quietly restating the hypothesis as though it held.

## Decision

**D1 — `Normalized Schema 0.2` is a discriminated union on `record_type`.** Every record
carries the same four envelope fields, and the rest depends on the type:

| Envelope field | Meaning |
|---|---|
| `schema_version` | `"0.2"` |
| `record_type` | `"document"` or `"trend_point"` |
| `external_id` | the source's own identity for this record |
| `language` | BCP-47, stated by configuration and never detected (DP-019 D2) |

**D2 — `record_type: "trend_point"` is one series at one period.**

| Field | Meaning | Null when |
|---|---|---|
| `series` | The group the source reported it under — `title` in every DataLab response | never |
| `dimension` | `search_keyword`, `shopping_category`, or `shopping_keyword` | never |
| `terms` | The keywords or category codes the series was built from | never (may be empty) |
| `period` | ISO-8601 date, the start of the interval | never |
| `time_unit` | `date`, `week`, or `month` | never |
| `ratio` | The number the source reported | never |
| `segment` | `{device, gender, ages}` as the request asked for them, `null` per unset part | never (may be all-null) |

**D3 — `ratio` is carried and never interpreted.** `[확인 사실]` The vendor documents it as
*"구간별 검색량의 상대적 비율"* with the window's maximum set to 100. `[추론]` It is
therefore **not comparable across requests**: two runs over different windows produce
numbers on different scales, and a reader who averages them is averaging two different
units. The normalizer carries the number and the window it came from and does no
arithmetic; `notes` records `start_date` and `end_date` so a later reader can see the scale
rather than having to assume one.

**D4 — One row per `(series, period)`, and `external_id` is that pair.** A DataLab response
nests periods inside series; `NormalizedResult` is flat and `source_item_key` is the lineage
key, so the nesting is unrolled at the *collector*: one `raw_item` per point. `[결정]`
Unrolled in the collector rather than the normalizer, so that the Raw envelope keeps the
whole response verbatim and the items are individually addressable — which is what makes a
snapshot of them orderable by key at all (DP-019 D5).

**D5 — 0.2 is additive, and `normalizer.naver.blog` stays at `output_contract_version 0.1`.**
Its output has not changed, and a 0.1 document is a valid 0.2 document. Bumping it would put
a new version number on identical bytes, which is the version axis saying something false.
`[추론]` The result table will therefore hold `0.1` and `0.2` rows side by side, which is
DP-019 D3's coexistence doing its job rather than a migration waiting to happen.

## What stays open

- **Whether `dimension` belongs in the schema or in the source row.** It is in the record
  because a reader of one row needs to know what the ratio measures. `[가설]` If a third
  dimension arrives that the enumeration cannot name, this is the field that breaks.
- **Cross-source comparison.** Nothing here makes a blog count and a search ratio
  comparable, and nothing should until OQ-002 says what decision would use both.
- **OQ-003 is still open.** Its minimum experiment wants 50–100 annotated records across
  both sources and two candidate schemas compared. This is one candidate, adopted because
  something has to run.

## Falsification

| Claim | Falsified by |
|---|---|
| D1 — an envelope plus a type is enough | A source whose records fit neither type and need a third |
| D3 — `ratio` must not be interpreted | A documented, stable scale that makes two windows comparable |
| D4 — unrolling belongs in the collector | A source whose points are only meaningful as a whole series |
| The H5 refutation | A later source pairing where genuine common *content* appears |
