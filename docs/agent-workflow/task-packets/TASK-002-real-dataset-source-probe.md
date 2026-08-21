# TASK-002 — Profile a real dataset source and record whether it passes its hard checks

- Status: `WORKER_DONE`
- Phase: P0-B, B1 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `general-purpose`, model `opus`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20 (worker completed 2026-08-20T08:35+09:00)

## Objective

One `SRC-003` source capability profile that states, from measurement rather than from the
provider's marketing, whether **Open Beauty Facts** passes every hard check the execution
plan sets for a dataset — and, if it does not, whether the KHISS cosmetics-industry CSV
does.

`[확인 사실]` Why this is reopened: `p0-charter.md`'s first P0-B exit criterion is *"One
REST source and **one dataset** complete the end-to-end flow."* The REST half is real. The
dataset half is [`SRC-002`](../../../experiments/source-probes/SRC-002-local-jsonl.md), a
file this project writes for itself, recorded as a deliberate substitution. The gate cannot
read a self-authored file as a dataset source.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §4, §5 — the dataset half of hypothesis 3 is self-authored and says so
- Accepted decisions: [DP-022](../../decisions/DP-022-structural-fixtures.md) (how a capture becomes publishable evidence), [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md) (P0 closes against the charter)
- Contracts: [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §Provenance and security
- Open Questions: [OQ-001](../../open-questions/OQ-001-source-capability.md) — this is its open half
- Owner decisions required: `none` — the owner chose Open Beauty Facts first and KHISS second on 2026-08-20; selecting between them on the measured result is this packet's output, not a new direction
- Required evidence or environment: network access for the provider's own documentation and a bounded sample. No credential is needed by either candidate.

## Scope

### Included

- `experiments/source-probes/SRC-003-open-beauty-facts.md`, following the structure of
  [`SRC-001`](../../../experiments/source-probes/SRC-001-naver-api-hub.md).
- Every hard check the execution plan's B1 candidate table sets for this candidate: **ODbL
  obligations including what licensing the *output* carries**, Korean sunscreen and toner
  coverage, ingredient completeness, stable row identity, and manageable fixture extraction.
- A recorded `GO` or `NO-GO` **per check**, with the measurement behind it.
- If Open Beauty Facts is `NO-GO`: a second profile for the KHISS candidate under
  `SRC-004-…`, with the same treatment, and an explicit statement of which check OBF failed.
- The retrieval procedure and the digest of whatever sample was actually measured.

### Excluded

- Writing any add-on. The importer is a separate packet.
- Downloading or committing the full export. A bounded sample is what this measures.
- Choosing the source. This packet **measures**; the orchestrator and owner select.
- Any change under `experiments/integrated-p0/`.

### Allowed files

- `experiments/source-probes/SRC-003-open-beauty-facts.md`
- `experiments/source-probes/SRC-004-khiss-cosmetics-statistics.md` (only if OBF is `NO-GO`)
- `experiments/source-probes/SOURCE-SELECTION-MATRIX.md` — append rows only

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- anything under `experiments/integrated-p0/`, `contracts/`, `docs/decisions/`
- any dataset payload. Store hashes and retrieval instructions, per `AGENTS.md`.

## Acceptance criteria

1. Every hard check in the execution plan's B1 row for this candidate has a `GO` / `NO-GO`
   and a measurement, not a restatement of the provider's claim.
2. The ODbL finding states what the licence requires of **derived output**, not only of
   redistribution, and cites the licence text.
3. Korean sunscreen and toner coverage is a **count from a real sample**, with the query or
   filter that produced it written down so it can be re-run.
4. Row identity is tested against change, not asserted: two captures, or one capture and the
   provider's stated identity guarantee with its own citation.
5. No payload is committed. The profile carries provider, capture time, licence basis,
   sample digest, and a retrieval procedure — the shape
   [`evidence/naver-real-data/README.md`](../../../experiments/integrated-p0/evidence/naver-real-data/README.md) uses.
6. Every claim carries an evidence label per [`evidence-labels.md`](../../conventions/evidence-labels.md).
   A `[확인 사실]` that is really a `[추론]` is a defect.
7. `NO-GO` on any check is a legitimate and complete result. Do not soften a failed check to
   produce a usable source.

## Verification

```sh
# Every command in the profile's retrieval procedure must run as written.
# The sample digest must reproduce from the recorded procedure:
sha256sum <the sample file the profile names>

# Coverage counts must re-run from the recorded filter.
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- Stop and report if the licence position is genuinely ambiguous. An ambiguous rights basis
  is a `BLOCKED`, never a `GO` with a caveat.

## Worker handoff

**Outcome: both candidates are `NO-GO`.** Open Beauty Facts holds zero Korean sunscreen and
zero Korean toner products; the KHISS entry has no retrievable file and its finest
granularity is one of thirteen statutory product classes by year.

### Changed files

- `experiments/source-probes/SRC-003-open-beauty-facts.md` — new
- `experiments/source-probes/SRC-004-khiss-cosmetics-statistics.md` — new
- `experiments/source-probes/SOURCE-SELECTION-MATRIX.md` — two rows appended to the candidate
  comparison table. Nothing else in that file was edited; *Selected pair* is untouched and
  still names `SRC-002`, which is now out of date and is the orchestrator's to resolve.

Nothing was committed. Nothing under `experiments/integrated-p0/`, `contracts/`, or
`docs/decisions/` was touched.

### Commands and results

All against the live providers on 2026-08-20 KST. Full commands are in each profile's
*Retrieval procedure*; these are the results.

**Open Beauty Facts coverage** — `GET https://world.openbeautyfacts.org/api/v2/search`:

| Filter | `count` |
|---|---|
| (none) | `73,464` at 07:48; `73,465` at 07:50:42 |
| `countries_tags_en=south-korea` | `36` |
| `categories_tags_en=sunscreen` | `579` |
| `categories_tags_en=toner` | `6` |
| `countries_tags_en=south-korea&categories_tags_en=sunscreen` | **`0`** |
| `countries_tags_en=south-korea&categories_tags_en=toner` | **`0`** |

Both zeroes reproduced on `cgi/search.pl`, an independent endpoint. Cross-checks that they
are not a filter artifact: `cosrx` 4, `innisfree` 4, `laneige` 6, `missha` 2,
`beauty-of-joseon` 0, `etude-house` 0; `origins_tags=en:south-korea` 20;
`manufacturing_places_tags=south-korea` 1; and exactly **1** South Korea row in the 3,425-row
export prefix, which is what 36-in-73,464 predicts.

**Ingredient completeness** — `states_tags=en:ingredients-completed`: `19,434 / 73,464`
database-wide (26.5%), `354 / 579` on sunscreens (61.1%), `12 / 36` on the Korean rows
(33.3%). The last figure matches an independent per-row count of `ingredients_text` in the
36-row sample.

**Row identity, tested against change.** The plain repeat capture **failed to test
anything** and is written up as such: two captures 36 minutes apart returned byte-identical
bodies, and three further requests with `x-cache-status: EXPIRED` confirmed the backend was
reached each time — no product was edited in that window. The test that worked used the
nightly delta export as a population known to have changed: 121 products from the
2026-08-19 delta, resolved against the live API 23 hours later — **121/121 resolved,
121/121 `created_t` identical, 3 with `rev` and `last_modified_t` advanced** (one from
`rev 2` to `rev 12`) under an unchanged `code`.

**Bounded extraction.** `Content-Range` on a one-byte request: CSV export `17,884,435`
bytes, JSONL `95,925,687`. A `Range: 0-1048575` request returned `206`, and the 1 MiB
decompressed to `3,426` newline-terminated lines — a header plus **3,425 complete 200-column
rows**, every one with exactly 200 fields.

**ODbL.** Licence text read in full at `opendatacommons.org/licenses/odbl/1-0/` and
`/dbcl/1-0/`. §4.3, §4.4 a/b/c, §4.5 b/c and §4.6 quoted in the profile with the
Derivative-Database / Produced-Work mapping worked through.

**KHISS.** `data.go.kr/catalog/3081174/fileData.json` → `license: 이용허락범위 제한 없음`,
`encodingFormat: CSV`, 96 rows, and **no `distribution` and no download URL**. The portal's
own preview endpoint returns a version list and no CSV. The provider's indicator API
(`khiss.go.kr/indi/get/statTable`) returned **42 cosmetics tables**, all annual or irregular
aggregates, latest period 2021 (employment 2022-02, R&D 2019). `kosis.kr/statHtml` → `302` to
`sso.kosis.kr`.

### Evidence locations

No payload is committed. Both profiles carry provider, capture time, licence basis, SHA-256
digests, and a retrieval procedure, following the shape of
[`evidence/naver-real-data/README.md`](../../../experiments/integrated-p0/evidence/naver-real-data/README.md).
Digest tables are in each profile's *Reproduction and artifacts*. The captured files live in
the worker's scratch directory outside the repository and are not preserved; the retrieval
procedures reproduce equivalents, not the same bytes.

### Limitations and remaining risks

- `[추론]` Every OBF count is one provider on one morning. The coverage zeroes are a property
  of the source rather than of the moment, but the completeness and null rates come from
  36 + 100 + 121 rows and a 3,425-row export prefix and are not estimates for all 73,464.
- `[측정]` The OBF API **silently ignores unknown query parameters** — `?zzz=1` and `?lang=ko`
  each return the unfiltered `73,464`. Any importer filter must be asserted against a
  known-good control.
- `[측정]` The API returned an **nginx HTML `500`** on a query it had answered twice, and
  returned the *same* query's fields with a key present-and-empty in one response and absent
  in the next. `fields=` is not a schema guarantee.
- `[가설]` One request returned no response at all right after a burst; the documented limit
  is 10 search req/min/IP. Probably the rate limiter, but no status was returned to prove it,
  and the falsifying test would risk an IP ban.
- `[확인 사실]` OBF delta exports **cannot express deletion** — the provider says so. An
  incremental importer would accumulate rows the source has removed.
- `[측정]` The KHISS CSV itself was never obtained. Its encoding, delimiter, header, row
  identity, duplicates, and null rates are all `UNKNOWN`, and the profile says `UNKNOWN`
  rather than inferring them from the catalogue description.

### Newly discovered questions or blockers

1. **No ingredient-completeness threshold exists anywhere in this repository.** The B1 table
   sets the check; no document sets the bar. The profile reports 26.5% / 61.1% / 33.3% and
   declines to declare any of them a pass.
2. **Which reading of the B1 dataset check is binding after DP-026?** DP-026 moved DP-011's
   opportunity card to P1, yet the B1 hard checks still read against "the selected card". The
   profile assumes the *categories* — sunscreen and toner — survive as the dataset's target
   scope. **If the intended reading is instead that any real external dataset closes the
   charter's dataset half regardless of category, then `SRC-003` is a `CONDITIONAL GO`, not a
   `NO-GO`, and this packet answered the wrong question.** This is the one finding that could
   invert the result and it is an owner decision.
3. **`data-handling.md` has no class for share-alike-encumbered data.** Committing an
   ODbL-derived fixture makes this repository a publicly used Derivative Database under §4.4 c
   and triggers §4.6's machine-readable-copy offer over the whole derived store. The
   `public` / `local` / `private` triple has no slot for "redistributable, but only if you
   also publish everything downstream of it."
4. **Which name does an OBF attribution notice carry?** The terms served on
   `openbeautyfacts.org` name Open Food Facts and link to `openfoodfacts.org`; the data page
   on the same host names Open Beauty Facts. Answerable by asking the provider.
5. **The execution plan's B1 table describes KHISS as "a downloadable Korean cosmetics CSV".
   It is not downloadable.** The plan's premise for that candidate is wrong as measured, and
   the table should be corrected by whoever owns it.
6. **Both dataset candidates the plan named are now exhausted.** The plan's own rule —
   *"Expanding beyond this table requires recording why every listed candidate failed a hard
   check"* — is now satisfied. What replaces them, or whether `SRC-002`'s substitution is
   accepted as the charter's dataset with the gap stated, is not a worker's call. **No blocker
   prevented completing this packet; this is the next decision, not an obstruction.**

## Review

- Attack report: not yet written
- Result: `BLOCKED`
- Orchestrator disposition: pending worker completion
