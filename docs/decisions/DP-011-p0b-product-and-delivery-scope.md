# DP-011 — P0-B product decision and delivery scope

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project owner and delivery team
- Related Open Questions: [OQ-001](../open-questions/OQ-001-source-capability.md), [OQ-002](../open-questions/OQ-002-project-decision-contract.md), [OQ-003](../open-questions/OQ-003-normalization-protocol.md)
- Related delivery decision: [DP-012](DP-012-independent-scraper-services.md)
- Affected contracts: future `Normalized Schema 0.x`, `PoC Contract 0.1`
- Affected acceptance tests: future `ACQ`, `RAW`, `SNP`, `NRM`, domain `OPS`, and evidence-card scenarios

## Decision question

What is the smallest product decision Cosmai must support by 2026-08-26, with
2026-08-27 reserved for independent verification and handoff?

## Candidates

1. Build broad Korean beauty forecasting across many channels, with ML, AutoML, RAG, and
   LLM generation in the first delivery.
2. Build a backend-first, evidence-traceable R&D review flow for two product categories,
   using deterministic canonicalization and trend classes before optional LLM explanation.
3. Finish only the source-neutral ingestion platform and leave the product decision open.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: An evidence-backed opportunity card is a useful provisional decision unit for a cosmetics R&D or product-planning reviewer. | A reviewer cannot identify a concrete follow-up action from the card, or any material claim on the card cannot be traced to stored evidence. |
| H2: Sunscreen and toner are narrow enough to test canonical product, ingredient, efficacy, formulation, and use-feel semantics without pretending to cover all cosmetics. | Representative records require a third category to express the selected decision, or the two categories need incompatible evidence units that cannot share a small schema. |
| H3: A deterministic trend baseline is sufficient for the first review workflow. | The same frozen input produces different classes, or a class cannot be explained from stored counts, windows, thresholds, and evidence identifiers. |
| H4: Source quality is a better P0 control than source count. | One live REST source plus one replayable dataset cannot exercise provenance, replay, canonicalization, and evidence-card behavior, even with channel-spread claims withheld. |

## Experiment

- Scope: the P0-B critical path in [the execution plan](../p0-execution-plan.md).
- Environment and versions: the `dev` branch at `c0a266d` when this packet was drafted;
  exact execution revisions belong in the experiment records.
- Input and fixture identity: decided by OQ-001 after rights and capability checks. This
  packet does not approve a source merely because an add-on or API key exists.
- Procedure: select one REST source and one dataset, run the end-to-end flow, manually
  review canonical mappings and trend classes, and verify every card claim against its
  evidence identifiers.
- Known limitations: no real provider capture or dataset profile existed at the drafting
  revision; the thresholds below are reversible P0 defaults, not validated market laws.

## Evidence

`[확인 사실]` The project owner fixed the initial market to South Korea, the product
categories to sunscreen and toner, and the delivery priorities to backend and ingestion,
collection quality over source count, and canonical product and ingredient identity.

`[확인 사실]` At `c0a266d`, P0-A is accepted, a direct `collector.naver.blog` prototype
exists, and its synthetic platform path has run. [DP-012](DP-012-independent-scraper-services.md)
subsequently selected an independent Naver service plus COSMAI adapter as the delivery
boundary, so the direct prototype is reference evidence rather than a completed path. No real provider capture, dataset importer, semantic
normalizer, trend result, opportunity card, or domain operator surface exists. EXP-003 is
still `RUNNING` with ten unrepaired adversarial-review findings, three of them blocking.
See [EXP-003](../../experiments/integrated-p0/EXP-003-capability-layer.md) and its
[adversarial review](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md).

