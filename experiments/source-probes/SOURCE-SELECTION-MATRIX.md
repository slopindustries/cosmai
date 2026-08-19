# P0-B Source Selection Matrix

- Status: `COMPLETE`
- Related Open Question: [OQ-001](../../docs/open-questions/OQ-001-source-capability.md) —
  stays `OPEN` for the dataset half; see *Selected pair* below
- Related experiments: [EXP-003](../integrated-p0/EXP-003-capability-layer.md)
- Last updated: 2026-08-19

Use one row per completed Source Capability Profile. Preserve links to measurements instead of copying unsupported conclusions into the matrix.

⚠️ `[확인 사실]` **This matrix was completed after the sources were integrated, not before.**
B1 places selection before implementation; in practice the NAVER collectors were built and
run first and this records what happened. The sequence failure is recorded in
[`JUDGMENT-DEBT-2026-08-18.md`](../integrated-p0/JUDGMENT-DEBT-2026-08-18.md); every cell
below is backed by a run whose evidence is linked.

## Candidate comparison

| Candidate | Mode | G1 Rights | G2 Safe handling | G3 Replayable sample | G4 P0 relevance | G5 Timebox | Key limitations | Recommendation | Profile |
|---|---|---|---|---|---|---|---|---|---|
| `SRC-001` NCP NAVER API HUB | `REST_API` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | Redistribution **not** permitted, so nothing captured may be committed; rate-limit and `Retry-After` behaviour `UNKNOWN`; one blog capture's digest lost before it was recorded | `CONDITIONAL GO` | [SRC-001](SRC-001-naver-api-hub.md) |
| `SRC-002` locally authored JSONL | `DATASET_IMPORT` | `PASS` (trivially) | `PASS` (trivially) | `PASS` | `PASS` | `PASS` | **Not an external dataset.** Self-authored, so the rights gate passes without testing anything; duplicate-row behaviour unexercised | `CONDITIONAL GO` *as a structural stand-in only* | [SRC-002](SRC-002-local-jsonl.md) |
| `SRC-003` Open Beauty Facts | `DATASET_IMPORT` | `PASS` | `PASS` | `PASS` | **`FAIL`** | `PASS` | **Korean sunscreen `0`, Korean toner `0`** of 73,464 products; only 36 South Korea rows at all, 22 of them with no category. ODbL share-alike and a machine-readable-copy offer attach to the derived store as soon as any output built from it is published; `code` identity verified against real change (delta export vs live API, 23 h apart) | **`NO-GO`** | [SRC-003](SRC-003-open-beauty-facts.md) |
| `SRC-004` KHISS cosmetics industry statistics | `DATASET_IMPORT` | `PASS` | `PASS` | **`FAIL`** | **`FAIL`** | `PASS` | **No retrievable file** — the data.go.kr entry carries no attachment and the tables sit behind a KOSIS SSO redirect. Finest granularity is one of 13 statutory product classes by year; sunscreen is not a class and toner is never broken out of 기초 화장용 제품류. Latest period 2021 | **`NO-GO`** | [SRC-004](SRC-004-khiss-cosmetics-statistics.md) |

## Decision rules

- `GO`: every hard gate is `PASS` and no unresolved limitation blocks its named P0 use.
- `CONDITIONAL GO`: every hard gate is `PASS`, but remaining non-gate operating limitations are bounded and explicitly accepted.
- `NO-GO`: at least one hard gate is `FAIL`, or any hard gate remains `UNKNOWN` at the P0-B source-selection review.
- A numeric score, popularity, or convenient API shape cannot override a hard-gate result.

## Selected pair

- REST candidate: **`SRC-001` — NCP NAVER API HUB**, `CONDITIONAL GO`. Three endpoints across
  two products: blog search (`GET`), search-term trend and shopping-category insight (`POST`).
- Dataset candidate: **`SRC-002` — a locally authored JSONL**, `CONDITIONAL GO` **as a
  structural stand-in**. `[결정]` Accepted by the project owner on 2026-08-19 in place of
  selecting a real dataset source, on the reasoning that the uncertainty B1's dataset half
  exists to reduce is *"does the add-on contract carry a non-network input path"*, and a
  file the project writes reduces that one completely while reducing nothing about dataset
  sources.
- Accepted conditions:
  1. Nothing captured from `SRC-001` is committed. Sources are registered `data_class = 'local'`
     and the repository holds hashes and retrieval instructions only.
  2. `SRC-002` may be cited as evidence about the **import path** and never about dataset
     *sources*.
  3. `SRC-001`'s rate-limit and `Retry-After` behaviour is `UNKNOWN` and may not appear in any
     synthesis as tested.
- Decision Packet: [DP-018](../../docs/decisions/DP-018-credential-parts-and-attachment.md)
  (credential shape), [DP-020](../../docs/decisions/DP-020-request-method-and-body.md)
  (request method and body), [DP-024](../../docs/decisions/DP-024-local-input-registry.md)
  (the input registry). `[확인 사실]` No packet was written for the *selection itself*; these
  three are the packets the selection produced.
- Fixture or retrieval identities: SHA-256 digests and the retrieval procedure in
  [`evidence/naver-real-data/README.md`](../integrated-p0/evidence/naver-real-data/README.md).
  `[확인 사실]` One of three captures has no digest, and why is recorded there.
- Remaining uncertainty carried into P0-B implementation and integration:
  - `[확인 사실]` **No real dataset source has been characterised.** `OQ-001` stays `OPEN` for
    that half. What P0 can now say is that the *mechanism* works, not that a source was found.
  - `[측정]` Throttling, deep pagination, redirects, schema drift, correction and deletion are
    all **unobserved** on `SRC-001`. The pipeline has code paths for redirects and bounds; none
    of them met a real source that used them.
  - `[가설]` A source that answers `200` with an error body is what `accept_status` exists for,
    and `SRC-001` **is not one** — it returns a real `401`. The control is built and its
    motivating case is untested against a real provider.
