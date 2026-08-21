# SRC-003 — Open Beauty Facts — Source Capability Profile

`[결정]` **Result: `NO-GO`.** Open Beauty Facts is a real, openly licensed, replayable
cosmetics dataset whose licence position is determinate and whose extraction is cheap. It
holds **zero** Korean sunscreen products and **zero** Korean toner products — the two
categories [DP-011](../../docs/decisions/DP-011-p0b-product-and-delivery-scope.md) fixed as
the product scope. Every other check it passes is a check on an empty set.

`[확인 사실]` This profile was written **before** any importer for this source exists, which
is the order B1 asks for and the order [`SRC-001`](SRC-001-naver-api-hub.md) could not
follow. Nothing here is back-filled from an integration.

## Identity

- Candidate ID: `SRC-003`
- Acquisition mode: `DATASET_IMPORT`
- Provider or producer: Open Beauty Facts, a project of the Open Food Facts association
- Distributor, if different: same (`static.openbeautyfacts.org` for exports,
  `world.openbeautyfacts.org` for the API); a Parquet mirror is published on Hugging Face
- Endpoint or dataset page: `https://world.openbeautyfacts.org/data`
- Content channel or domain: crowd-contributed cosmetics products — barcode, name, brand,
  category, country, quantity, ingredient text, and photographs
- Related experiment: none yet. This profile is input to the P1 Entry Gate, not to a run.
- Profile captured at: 2026-08-20T07:47+09:00 to 2026-08-20T08:32+09:00

## Rights and processing basis

- Terms or license URL and version/date:
  - `https://world.openbeautyfacts.org/data`, fetched 2026-08-20T07:51+09:00
  - `https://world.openbeautyfacts.org/terms-of-use`, fetched 2026-08-20T07:51+09:00
  - `https://world.openbeautyfacts.org/legal`, fetched 2026-08-20T07:51+09:00
  - ODbL 1.0 full text, `https://opendatacommons.org/licenses/odbl/1-0/`, fetched
    2026-08-20T07:50+09:00
  - DbCL 1.0 full text, `https://opendatacommons.org/licenses/dbcl/1-0/`, fetched
    2026-08-20T08:00+09:00
- Permitted experimental use: `YES`, unconditionally for internal work. ODbL §4.5 c:
  *"Use of a Derivative Database internally within an organisation is not to the public and
  therefore does not fall under the requirements of Section 4.4."*
- Redistribution permitted: **`CONDITIONAL`** — permitted, and the conditions are
  enumerated below. It is not a free redistribution.
- Agent processing permitted: `YES`
- Attribution or deletion obligation: attribution notice is required on any publicly used
  output (ODbL §4.3); share-alike and a machine-readable-copy offer attach to the derived
  store once that output is published (§4.4 c, §4.6). No deletion obligation is stated; the
  deletion *mechanism* is a separate measured gap, recorded under *Dataset capability*.
- Evidence and unresolved interpretation: see the next section. `[확인 사실]` The position
  is **not ambiguous**, so this candidate is not `BLOCKED` on rights. It fails on coverage.

### What the licence requires of derived output

`[확인 사실]` Three distinct licences are stated, on three distinct things, by
`https://world.openbeautyfacts.org/data` (fetched 2026-08-20):

> The Open Beauty Facts database is available under the Open Database License. The
> individual contents of the database are available under the Database Contents License.
> Products images are available under the Creative Commons Attribution ShareAlike licence.

`[확인 사실]` The contents licence does not soften the database licence. DbCL 1.0 §2.2, in
full: *"You must comply with the ODbL."*

`[확인 사실]` ODbL 1.0 defines the two output categories that matter here:

> "Derivative Database" – Means a database based upon the Database, and includes any
> translation, adaptation, arrangement, modification, or any other alteration of the
> Database or of a Substantial part of the Contents. This includes, but is not limited to,
> Extracting or Re-utilising the whole or a Substantial part of the Contents in a new
> Database.

> "Produced Work" – a work (such as an image, audiovisual material, text, or sounds)
> resulting from using the whole or a Substantial part of the Contents (via a search or
> other query) from this Database, a Derivative Database, or this Database as part of a
> Collective Database.

`[추론]` Under those definitions, a Cosmai import maps as follows. Raw envelopes, snapshots,
and normalized rows built from an OBF extract are a **Derivative Database** — §4.4 b says so
without room for reading: *"For the avoidance of doubt, Extraction or Re-utilisation of the
whole or a Substantial part of the Contents into a new database is a Derivative Database and
must comply with Section 4.4."* An opportunity card, a dashboard screen, or a report
rendered from those rows is a **Produced Work**. The alternative reading — that a normalized
row store is itself a Produced Work rather than a Derivative Database — is not available,
because §4.5 b limits the Produced Work carve-out to *creating* the work and the store is a
database, not a work.