`[확인 사실]` The official
[Naver Blog Search API](https://developers.naver.com/docs/serviceapi/search/blog/blog.md),
checked 2026-08-19, is a REST API, requires a client ID and client secret in two headers,
exposes title, link, description, blogger, and post date, and limits search position to
1,000. The existing collector therefore represents a viable B1 candidate, not a selected
source or a complete market census.

`[추론]` The current critical path is not model search. It is closing the EXP-003
reliability gaps, selecting lawful inputs, and completing importer, canonicalization,
snapshot, lineage, scoring, and operator evidence. Adding AutoML before those artifacts
exist would optimize against an undefined and untraceable target.

## Decision

`[결정]` Candidate 2 is accepted for this P0 delivery.

### Decision consumer and action

- **Consumer:** a cosmetics-company R&D or product-planning reviewer.
- **Trigger:** a daily or weekly evidence review after a completed collection and analysis
  run.
- **Decision:** whether a sunscreen- or toner-related topic deserves human R&D review,
  evidence expansion, monitoring, or rejection.
- **Output unit:** one evidence-backed **R&D opportunity card** per canonical topic and
  product category.
- **Human boundary:** Cosmai proposes a review candidate. It does not recommend a formula,
  make a safety or efficacy claim, or approve product development.

### Card contract for the first delivery

Every card must contain:

- product category and canonical topic identifier;
- topic dimension: `ingredient`, `efficacy`, `formulation`, or `use_feel`;
- observed window, comparison window, sample size, source/channel, and capture time;
- deterministic class and the exact metrics and thresholds that produced it;
- evidence quality, uncertainty, and any `INSUFFICIENT_EVIDENCE` reason;
- stored `evidence_id` values and original URLs for every material claim;
- a bounded human review action: `REVIEW_NOW`, `WATCH`, `EXPAND_EVIDENCE`, or `REJECT`.

The card must not contain invented sales, market share, formulation, ingredient, product,
or source facts. Search-result counts and samples are labelled as observations of the
selected source, never as total Korean market volume.

### Canonical identity boundary

The minimum canonical graph is:

```text
product_category ← canonical_product → brand
                         ↓
               product_ingredient → canonical_ingredient
                         ↓
                   canonical_topic
                         ↓
                 evidence observation
```

Each canonical entity has a stable internal identifier, normalized label, aliases, source
identifiers, and mapping status. Resolution order is exact source identifier, approved
alias, then deterministic similarity with a recorded threshold and margin. Ambiguous
matches go to `REVIEW_REQUIRED`; they are never forced and an LLM cannot create an entity.

### Product and keyword seed boundary

Seeds start collection and normalization. They are not labels that prove a trend.

| Dimension | Sunscreen seed families | Toner seed families |
|---|---|---|
| Category and format | 선크림, 자외선차단제, 선로션, 선젤, 선세럼, 선에센스, 선스틱, 톤업 선크림, 무기자차, 유기자차, 혼합자차, SPF, PA | 토너, 스킨, 토너패드, 닦토, 흡토, 수분 토너, 진정 토너, 각질 토너, 약산성 토너, 미스트 토너 |
| Ingredient | 징크옥사이드, 티타늄디옥사이드, 에칠헥실트리아존, 디에칠아미노하이드록시벤조일헥실벤조에이트, 비스-에칠헥실옥시페놀메톡시페닐트리아진 | 병풀/시카, 어성초, 판테놀, 히알루론산, 세라마이드, 나이아신아마이드, 글리세린, 베타글루칸, 알란토인, AHA, BHA, PHA |
| Efficacy expression | 자외선 차단, 광안정성, 워터프루프, 톤업, 메이크업 베이스 | 수분, 진정, 장벽, 각질, 피지, 모공, 피부결, pH/약산성 |
| Formulation | 무기/유기/혼합 필터, 로션, 젤, 에센스, 세럼, 스틱, 쿠션, 스프레이 | 워터, 젤, 밀크, 에센스, 패드, 미스트, 2층상 |
| Use feel | 백탁, 눈시림, 밀림, 유분감, 끈적임, 발림성, 흡수, 화장 궁합, 향 | 끈적임, 흡수, 쿨링, 자극/따가움, 잔여감, 닦임 마찰, 레이어링, 향 |

Brand names and product names are not global query seeds by default. They enter an alias
table from selected-source evidence so that the collection plan does not silently become a
brand-ranking product.

### Deterministic trend baseline

Trend is classified per `canonical_topic × product_category × channel` on deduplicated
weekly observations. For a current two-week window:

```text
R = observations in the current two weeks
B = mean observations per two weeks over the prior six eligible weeks
velocity = log1p(R) - log1p(B)
robust_z = (R - median(baseline windows)) / (1.4826 * MAD(baseline windows) + 1)
persistence = active_weeks / eligible_weeks
diversity = unique_publishers / max(1, deduplicated_observations)
```

The first reversible thresholds are:

| Class | Minimum rule |
|---|---|
| `INSUFFICIENT_EVIDENCE` | Fewer than six eligible weeks, `R < 5`, provenance coverage below 95%, a required timestamp is missing, or the source retrieval cap truncates either comparison window. |
| `EMERGING` | Prior-six-week total `< 5`, `R >= 10`, and `diversity >= 0.5`. |
| `RISING` | `robust_z >= 2`, `velocity >= log(1.5)`, `R >= 10`, and `diversity >= 0.5`. |
| `STEADY` | `persistence >= 0.75`, `abs(robust_z) < 1`, and weekly coefficient of variation `<= 0.5`. |
| `COOLING` | `robust_z <= -1.5` and the matched baseline volume is at least 10. |
| `REVIEW` | Evidence passes the minimum gate but no class above is satisfied. |

These labels describe the captured source sample. They do not estimate sales or causal
demand. Channel spread is `NOT_MEASURED` until at least two eligible live channels exist;
an imported reference dataset does not count as a social channel.

### ML, RAG, and LLM boundary

- No ML, deep-learning, or AutoML model is on the delivery critical path. There is no
  labelled target or hidden evaluation corpus that would make a trained ranking claim
  defensible by 2026-08-26.
- Evidence retrieval by canonical IDs, time window, and `evidence_id` is allowed. This is
  the useful RAG-shaped part of the first delivery; a vector database is not required.
- An LLM may render a Korean explanation from a completed card and retrieved evidence only
  after the deterministic path passes. It cannot assign the trend class, create canonical
  entities, or add facts. Every explanation sentence must cite one or more `evidence_id`
  values, otherwise the renderer returns `REVIEW_REQUIRED`.

## Rejected alternatives

- Candidate 1 is rejected for this deadline. Broad source coverage and learned prediction
  multiply unresolved source, label, and evaluation questions before the backend flow is
  trustworthy.
- Candidate 3 is rejected because it would leave the system unable to demonstrate the
  R&D review action the project owner selected.
- Olive Young or other unapproved storefront crawling is not a fallback. Access and usage
  permission must be recorded before any such source enters OQ-001.

## Tradeoffs and risks

- Benefits: one traceable output unit, a small domain, deterministic replay, and a critical
  path that matches the existing backend architecture.
- Costs: the first result does not claim nationwide market volume, sales, or broad
  cross-channel spread.
- Failure modes: biased search samples, alias collisions, insufficient history, source
  rights uncertainty, and a polished explanation masking weak evidence.
- Reversibility: category seeds, thresholds, and the optional explanation renderer are P0
  defaults. Canonical IDs, provenance, Raw lineage, and abstention behavior are the
  intended contract candidates.

## Remaining uncertainty

- OQ-001 still selects the REST source and dataset after measurement and rights review.
- OQ-003 and OQ-004 still fix the schema/provider and sealed-snapshot boundary.
- The useful long-term time horizon, sales ground truth, and any learned prediction target
  remain open beyond this delivery.
- Independent scraper services expose a versioned export contract and COSMAI integrates
  only adapter add-ons under DP-012. Exact `trend-radar`, `yt-scrapper`, and Naver service
  schemas still need fixture and replay evidence.
- A second live channel is stretch scope; without it, channel-spread claims abstain.

## Required changes

- Project State: record the provisional product goal and the delivery window.
- Contract or schema: draft `Normalized Schema 0.x` and `PoC Contract 0.1` from real samples.
- Acceptance tests: add deterministic class, abstention, canonical-mapping, evidence-lineage,
  and unsupported-claim scenarios.
- Migration or compatibility: none in this packet; implementation changes remain P0-only.
- Implementation handoff: follow the dated critical path in the P0 execution plan.
- Service integration handoff: follow the independent-service adapter guide and do not
  merge external scraper repositories into COSMAI.
