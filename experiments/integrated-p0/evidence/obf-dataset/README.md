# Real-data capture — Open Beauty Facts, `importer.local.jsonl`

`[결정]` **No OBF row is committed here, and none will be.** `DP-027` registered this
source `data_class = "local"`: the licence permits internal processing unconditionally
(ODbL §4.5 c), but publishing a derived extract is the act that pulls in §4.4 c's
share-alike and §4.6's machine-readable-copy offer (`SRC-003`, *What the licence requires
of derived output*). So, exactly as `../naver-real-data/README.md` does for NAVER: hashes
and a retrieval procedure, no payload.

## Why this exists

`SRC-003` measured Open Beauty Facts as a real, cheaply-extractable dataset and
recommended `NO-GO` on Korean sunscreen/toner **coverage** — but that recommendation is
about product content, and `DP-026` moved the product scope to P1. What was still missing
was evidence that a real external dataset's own bytes, not `SRC-002`'s self-authored
fixture, pass through the installed `importer.local.jsonl`, `DP-024`'s input registry, and
a sealed snapshot. `TASK-007` is that evidence, and this file is its record.

## What this does not establish

`[결정]` `DP-028` D6: *no gate claim may read "the dataset half is closed" as "the dataset
is useful for the product question"*. Stated plainly, not as a subordinate clause, because
this is the file a P1 Entry Gate reader opens first for the charter's dataset half:

- `[확인 사실]` `DP-027` D2 recorded **zero Korean sunscreen and zero Korean toner rows**
  in this source. P0 gains no product-relevant evidence from Open Beauty Facts, and nothing
  below changes that count.
- `[확인 사실]` `DP-027` D2 also recorded **ingredient completeness at 26.5%,
  database-wide** — and no threshold exists anywhere in this repository to judge that
  number against. A reader cannot conclude "good enough" or "not good enough" from it; it
  is reported because it was measured, not because it is decided.
- **"Closed" below means the mechanical path works** — a real delta's own bytes import
  through the installed `importer.local.jsonl`, seal into a verifiable snapshot, and
  normalize through the installed `normalizer.obf.product` into Schema 0.3 `product`
  records. It does not mean this dataset answers, or can answer, the Korean sunscreen/toner
  product question.
- `[확인 사실]` `DP-026` D1 moved that product question — the opportunity card, sunscreen
  and toner canonicalization, deterministic trend classes — to **P1's first milestone**.
  Nothing in this file substitutes for that work.

## Which two deltas, and why

`SRC-003` measured that OBF's delta index is a rolling window whose newest two windows
abut — one's `to_ts` equals the next one's `from_ts` — and that the newest-at-capture-time
delta and the one before it shared three `code`s across a real edit. This capture read
"take the most recent complete delta" and "a second, later delta whose window overlaps"
together as: the newest published delta is the *second* import, and the one immediately
before it is the *first*. On **2026-08-20**, that pair happened to be the same two files
`SRC-003` already looked at the same day, ~7 hours earlier — one delta had not yet been
superseded by a newer one — so the three-`code` overlap `SRC-003` measured is exercised
again here, this time through the importer rather than through a hand probe.

## What was captured