`[추론]` The "it is only a few rows" escape does not survive the licence's own definition.
ODbL restricts use of a *Substantial* part, and defines it as *"substantial in terms of
quantity or quality or a combination of both. The repeated and systematic Extraction or
Re-utilisation of insubstantial parts of the Contents may amount to the Extraction or
Re-utilisation of a Substantial part of the Contents."* A scheduled importer is repeated and
systematic by construction. `[가설]` A one-off 36-row extract might fall below the threshold;
that reading is untested, cannot be relied on for a pipeline that re-runs, and is not needed
here.

`[확인 사실]` Three obligations follow, and they are not the same obligation:

1. **Publishing the output alone (§4.3).** *"Creating and Using a Produced Work does not
   require the notice in Section 4.2. However, if you Publicly Use a Produced Work, You must
   include a notice associated with the Produced Work reasonably calculated to make any
   Person that uses, views, accesses, interacts with, or is otherwise exposed to the Produced
   Work aware that Content was obtained from the Database, Derivative Database, or the
   Database as part of a Collective Database, and that it is available under this License."*
   §4.3 a gives the satisfying wording: *"Contains information from DATABASE NAME, which is
   made available here under the Open Database License (ODbL)."*
2. **Publishing the output pulls the store in with it (§4.4 c).** *"Derivative Databases and
   Produced Works. A Derivative Database is Publicly Used and so must comply with Section
   4.4. if a Produced Work created from the Derivative Database is Publicly Used."* §4.4 a
   then requires that Derivative Database be licensed under ODbL, a later ODbL, or a
   compatible licence.
3. **And requires handing over a copy (§4.6).** *"If You Publicly Use a Derivative Database
   or a Produced Work from a Derivative Database, You must also offer to recipients of the
   Derivative Database or Produced Work a copy in a machine readable form of: a. The entire
   Derivative Database; or b. A file containing all of the alterations made to the Database
   or the method of making the alterations to the Database (such as an algorithm), including
   any additional Contents, that make up all the differences between the Database and the
   Derivative Database."* Free of charge over the internet.

`[추론]` The practical consequence for this project, stated so it cannot be mistaken for a
caveat: **a public Cosmai card built on OBF data is not free.** It obliges an ODbL notice on
the card, ODbL licensing of the normalized store behind it, and a public machine-readable
copy of that store or of the exact transformation that produced it. Keeping the pipeline
internal (§4.5 c) removes all three. Committing an OBF-derived fixture to this repository is
the *publishing* case, not the internal one.

`[결정]` This profile does not choose between those regimes. That choice is a Decision
Packet, and this candidate is `NO-GO` for an unrelated reason, so the packet is not needed
now. It becomes needed the moment any OBF-derived row is published.

### What the provider's own terms add on top of ODbL

`[확인 사실]` `https://world.openbeautyfacts.org/terms-of-use`
(`sha256:a6d528dc8e0a86e90a65711041d1f2b9064e28edc023e203a0962423399aa688`, fetched
2026-08-20T08:00+09:00) states an attribution requirement in its own words, and applies it to
derivative works explicitly:

> The individuals and entities who reproduce or re-use information, data and/or photos from
> the Open Food Facts site or database have to mention the licence and to attribute the
> authorship to Open Food Facts with a link to https://openfoodfacts.org, the appropriate
> local version (e.g. https://en.openfoodfacts.org) or the product page, when the
> information and data reproduced or re-used pertain to a specific product. Such attribution
> is also necessary for derivative works.

`[확인 사실]` The same page also disclaims third-party rights inside the data: *"Other rights
of third parties may apply, such as: copyright for the product design and graphical elements
it contains (illustrations, pictures etc.), image rights of people (e.g. celebrities)
featured on the packaging, trademark rights etc. … It is the responsibility of individuals
and entities who wish to re-use the information, data and/or photos to verify by themselves
the rights that may apply."* `[추론]` That is a reason to import text fields and leave the
photographs alone; the photographs are also the CC BY-SA asset, i.e. the one under a
different licence again.

`[측정]` The terms served on the `openbeautyfacts.org` domain name **Open Food Facts**
throughout — *"The Open Food Facts database is available under the Open Database License"* —
while the `/data` page on the same domain names *Open Beauty Facts*. `[추론]` The licence is
the same either way, so this is not a licence ambiguity; what it leaves unsettled is which
name and URL an attribution notice should carry. That question is cheap to ask the provider
and is recorded rather than guessed.


`[확인 사실]` Nothing from this probe is committed. The repository holds digests and the
retrieval procedure only, per `AGENTS.md`.

## Hard gates

| Gate | Result | Evidence or blocking reason |
|---|---|---|
| G1 — Access and rights permit the recorded P0 experiment. | `PASS` | ODbL 1.0 + DbCL 1.0, stated by the provider and read in full; §4.5 c exempts internal use from share-alike. No credential, no registration, no quota application. |
| G2 — Data can be handled without exposing prohibited secrets, personal data, or restricted content. | `PASS` | Anonymous HTTPS reads, no credential to store. Product rows carry a contributor username in `creator` (3,424 of 3,425 rows in the export prefix) and `last_modified_by` (3,177 of 3,425); those are pseudonymous public contributor handles, and an importer that drops them is sufficient. No content requiring redaction was observed in either sample. |
| G3 — A representative sample can be retrieved or reconstructed with recorded identity, time, and hashes. | `PASS` | Seven captures with SHA-256 digests and exact commands, across both the API and the static export server; see *Reproduction and artifacts*. |
| G4 — The sample exercises at least one named P0 architecture question. | `FAIL` | The named question is `OQ-001`'s dataset half **for the DP-011 product scope** — Korean sunscreen and toner. Both counts are `0`. A dataset that holds none of the target population cannot answer whether the pipeline can normalize it. It could still exercise the mechanical import path — but so does [`SRC-002`](SRC-002-local-jsonl.md), which is already accepted for exactly that and claims nothing more. |
| G5 — Required access, volume, rate, and cost fit the P0-B timebox. | `PASS` | Free, anonymous. Full cosmetics CSV export 17,884,435 bytes gzipped; a 1 MiB HTTP range yields 3,425 complete rows. Documented API limits are 10 req/min for search and 15 req/min for product reads. |

## B1 hard checks

`[확인 사실]` [`p0-execution-plan.md`](../../docs/p0-execution-plan.md) §"B1 bounded candidate
set" sets five hard checks on this candidate. Each is answered from a measurement below.

| Hard check | Result | Measurement |
|---|---|---|
| ODbL obligations | `GO` | Licence read in full and the obligations on derived output enumerated above with citations. Determinate, satisfiable, and materially costly if output is published. |
| Korean sunscreen coverage | **`NO-GO`** | `0` products. `countries_tags_en=south-korea` ∩ `categories_tags_en=sunscreen` = 0, confirmed on two independent endpoints. |
| Korean toner coverage | **`NO-GO`** | `0` products. Same intersection with `categories_tags_en=toner` = 0. The whole database holds `6` toners of any nationality. |
| Ingredient completeness | **`NO-GO`** (not evaluable for the target scope) | The target population is empty, so completeness on it is undefined. Database-wide, `19,434 / 73,464` products (26.5%) are in state `en:ingredients-completed`; the global sunscreen category is `354 / 579` (61.1%); the 36 South Korea products are `12 / 36` (33.3%). No project document records a threshold to judge these against — see *Newly discovered questions*. |
| Stable row identity | `GO` | `code` survived real content change: all 121 products in the 2026-08-19 nightly delta export resolved in the live API 23 hours later with `created_t` identical, and the 3 whose `rev` and `last_modified_t` advanced kept the same `code`. A plain repeat capture 36 minutes apart produced **no** change and is reported as proving nothing. Deletion is a recorded gap in the *mechanism*, not in the identity. |
| Manageable fixture extraction | `GO` | The export server honours HTTP range requests (`206`). A 1,048,576-byte range of the gzipped CSV decompresses to 3,425 complete 200-column rows without touching the remaining 94% of the file. |

`[추론]` Two `NO-GO`s and one undecidable check. Under the matrix's own decision rule — *"at
least one hard gate is `FAIL`"* — this candidate is `NO-GO`, and no combination of the
passing checks changes that.

## Dataset capability

- File format and compression: four flavours are published — gzipped tab-separated CSV
  (`en.openbeautyfacts.org.products.csv.gz`), gzipped JSONL
  (`openbeautyfacts-products.jsonl.gz`), a gzipped MongoDB dump, and a Parquet mirror on
  Hugging Face. A gzipped RDF export exists and the provider marks it unmaintained.
  `[측정]` CSV `17,884,435` bytes, JSONL `95,925,687` bytes, both read from `Content-Range`
  on a one-byte range request at 2026-08-20T07:52+09:00.
- Dataset version or release date: `[측정]` `Last-Modified: Wed, 19 Aug 2026 00:22:27 GMT`
  on the CSV export and `00:18:01 GMT` on the JSONL, read at 2026-08-20T07:52+09:00. The
  provider states exports are generated nightly; the observed timestamps are consistent with
  that and do not independently prove a nightly cadence.
- Encoding and delimiter: `[측정]` UTF-8, tab-separated, `\n` line terminator. Every one of
  the 3,425 complete data lines in the measured prefix split into exactly 200 fields, so no
  embedded newline occurred in that prefix. `[추론]` That is evidence about the first 4.7% of
  the file ordered by barcode, not about the whole export.
- Row identity candidate: `code`. `[확인 사실]` The provider's field documentation says
  *"code : barcode of the product (can be EAN-13 or internal codes for some food stores), for
  products without a barcode, Open Food Facts assigns a number starting with the 200 reserved
  prefix"* — read from `https://static.openfoodfacts.org/data/data-fields.txt` on
  2026-08-20. `[측정]` The Open Beauty Facts copy that its own `/data` page links to,
  `https://world.openbeautyfacts.org/data/data-fields.txt`, returns `404`; so does
  `https://static.openbeautyfacts.org/data/data-fields.txt`. The citation above is therefore
  the sibling Open Food Facts file, and whether every OBF-specific field matches it is
  `UNKNOWN`.
- Event, publication, and update timestamps: `created_t`, `last_modified_t`,
  `last_updated_t` as Unix seconds, with `*_datetime` string twins in the CSV export. `rev`
  is a monotonically increasing per-product revision counter. `[측정]` All three of
  `created_t`, `last_modified_t`, and `rev` were present on 36 of 36 rows in sample A.
- Duplicate behavior: `[측정]` No duplicate `code` in any sample — 36 unique of 36, 100
  unique of 100, 50 unique of 50. `[추론]` `code` is the primary key of the upstream store, so
  duplicates within one export are not expected; this measures three samples, not the export.
- Missing and invalid values: heavy and uneven. `[측정]` In the 36-row South Korea sample:
  `product_name` 19/36, `brands` 25/36, `ingredients_text` 12/36, `categories_tags` 14/36,
  `quantity` 17/36, `product_name_ko` 0/36, `ingredients_text_ko` 0/36. In the 100-row
  sunscreen sample: `product_name` 82/100, `brands` 87/100, `ingredients_text` 67/100.
  `[확인 사실]` The provider states the reason itself, in its API documentation: *"Data in the
  Open Food Facts database is provided voluntarily by users who want to support the program.
  As a result, there are no assurances that the data is accurate, complete, or reliable."*
- Version, correction, and deletion behavior: `[확인 사실]` Daily delta exports cover the
  previous 14 days, listed at `https://static.openbeautyfacts.org/data/delta/index.txt`
  (13 files present when read on 2026-08-20T07:52+09:00). `[확인 사실]` The provider states
  the delta path cannot express deletion: *"due to the nature of mongoexport, the delta files
  cannot tell you about deleted products. To remove deleted products from your database, you
  will need to import the full MongoDB dump."* `[추론]` An incremental importer built on the
  deltas would accumulate tombstone-less rows and drift from the source; correcting it costs
  a full re-import. That is a real design constraint on any importer for this source and
  would have been worth knowing regardless of the coverage result.

## Measured data profile

All counts were obtained on 2026-08-20 between 07:47 and 07:58 +09:00 against
`world.openbeautyfacts.org`. Commands are in *Reproduction and artifacts*.

### Coverage — the check this candidate fails

| Filter | Count |
|---|---|
| whole database | `73,464` at 07:48, `73,465` at 07:50:42 |
| `countries_tags_en=south-korea` | `36` |
| `categories_tags_en=sunscreen` | `579` |
| `categories_tags_en=toner` | `6` |
| `countries_tags_en=south-korea` **∩** `categories_tags_en=sunscreen` | **`0`** |
| `countries_tags_en=south-korea` **∩** `categories_tags_en=toner` | **`0`** |

`[측정]` The two zeroes were reproduced on a second, independent endpoint —
`cgi/search.pl?action=process&tagtype_0=countries&tag_0=south-korea&tagtype_1=categories&tag_1=sunscreen&json=1`
returned `count: 0`, and the same endpoint returned `36` for South Korea alone, matching
`api/v2/search`.

`[측정]` The zeroes are not an artifact of a wrong country filter. South Korea does not
appear among the 100 country facets the provider lists; the least-populated one that does is
`en:somalia` at 44 products, so 36 falls just under the cutoff. K-beauty brands are present and tiny: `cosrx` 4, `innisfree` 4, `laneige` 6, `missha` 2,
`beauty-of-joseon` 0, `etude-house` 0 — and `brands_tags=cosrx` ∩ `sunscreen`,
`brands_tags=innisfree` ∩ `sunscreen`, and `brands_tags=laneige` ∩ `toner` are each `0`.
`origins_tags=en:south-korea` is `20`; `manufacturing_places_tags=south-korea` is `1`.

`[측정]` The zeroes are not an artifact of the API either. The 1 MiB export prefix — 3,425
rows ordered by ascending barcode — contains exactly **1** row mentioning South Korea, which
is what 36 in 73,464 predicts.

`[측정]` The category vocabulary is thin in exactly the place this project needs it.
`categories_tags_en=toners` (plural) returns `0`; `face-toner` returns `4` and
`facial-toner` returns `3`, which are separate free-text tags rather than a canonical
taxonomy entry. Of the 36 South Korea products, **22 carry no `categories_tags` at all**, and
the tags the remaining 14 carry include free text such as `en:Korean Cosmetics` and one
`ko:케첩` — "ketchup" — in a cosmetics database.

`[추론]` A canonicalization step could not repair this. There is no Korean sunscreen or toner
row to canonicalize, and the category field on the Korean rows is mostly absent and partly
wrong where present.

### Field profile

- `[측정]` The CSV export header carries **200 columns**. The first eleven are `code`, `url`,
  `creator`, `created_t`, `created_datetime`, `last_modified_t`, `last_modified_datetime`,
  `last_modified_by`, `last_updated_t`, `last_updated_datetime`, `product_name`.
- `[측정]` Ingredient text, where present, is substantial: median length 695 characters over
  the 12 non-empty South Korea rows; median `ingredients_n` of 33 parsed ingredients over the
  67 non-empty sunscreen rows.
- `[측정]` **No Korean-language content exists on the Korean rows.** In sample A,
  `product_name_ko` is 0/36 and `ingredients_text_ko` is 0/36; the 12 rows that carry
  ingredient text carry it identically in `ingredients_text` and `ingredients_text_en`; and
  **no Hangul character appears in any `product_name` or `ingredients_text` in the sample**.
  This holds even though `lang` is `ko` on 12 of the 36 rows (the rest: `en` 15, `de` 4,
  `fr` 3, `it` 1, `vi` 1). `[추론]` A Korean-market normalizer would be canonicalizing
  English strings written by non-Korean contributors, which is not the input DP-011's
  canonicalization hypothesis assumes.

### Row identity, tested against change

#### The repeat-capture test did not produce a change, and is reported as such

`[측정]` Two captures of the 50 most-recently-modified products, 36 minutes apart with
identical parameters — `C0` at 2026-08-20T07:50:42+09:00 and `C1` at 2026-08-20T08:26:23+09:00
— returned **byte-identical** bodies, `sha256:b8830040dba6f4f39fb332080dcba352c1424d4f60464fc4f8137843183ee628`
both times. Same 50 codes, same `rev`, same `last_modified_t`, same `created_t`, zero
differences of any kind.

`[측정]` That is not a cache artifact. Three further requests of the same query at 08:28:28,
08:29:15, and 08:30:01 each returned `x-cache-status: EXPIRED` — the proxy went to the
backend every time — and each returned the same bytes again. The newest `last_modified_t` in
all five responses is 2026-08-19T22:50:40Z, and the last request was issued at
2026-08-19T23:30Z.

`[추론]` No product in the database was edited during those 40 minutes. `[확인 사실]` **So the
repeat capture tested nothing about identity**, because there was no change for identity to
survive. Reporting it as "identity held across two captures" would be the defect this
project names: a test that passes while proving nothing.

#### The test that did produce a change

`[측정]` The nightly delta export supplies a population that is *known* to have changed, from
a *different* distribution channel. Procedure and result:

1. Fetched the newest delta,
   `openbeautyfacts_products_1787012322_1787098703.json.gz`, 81,135 bytes,
   `sha256:0af0a0e5297c50d9b2acfadec21b23fc6ba515db20721dc9ec0222a180c4aea5`, at
   2026-08-20T08:30:48+09:00. Provider-side `Last-Modified` 2026-08-19T00:18:24Z. It holds
   **121 products, 121 unique `code`s**, whose edits span 2026-08-18T01:16:27Z to
   2026-08-18T23:45:34Z.
2. Resolved all 121 codes against the live API at 2026-08-20T08:31+09:00 — about 23 hours
   after the export was cut — in three batched `?code=` queries.

| Observation | Result |
|---|---|
| delta codes that resolve to a live product | **121 / 121** |
| live `created_t` identical to the delta's | **121 / 121** |
| products whose `rev` advanced between the two | **3** |
| products whose `last_modified_t` advanced | **3** (the same 3) |

`[측정]` The three that moved: `7891010974312` `rev 5 → 7`, `5906721183488` `rev 13 → 14`,
and `4047196060247` `rev 2 → 12` — ten edits on that last one. In every case `code` and
`created_t` were unchanged while the revision counter and the modification time advanced.

`[추론]` **`code` survived real content change**, across 23 hours and across two independent
channels (a static nightly export and the live API). That is the claim the check asks for,
and it is now supported by an observation of change rather than by an absence of it.

`[가설]` Barcode reassignment and product deletion remain the two ways `code` could still
break as an identity, and neither is observable here. The provider states the second one is
invisible on the incremental path — *"the delta files cannot tell you about deleted
products"* — so an importer built on deltas cannot detect a deletion at all. Falsifying this
needs a capture separated by weeks against a population known to contain deletions; that is
P1 work.

### Observed failures and limits

- `[측정]` **Unknown query parameters are silently ignored.** `…/api/v2/search?zzz=1` returns
  the full `73,464`; `…?lang=ko` also returns the full `73,464`, and `sunscreen&lang=ko`
  returns the unfiltered `579`. An unknown *value* on a known tag filter behaves correctly —
  `categories_tags_en=zzzznotacat` returns `0`. `[추론]` An importer that filters on a
  parameter this API does not implement receives the whole database and no error. Any
  add-on for this source must assert the returned count against a known-good control, not
  trust the filter.
- `[측정]` `https://world.openbeautyfacts.org/country/south-korea.json` failed with no
  response at 07:52+09:00 and returned `200` on three consecutive retries at 07:55+09:00.
  `https://world.openbeautyfacts.org/country/en:south-korea.json` returns `500`.
- `[측정]` `https://world.openbeautyfacts.org/data/data-fields.txt`, linked from the
  provider's own data page, returns `404`.
- `[측정]` **The API returned `500` on a query it had already answered twice.** The identical
  `sort_by=last_modified_t&page_size=50` request that succeeded at 07:50:42 and 08:26:23
  returned `HTTP 500` at 08:27:28, and succeeded again at 08:28:28. `[확인 사실]` The `500`
  body is an **nginx HTML error page**, not JSON: `<html><head><title>500 Internal Server
  Error</title></head>…`, 177 bytes, `Content-Type: text/html`. `[추론]` An importer that
  parses the response before checking the status will fail on the parse rather than on the
  status, and will report the wrong cause. This is the case
  [`accept_status`](../integrated-p0/README.md) was built around, inverted: a real error
  status with a body that is not the documented envelope.
- `[측정]` **The response shape is not stable across identical requests.** Sample A at
  07:49:19 and sample A2 at 08:26:48 returned the same 36 codes with identical `rev`,
  `created_t`, and `last_modified_t` — and differed in bytes. Six rows carried a
  `product_name_ko` key with an empty value in the first response and **omitted the key
  entirely** in the second. `[추론]` `fields=` is not a schema guarantee: absent-key and
  empty-value are both possible for the same field on the same unchanged product, so a
  normalizer must treat them as one case.
- `[측정]` No `429` and no `503` was observed during this probe. One request — a plain
  `GET /terms-of-use` at about 07:57+09:00, immediately after a burst — returned **no
  response at all** (curl reported no status), and the identical request succeeded at
  08:01+09:00 after a deliberate 60-second pause. `[가설]` That was the rate limiter, dropping
  rather than answering. It is a hypothesis because no status code was returned to identify
  it; the falsifying test is a controlled burst, which was not run because being banned would
  have ended the probe. `[확인 사실]` The provider documents 10 req/min/IP for search and 15
  req/min/IP for product reads, and warns that exceeding them may result in an IP ban.
  `[추론]` Several bursts in this probe were at or above the search limit and were answered
  normally, so the limit is not enforced on every request — which is not evidence that
  exceeding it is safe.
- `[확인 사실]` The provider's own guidance for bulk consumers is not to use the API:
  *"If you expect your app to generate a lot of API traffic, we strongly encourage you to
  host a local instance of Product Opener … and use the daily exports to update your
  database."*

## Reproduction and artifacts

`[결정]` **No payload is committed.** OBF's ODbL basis would permit a redistribution under
conditions, but publishing an extract is the case that triggers §4.4 c and §4.6, and this
candidate is `NO-GO` — taking on a share-alike obligation for a rejected source would be
gratuitous. Digests and commands only.

### Environment and versions

| | |
|---|---|
| Client | `curl 8.21.0`, `python 3.14.4` |
| Platform | Linux 6.18.33.2 (WSL2) |
| Repository revision | `f85287c` on `dev` |
| User-Agent sent | `cosmai-p0-source-probe/0.1 (research contact <redacted>)` |

`[확인 사실]` The provider asks for an identifying User-Agent of the form
`AppName/Version (ContactEmail)`. The probe sent one. The contact address is the operator's
and is not written into this file.

### Retrieval procedure

Pace requests: the documented ceiling is 10 search requests per minute per IP.

```sh
UA='cosmai-p0-source-probe/0.1 (research contact <your-email>)'
BASE=https://world.openbeautyfacts.org/api/v2/search

# Coverage counts. Each returns {"count": N, ...}.
for q in \
  '' \
  'countries_tags_en=south-korea' \
  'categories_tags_en=sunscreen' \
  'categories_tags_en=toner' \
  'countries_tags_en=south-korea&categories_tags_en=sunscreen' \
  'countries_tags_en=south-korea&categories_tags_en=toner' ; do
  curl -s -A "$UA" "$BASE?$q&page_size=1&fields=code" |
    python3 -c 'import sys,json; print(json.load(sys.stdin)["count"])'
  sleep 7
done

# Ingredient completeness, from the provider's own state tag.
for q in \
  'states_tags=en:ingredients-completed' \
  'countries_tags_en=south-korea&states_tags=en:ingredients-completed' \
  'categories_tags_en=sunscreen&states_tags=en:ingredients-completed' ; do
  curl -s -A "$UA" "$BASE?$q&page_size=1&fields=code" |
    python3 -c 'import sys,json; print(json.load(sys.stdin)["count"])'
  sleep 7
done

# Cross-checks that the zeroes are not a filter artifact.
for q in \
  'brands_tags=cosrx' 'brands_tags=innisfree' 'brands_tags=laneige' 'brands_tags=missha' \
  'brands_tags=cosrx&categories_tags_en=sunscreen' \
  'brands_tags=laneige&categories_tags_en=toner' \
  'origins_tags=en:south-korea' 'manufacturing_places_tags=south-korea' \
  'zzz=1' 'categories_tags_en=zzzznotacat' ; do
  curl -s -A "$UA" "$BASE?$q&page_size=1&fields=code" |
    python3 -c 'import sys,json; print(json.load(sys.stdin)["count"])'
  sleep 7
done

# Independent confirmation on the older search endpoint.
curl -s -A "$UA" 'https://world.openbeautyfacts.org/cgi/search.pl?action=process&tagtype_0=countries&tag_contains_0=contains&tag_0=south-korea&tagtype_1=categories&tag_contains_1=contains&tag_1=sunscreen&json=1&page_size=1&fields=code'

# Sample A — every South Korea product, all measured fields.
F='code,product_name,product_name_ko,brands,categories_tags,countries_tags,lang,quantity,ingredients_text,ingredients_text_ko,ingredients_text_en,ingredients_n,ingredients_tags,created_t,last_modified_t,states_tags,rev'
curl -s -A "$UA" "$BASE?countries_tags_en=south-korea&page_size=100&fields=$F" -o sampleA-korea.json

# Sample B — the first 100 of the global sunscreen category.
G='code,product_name,brands,categories_tags,countries_tags,ingredients_text,ingredients_n,ingredients_tags,created_t,last_modified_t,rev,states_tags,quantity'
curl -s -A "$UA" "$BASE?categories_tags_en=sunscreen&page_size=100&page=1&fields=$G" -o sampleB-sunscreen-p1.json

# Captures C0 / C1 — the 50 most recently modified products, taken twice.
H='code,product_name,brands,last_modified_t,rev,created_t,ingredients_text,states_tags'
curl -s -A "$UA" "$BASE?sort_by=last_modified_t&page_size=50&fields=$H" -o capC0.json
# …wait…
curl -s -A "$UA" "$BASE?sort_by=last_modified_t&page_size=50&fields=$H" -o capC1.json

# Row identity against real change: the nightly delta vs the live API.
# The filename comes from the delta index; substitute the newest line.
curl -s -A "$UA" https://static.openbeautyfacts.org/data/delta/index.txt
curl -s -A "$UA" \
  https://static.openbeautyfacts.org/data/delta/openbeautyfacts_products_1787012322_1787098703.json.gz \
  -o delta-newest.json.gz
gzip -dc delta-newest.json.gz > delta-newest.json         # one JSON object per line
python3 -c 'import json,sys
rows=[json.loads(l) for l in open("delta-newest.json") if l.strip()]
print("\n".join(r["code"] for r in rows))' > delta-codes.txt
# then, in batches of 50, with a pause between batches:
curl -s -A "$UA" "$BASE?code=$(paste -sd, <(head -50 delta-codes.txt))&page_size=100&fields=code,rev,created_t,last_modified_t"
# compare: every code must resolve, created_t must match, and any rev that advanced
# is a product whose content changed while its identity did not.

# Bounded fixture extraction — 1 MiB of the gzipped CSV export, not the export.
curl -s -A "$UA" -r 0-1048575 \
  https://static.openbeautyfacts.org/data/en.openbeautyfacts.org.products.csv.gz \
  -o csv-prefix-1MiB.gz
gzip -dc csv-prefix-1MiB.gz > csv-prefix.tsv   # exits non-zero: "unexpected end of file"

# Export sizes without downloading them.
curl -s -A "$UA" -r 0-0 -D - -o /dev/null \
  https://static.openbeautyfacts.org/data/en.openbeautyfacts.org.products.csv.gz
```

### Digests of what was actually measured

| Artifact | Captured (KST) | Bytes | SHA-256 |
|---|---|---|---|
| `sampleA-korea.json` — 36 South Korea products | 2026-08-20T07:49:19 | 53,279 | `ec1286aac96acdc284887a7de5a53fc933859068bc5ac69a0b8d5a39babc91b3` |
| `sampleB-sunscreen-p1.json` — 100 sunscreens | 2026-08-20T07:53:40 | 171,494 | `79e4d533d087b48c1c0391d0c4fbacf1f4b7ae1431042941df23445d0ae9d827` |
| `capC0.json` — 50 most recently modified | 2026-08-20T07:50:42 | 32,534 | `b8830040dba6f4f39fb332080dcba352c1424d4f60464fc4f8137843183ee628` |
| `capC1.json` — the same query, 36 min later; **byte-identical to `capC0.json`** | 2026-08-20T08:26:23 | 32,534 | `b8830040dba6f4f39fb332080dcba352c1424d4f60464fc4f8137843183ee628` |
| `sampleA2-korea.json` — sample A re-taken 37 min later | 2026-08-20T08:26:48 | 53,153 | `c164d515a360b93bbb2590505e6f32ae8f1f10c337591d2f129e3a9583073217` |
| `delta-newest.json.gz` — the 2026-08-19 nightly delta, 121 products | 2026-08-20T08:30:48 | 81,135 | `0af0a0e5297c50d9b2acfadec21b23fc6ba515db20721dc9ec0222a180c4aea5` |
| `live-delta-codes.json` — those 121 codes resolved live | 2026-08-20T08:31 | — | `5f5aa0e8e8d51b46082a77174f66ff98619cf10ae10080bd5ccea8bf7c0eb0ed` |
| `csv-prefix-1MiB.gz` — bytes 0–1048575 of the CSV export | 2026-08-20T07:52:12 | 1,048,576 | `67e2bf214760b362094823f416006c8eaecee0469ced15dc1c106fc7761dee40` |

`[확인 사실]` **A re-run will not reproduce these digests.** The database gained a product
during this probe (`73,464` → `73,465` in under three minutes) and the export is regenerated
nightly. The digests identify these captures. What a re-run reproduces is the *shape* and,
for the coverage table, the zeroes — those are a property of the source, not of the moment.

- Redistributable fixture or local-only metadata location: none. No file from this probe
  enters the repository.
- Redaction or transformation: none applied. Field selection via the API's `fields`
  parameter is recorded in each command above.

## Newly discovered questions

`[확인 사실]` These are questions this probe could not answer from the project's own
documents. They are recorded here rather than resolved, per `AGENTS.md`.

1. **What ingredient-completeness rate would have counted as a pass?** No document in this
   repository states a threshold. The check exists in the B1 table; the bar does not. This
   probe reports 26.5% database-wide, 61.1% on sunscreens, and 33.3% on the Korean rows and
   declines to declare any of them sufficient.
2. **Whose card does the B1 dataset check serve now?**
   [DP-026](../../docs/decisions/DP-026-p0-closure-scope-and-collector-topology.md) moved
   DP-011's opportunity card to P1's first milestone, but the B1 table's hard checks still
   read against "the selected card". `[추론]` The reading used here is that the *categories*
   DP-011 fixed — sunscreen and toner — survive as the dataset's target scope even though the
   card moved, because the charter's P0-B exit criterion still asks for one dataset through
   the end-to-end flow and the flow's normalizers are category-shaped. If the intended
   reading is instead that any real external dataset closes the charter's dataset half
   regardless of category, then `SRC-003` is a `CONDITIONAL GO`, not a `NO-GO`, and this
   profile has answered the wrong question. That is an owner decision.
3. **May an ODbL-derived fixture ever be committed here?** Committing one makes this
   repository a publicly used Derivative Database under §4.4 c and triggers the §4.6
   machine-readable-copy offer over the whole derived store.
   [`data-handling.md`](../../docs/conventions/data-handling.md) treats `public` as
   "redistributable" without a case for share-alike-encumbered redistribution, and the
   `public`/`local`/`private` triple has no slot for "redistributable, but only if you also
   publish everything downstream of it". A fourth class, or an explicit rule, is missing.
4. **Which name does an OBF attribution notice carry?** The terms served on
   `openbeautyfacts.org` name Open Food Facts and link to `openfoodfacts.org`; the data page
   on the same host names Open Beauty Facts. Answerable by asking the provider.
5. **Is there a third dataset candidate?** The execution plan's rule is that expanding the
   B1 table requires recording why every listed candidate failed. Both listed dataset
   candidates now have that record. What replaces them, or whether `SRC-002`'s substitution
   is accepted as the charter's dataset with the gap stated, is not a worker's call.

## Recommendation

- Outcome: **`NO-GO`**
- Conditions or blocking gates: G4 fails. Korean sunscreen coverage is `0` and Korean toner
  coverage is `0` — the two categories DP-011 fixed. Ingredient completeness on the target
  scope is not evaluable because the scope is empty.
- P0 questions this candidate can test: `[추론]` Only the ones `SRC-002` already covers —
  that the add-on contract carries a non-network input path. It would test them against a
  real external provider rather than a self-authored file, which is a genuine improvement,
  but it cannot supply the *content* the charter's dataset half exists to obtain.
- Known representativeness limits: `[추론]` Every count is one provider on one day. The
  coverage zeroes are stable in the sense that a crowd-sourced database does not gain
  hundreds of Korean sunscreen rows quickly, but nothing here forecasts. The completeness
  and null rates come from 36 + 100 + 50 rows and a 3,425-row export prefix; they are not
  estimates for the whole 73,464.
- Proposed next action: profile the domestic fallback,
  [`SRC-004`](SRC-004-khiss-cosmetics-statistics.md). `[결정]` Written, and it is `NO-GO`
  too, for a different reason.