| | Delta A (first import) | Delta B (second, later import) |
|---|---|---|
| Filename | `openbeautyfacts_products_1787012322_1787098703.json.gz` | `openbeautyfacts_products_1787098703_1787185119.json.gz` |
| URL | `https://static.openbeautyfacts.org/data/delta/openbeautyfacts_products_1787012322_1787098703.json.gz` | `https://static.openbeautyfacts.org/data/delta/openbeautyfacts_products_1787098703_1787185119.json.gz` |
| Local file read (`raw_envelope.retrieved_at`) | 2026-08-20T15:35:5x KST (`raw_envelope.retrieved_at 15:35:56.234257+09`, `TestARealDeltaImportsThroughTheInstalledHost` run) | 2026-08-20T15:39:25.774578+09 (`raw_envelope.retrieved_at`, `TestChangedContentIsANewObservation` run) |
| `.gz` bytes / SHA-256 | 81,135 / `sha256:0af0a0e5297c50d9b2acfadec21b23fc6ba515db20721dc9ec0222a180c4aea5` | 114,812 / `sha256:333d98a72a69789d114b28bf58e872250f6c668840278ad90be28beec022bd50` |
| `.jsonl` bytes / SHA-256 | 665,658 / `sha256:5cefb426f7d94afd0bd3c743e38f13f70e2f7720d7f2277c51bc28901a3b3337` | 898,166 / `sha256:91631c0a30ad325a3ce1a608db3b1b9bec49f292b9f1aa78820d055dd413dd05` |
| Products / unique `code` | 121 / 121 | 126 / 126 |

`[확인 사실]` The row above is labeled by what it is, not by what an earlier version of this
table called it. `raw_envelope.retrieved_at` is set at `addon_host/capabilities.py:548` when
the **local decompressed file** is read, not when HTTPS delivered it — `FetchedDelta.fetched_at`
in `test_obf_real_data.py` is the actual acquisition time, and this run did not persist it
anywhere. The two differ by however long decompression and job dispatch took between fetch
and import; small here, but the earlier "Fetched" label claimed a quantity this table does
not carry.

`[측정]` Delta A's `.gz` digest is byte-identical to the one `SRC-003` recorded for this
same filename **the same day, ~7 hours earlier** — `SRC-003`'s *Capture ledger* records it
at `2026-08-20T08:30:48+09:00` (`0af0a0e5...`), not "a day earlier" as an earlier version of
this line said; the 2026-08-19 date belongs to the delta's *content*, not to `SRC-003`'s
capture time. The export server serves a fixed archived file rather than a live query, so a
second retrieval reproducing the same bytes is expected here, unlike NAVER's blog search or
DataLab endpoints.

`[측정]` The three `code`s `SRC-003` found advancing between the delta and a live re-check
— `7891010974312`, `5906721183488`, `4047196060247` — are exactly the three `code`s shared
between delta A and delta B here. `SRC-003` observed the *effect* (a `rev` and
`last_modified_t` that had moved); this capture observes the *cause* from OBF's own two
export windows, without needing the live API at all.

### The real import, through the installed host

`[측정]` `POST /sources/obf-dataset/import` (added 2026-08-20; DP-024's route for the
dataset half of the charter's operator flow) enqueued `addon:importer.local.jsonl`, and
`JobRunner` ran it against delta A, decompressed to
`var/samples/obf/openbeautyfacts_products_1787012322_1787098703.json` (gitignored, not in
the working tree).

| | |
|---|---|
| `raw_envelope.body_sha256` | `sha256:5cefb426f7d94afd0bd3c743e38f13f70e2f7720d7f2277c51bc28901a3b3337` — identical to the `.jsonl` digest above: the envelope holds the file whole, byte for byte |
| `raw_envelope.retrieved_at` | `2026-08-20 15:35:56.234257+09` |
| `raw_item` count | 121, unique `item_key` (= `code`) count 121 |
| Skip counters | `malformed_json` 0, `not_an_object` 0, `missing_key_field` 0 — a real delta held none of B4's dataset-row failures; `SRC-002` already carries that coverage |
| Payload check | every stored `raw_item.payload`'s SHA-256 is a member of the set of per-line SHA-256 digests computed directly from the downloaded file — the payload is the source's own bytes, not a re-serialization |

Environment for this run: kept test database `cosma_p0_test_main_79244_0`
(`--keep-database`, not part of this change; dropped after this record was written).

### Snapshot sealed and verified

`[측정]` `POST /sources/obf-dataset/snapshots` over the 121-item delta-A import sealed:

| | |
|---|---|
| Snapshot id | `8951b6f0-c3dd-4ecc-b54f-5e785769378c` (kept db `cosma_p0_test_main_80669_0`) |
| `item_count` | 121 |
| `manifest_sha256` | `sha256:82c27a07b12d62a6bc455f58c8c8c112227dd43055a41136ccaca041ca70b770` |
| `sealed_at` | `2026-08-20 15:38:22.159815+09` |
| `verifies` (via `GET /snapshots/{id}` and `domain.snapshot_tampering`) | `true`, `problems: []` |

A second, independent seal over the same 121 raw items (a different test, its own database)
produced snapshot `f17f43d6-f01f-4023-b5b2-b2cfe7aeacc5`, `sealed_at`
`2026-08-20 15:38:22.292334+09`, **the same** `manifest_sha256`
(`82c27a07b12d62a6bc455f58c8c8c112227dd43055a41136ccaca041ca70b770`) — the selection rule
(`DP-019` D5: ordered by `item_key`, latest wins on a duplicate) is deterministic over one
fixed set of raw rows, independent of which process sealed it.

### Tamper detection

`[측정]` On the second snapshot above (`f17f43d6…`), `domain.snapshot_tampering` returned
`()` — verified clean — **before** any change. Then, directly against `snapshot_item`
(no store method exists for this, matching `test_domain_store.py`'s own tamper tests):

```sql
update snapshot_item set payload = '{"code": "tampered"}'
where snapshot_id = 'f17f43d6-f01f-4023-b5b2-b2cfe7aeacc5' and ordinal = 0;
```

Ordinal 0's `item_key` is OBF `code` `00036151`; its stored `payload_sha256` remained the
*original* digest (`payload_sha256` is written at seal time, not recomputed on write), so it
now disagrees with the mutated bytes. `domain.snapshot_tampering` after the mutation named
both:

- `member 0 ('00036151') no longer matches its digest`
- `the recomputed manifest digest differs from the sealed one`

and `GET /snapshots/f17f43d6-...` reported `"verifies": false`. The detector is shown
capable of both outcomes on the same snapshot: `()` before, two named problems after.

### Identical replay

`[측정]` Kept db `cosma_p0_test_main_80881_0`: delta A imported twice through
`POST /sources/obf-dataset/import`, then sealed once before the replay and once after.

| | |
|---|---|
| `raw_envelope` count | 2 (Raw is logically append-only; the replay is not refused at this layer) |
| `raw_item` count | 242 = 2 × 121 |
| Snapshot before replay | `a10aacab-1925-4519-85b5-4d255f6bc85b`, `item_count` 121, manifest `82c27a07…` |
| Snapshot after replay | `6d2b4d67-8b46-4140-b798-d407c054a219`, `item_count` 121, manifest `82c27a07…` (identical) |

`[결정]` The chosen idempotency behavior (charter exit criterion 3) lives at the snapshot
layer, not at Raw: `raw_item` doubles, but `seal_snapshot_from_raw`'s duplicate-key rule
(`DP-019` D5 — latest `emitted_at` wins) collapses the replay to the same 121 members and
the same manifest digest either way. A platform that refused the second `raw_item` insert
outright was not built for this kind — nothing in `DP-024` or `importer.local.jsonl`
enforces Raw-level uniqueness — so this is reported as the behavior observed, not asserted
as the only correct one.

### Changed content — a new observation, not an edit

`[측정]` Kept db `cosma_p0_test_main_81154_0`: delta A imported, then the operator-approved
`input_profile.inputs.rows` repointed at delta B's decompressed file, then imported again
into the **same** `obf-dataset` source — the scenario `SRC-003` could only observe from
outside, now exercised through the importer itself.

| | |
|---|---|
| `raw_envelope` 1 | `body_sha256 5cefb426…` (delta A), `retrieved_at 15:39:25.716439+09` |
| `raw_envelope` 2 | `body_sha256 91631c0a…` (delta B), `retrieved_at 15:39:25.774578+09` |
| Each of the 3 shared codes (`7891010974312`, `5906721183488`, `4047196060247`) | **2** `raw_item` rows, in the two distinct envelopes above — appended, not updated in place |
| Snapshot | `81cce37f-eba5-48d6-acea-99035f4ab139`, `item_count` **244** = 121 + 126 − 3, manifest `sha256:bc4d8a23b0042e0769d0c9871166dee56eb4089a7a8e1ca7892fdc25a4403443` |

The test asserted, and this record confirms independently: for each of the 3 shared codes
the sealed snapshot's member is byte-identical to that code's line in **delta B**, not
delta A — `seal_snapshot_from_raw`'s "latest `emitted_at` wins" rule selected the newer
observation. Both the older and the newer `raw_item` row remain in the database; nothing
was edited or deleted to produce this.

## Usage basis

| | |
|---|---|
| Provider | Open Beauty Facts / Open Food Facts association |
| Stated basis | `DP-027`, `CONDITIONAL GO`: internal processing under ODbL 1.0 §4.5 c, no public use |
| Covers | Retrieval, decompression to `var/` (gitignored), import into Raw, sealing a snapshot |
| Does **not** cover | Redistribution — no OBF row, in any form, enters the working tree, tracked or untracked, outside `var/` |
| Recorded as | `source.data_class = 'local'` on `obf-dataset` |
| Redaction | none needed for this capture: `code`, `product_name`, `brands`, timestamps, `rev` — no credential-shaped field |

## Retrieval procedure

```sh
UA='cosmai-p0-obf-importer/0.1 (research contact <your-email>)'
curl -s -A "$UA" https://static.openbeautyfacts.org/data/delta/index.txt | sort | tail -2
# the last two lines are delta A (second-to-last) and delta B (last)

curl -s -A "$UA" \
  https://static.openbeautyfacts.org/data/delta/openbeautyfacts_products_1787012322_1787098703.json.gz \
  -o deltaA.json.gz
curl -s -A "$UA" \
  https://static.openbeautyfacts.org/data/delta/openbeautyfacts_products_1787098703_1787185119.json.gz \
  -o deltaB.json.gz
sha256sum deltaA.json.gz deltaB.json.gz
gzip -dc deltaA.json.gz | sha256sum
gzip -dc deltaB.json.gz | sha256sum
```

**The gated real-data test.**

```sh
export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"
# `experiments/integrated-p0/tests/test_obf_real_data.py` alone does not register
# `--run-network`/`--run-credential`: those flags live in `tests/conftest.py`, and pytest
# only loads a conftest that is an ancestor of an argument path. Listing `tests` alongside
# the target file — as below — is what makes the flag exist; the packet's own verification
# command, which names the file alone, hits `unrecognized arguments` for the same reason
# `test_naver_real_data.py` does when invoked the same way. Recorded under *Newly
# discovered questions* below rather than silently worked around.
.venv/bin/python -m pytest -q tests experiments/integrated-p0/tests/test_obf_real_data.py \
  --run-network
```

**What will not match.** A re-run imports whatever the *current* newest two deltas are —
the rolling window moves daily — so a later run exercises a different pair of files with
different digests. What a re-run reproduces is the *shape*: one file, decompressed intact,
imported without a skip, sealed, replayed idempotently at the snapshot layer, and (when the
pair happens to overlap) a later occurrence outranking an earlier one without editing it.

## Environment

| | |
|---|---|
| Python | 3.13.14 |
| PostgreSQL | local cluster under `var/postgres` (`COSMA_DB_HOST`/`COSMA_DB_NAME`/`COSMA_DB_USER`, not `scripts/with-database.sh` — recorded failing on this machine before this task) |
| Repository revision at capture | `dev`, 2026-08-20, on top of TASK-007's working tree |
| Contract version | `addon_api` per `CONTRACT_VERSION` at capture time |
| Platform | Linux 6.18 (WSL2) |

## Newly discovered questions

1. **`experiments/integrated-p0/tests/test_obf_real_data.py --run-network` alone is not a
   runnable command in this environment.** `pytest`'s conftest discovery only loads a
   conftest that sits on an ancestor path of a collection argument; `tests/conftest.py`
   (which defines `--run-network`/`--run-credential`) is not an ancestor of
   `experiments/integrated-p0/tests/`, so passing only the latter fails with
   `unrecognized arguments`. This affects `test_naver_real_data.py`'s documented
   invocation identically — it is a pre-existing property of the suite, not something
   this task introduced — but neither evidence file had said so until now. Passing `tests`
   alongside the target file (as this file's retrieval procedure does) works because
   `pytest`'s initial conftest collection then includes both trees.
2. **Reading `httpx`'s certificate bundle needed the sandbox disabled.** This machine's
   command sandbox denies reads of `.venv/lib/python3.13/site-packages/certifi/cacert.pem`,
   which `ssl.create_default_context` needs to build a verified HTTPS client. Every
   network call in this task's test run — and the manual `curl` calls in this file's
   retrieval procedure, which do not hit this path — otherwise behaves normally.

## TASK-010 — the normalizer half of the flow, run for the first time

`[확인 사실]` Everything above this section is TASK-007's: a real delta into Raw and a
sealed snapshot, and no further. The attack report on TASK-008
(`../../ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md`) measured that no real Open Beauty
Facts row had ever reached `normalizer.obf.product` — every prior `product` record came
from a fixture its own author wrote. This section is that run: the snapshot above, taken
through the installed `normalizer.obf.product@0.1` by `JobRunner` and the host's normalize
path (`experiments/integrated-p0/tests/test_obf_real_data.py::TestTheNormalizerRunsOnTheRealSnapshot`),
not a hand-built `NormalizeContext`.

`[측정]` **Which delta, and why the digest repeats.** This run re-fetched OBF's delta index
rather than trusting the files already under `var/samples/obf/` (the packet's own
instruction). The rolling window had not moved since TASK-007's capture, so the
newest-two-deltas pair was byte-identical to TASK-007's delta A and B, and the resulting
snapshot's `manifest_sha256` is the same value TASK-007 recorded.

| | |
|---|---|
| Snapshot id | `1ce74fc5-0502-4c3d-a626-d8233fe6b77d` — a fresh seal, not a reuse of TASK-007's snapshot row. `[확인 사실]` This run's database name was not recorded before the kept database was dropped, unlike TASK-007's four scenarios above (`…_79244_0`, `…_80669_0`, `…_80881_0`, `…_81154_0`); this line names the gap rather than the vague "this run's own" an earlier version used. |
| `manifest_sha256` | `sha256:82c27a07b12d62a6bc455f58c8c8c112227dd43055a41136ccaca041ca70b770` — identical to TASK-007's delta-A snapshot, because the source delta is identical |
| `item_count` | 121 |
| Normalizer | `normalizer.obf.product`, `addon_version 0.1.0` |
| `output_contract_version` | `0.3` |
| `record_type` | `product`, on every emitted row |

### Counts

`[측정]` `results_emitted 121`, `skipped 0` — `121 + 0 == 121`, the snapshot's own
`item_count`. Every one of the 121 real rows in this delta carried a usable `code`; none was
skipped. This is reported as observed, not smoothed toward an expected split — a run that
skipped nothing is itself worth naming, since it means every one of DP-028 D3's absence
paths for `external_id` went untested by this particular delta (they are tested by
`test_normalizer_obf_product.py`'s fixtures, not by this real run).

### Field presence, per DP-028 D3's four body fields

`[측정]` Measured over the 121 emitted records, from the persisted `normalized_result` rows
themselves (not the raw payload):

| Field | Present | Share |
|---|---|---|
| `display_name` (`product_name`) | 27 / 121 | 22% |
| `brands` (non-empty list) | 22 / 121 | 18% |
| `observed_at` (`last_modified_t`) | 121 / 121 | 100% |
| `has_ingredients = true` | 16 / 121 | 13% |

`[추론]` `observed_at` at 100% and the other three well under half is the sparse shape
`SRC-003` predicted (`product_name` 19/36 sampled) — not a run where every field is
populated, which the packet's own acceptance criterion 3 names as the suspicious outcome to
watch for. `last_modified_t` being universal rather than sparse is new information this run
adds: OBF's mongoexport apparently stamps every row with a modification time, unlike
`product_name` or `brands_tags`.

### `brands_tags`, confirmed

`[측정]` `test_the_brands_tags_prefix_measurement_is_confirmed_or_contradicted` passed:
across the 22 records carrying a non-empty `brands`, 25 individual tag values were present,
and **all 25 carried the `xx:` language prefix** (`xx:Hismile`-shaped). This confirms, from
a run through the installed host rather than from reading the delta file by hand, the
measurement TASK-008's `Review` section recorded from the same two delta files (26/121 rows
of delta A carrying `brands_tags`, 70/70 individual values prefixed `xx:` across both
deltas). The counts differ (22 non-empty records here vs. 26 rows measured there) because
this run's 121-row snapshot is delta A alone and this table counts *non-empty* `brands`
after the add-on's own `_brands` — a source row with `brands_tags: []` counts as present in
the orchestrator's payload-level reading and as absent in this output-level reading. Both
readings measure real data; neither is wrong.

`[결정]` **Not decided here.** Whether Schema 0.3's `brands` field should carry the `xx:`
prefix verbatim (as the add-on does today) or strip it to the bare name is a schema question
for the project owner — TASK-010's packet says so explicitly, and this record states the
measurement rather than resolving it.

### The add-on's behavior on real rows

`[확인 사실]` Nothing found here required touching `handler.py` or `addon.toml`. The
add-on's abstention paths behaved as its own tests already pin: every row's `code` was a
non-blank string (no skip), `product_name` and `ingredients_text` absent rows abstained to
`None`/`false` rather than raising, `last_modified_t` converted on every row, and
`brands_tags` (a list in every present case) was carried forward verbatim, tag order and
all. Per TASK-010's packet, a real row misbehaving would have been reported here and left
unrepaired to protect the independence of TASK-008's attack; that condition was not reached.

### Coexistence with real NAVER rows

Not attempted. `docs/agent-workflow/task-packets/TASK-010-obf-real-snapshot-normalized.md`
allows skipping this when it is not free, and it is not: it would require a second real
capture (`test_naver_real_data.py`'s `--run-network --run-credential`, which additionally
spends a live API quota) landing in the *same* database as this run, which neither this
run's kept-database session nor TASK-007's did. `TestCoexistenceOverOneLineage` in
`test_normalizer_obf_product.py` already covers the structural property with invented
fixtures, as the packet notes.

### Environment for this run

| | |
|---|---|
| Command | `.venv/bin/python -m pytest -q -p no:cacheprovider tests experiments/integrated-p0/tests/test_obf_real_data.py --run-network` |
| Result | `123 passed` in `test_obf_real_data.py` plus `tests`: 12 of this file's tests hit the network (8 from TASK-007's four classes, 4 new from `TestTheNormalizerRunsOnTheRealSnapshot`), the rest are `tests`' own suite collected alongside for `--run-network`'s conftest reason |
| Sandbox | Disabled for this command, same reason TASK-007 recorded: the command sandbox denies reading `.venv/**/certifi/cacert.pem`, which `httpx`'s default SSL context needs |
| Retrieval | Re-fetched both deltas over the network rather than trusting the files already under `var/samples/obf/`, per the packet's instruction; the index had not advanced, so the same two files came back |
| Database | `COSMA_DB_HOST=$PWD/var/postgres`, `COSMA_DB_NAME=cosma_p0`, `COSMA_DB_USER=$(id -un)` |
