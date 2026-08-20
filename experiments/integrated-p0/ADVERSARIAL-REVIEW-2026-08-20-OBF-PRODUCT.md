# ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT — Attack report on TASK-008

- Packet: [`TASK-008-obf-product-normalizer.md`](../../docs/agent-workflow/task-packets/TASK-008-obf-product-normalizer.md)
- Subject: `experiments/integrated-p0/addons/normalizer.obf.product/` (new),
  `experiments/integrated-p0/tests/test_normalizer_obf_product.py` (new)
- Worker revision: **none.** `[확인 사실]` The work is uncommitted and untracked. `git status
  --short -uall` lists `addon.toml` and `handler.py` as `??`, so there is no worker commit to
  diff against and no way to prove that the bytes reviewed here are the bytes the worker ran
  its own verification against, beyond the worker's word and the digests recorded below. Every
  measurement in this report is against the working-tree bytes at the digests in *Baseline*.
- Attacker: `adversarial-reviewer` session, resumed once after a session-limit interruption
- Date: 2026-08-20
- Decision implemented: [DP-028](../../docs/decisions/DP-028-schema-0-3-product-records.md)
- Result: **`PASS`** — all eight packet criteria survived, with **six findings, none blocking
  the packet** and one (F1) blocking a gate *claim* rather than the code. See *Conclusion*.

## Baseline digests and restoration proof

`[측정]` Byte-exact backups were taken before any mutation. Baseline:

```
71156e6fff17d8a78a9a6333d37b8a449d5bbd1456ad8a57836d18483c86a33f  addons/normalizer.obf.product/handler.py
8d3556c56a9084c1cadd5a90880d47081311d069a4efa997fb6a97f7dae2e967  tests/test_normalizer_obf_product.py
aa308cd284632a62ea65a03ea3f21e4eaf1c99c7b7ca241804f32ffeacd030b7  addons/normalizer.obf.product/addon.toml
```

`[측정]` After all 30 mutants, re-measuring the same three files returned the same three
digests. `find experiments/integrated-p0 \( -name '*.bak' -o -name '*.orig' -o -name
'.tmp-*' \)` returned nothing. Only `handler.py` was ever written; the test file and
`addon.toml` were never opened for writing. The mutation driver restores from an in-memory
copy of the original in a `finally` block, so an interrupted run cannot leave a mutant.

## Reproduced worker evidence

| Claim | Command or procedure | Observed result | Evidence |
|---|---|---|---|
| `check-addons.sh` reports `ok` | `./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.obf.product` | `normalizer.obf.product          ok`, exit 0 | reproduced |
| 46 passed on the packet's combined command | `.venv/bin/python -m pytest -q -p no:cacheprovider experiments/…/test_normalizer_obf_product.py tests/environment/test_addon_layer_direction.py` with `COSMA_DB_*` set | `46 passed in 0.77s` | reproduced exactly, **and without `PYTHONPATH`** — the packet's documented command works as written |
| 41 cases in the new file | `pytest -v` on the file alone | `collected 41 items`, `41 passed in 0.72s` | reproduced; the handoff's "41 cases" is correct and its "46 passed" is the combined figure, not a contradiction |
| add-on-wide guards + layer direction | the packet's second pytest block plus `tests/environment/test_addon_layer_direction.py` | `97 passed in 0.19s` | reproduced (worker reported 92 for the four-file subset; 97 includes the 5 layer-direction cases) |
| `ruff` clean | `.venv/bin/ruff check` on the three paths | `All checks passed!` | reproduced |
| `mypy` clean | `.venv/bin/mypy handler.py test file` | `Success: no issues found in 2 source files` | reproduced |
| The determinism mutation goes red | `results.append(` → `results.insert(0, ` in `handler.py` `run` | `1 failed, 40 passed`, killed by `TestItIsDeterministic.test_the_order_follows_the_snapshot` | **reproduced independently** (mutant `M1`); the worker's claim is true as stated |
| The coexistence test ran rather than skipping | `pytest -v -rs` on `TestCoexistenceOverOneLineage` alone, with `COSMA_DB_HOST=$PWD/var/postgres COSMA_DB_NAME=cosma_p0 COSMA_DB_USER=$(id -un)` | `1 passed in 0.67s`, no skip line | **reproduced.** The worker's claim that it executed for real is true |
| `git status --short` shows nothing outside the allowed list | `git status --short -uall -- <addon dir>`; `git diff --stat` | see *Scope* below | reproduced; the worker's characterisation of the three pre-existing tracked modifications is accurate |

### The silent-skip path is real, and I measured it

`[측정]` This was an explicit review item: whether criterion 6 can *appear* covered while never
executing. It can.

```sh
env -u COSMA_DB_HOST -u COSMA_DB_NAME -u COSMA_DB_USER \
  .venv/bin/python -m pytest -q -p no:cacheprovider -rs \
  experiments/integrated-p0/tests/test_normalizer_obf_product.py
```

```
........................................s
SKIPPED [1] …/test_normalizer_obf_product.py:425: no local database configured
  (invalid platform configuration: COSMA_DB_HOST is required but is not set; …)
40 passed, 1 skipped in 0.04s
```

`[추론]` A reader who runs the file without the three environment variables sees `40 passed,
1 skipped` and gets a green line. The count `1 skipped` is visible, but nothing in that output
says that the one skipped case *is* a charter exit criterion. The 0.04s runtime is the only
other tell. `[측정]` With the variables set, the same file reports `41 passed` and the class
runs against a real cluster. Both readings are correct; only one of them establishes criterion
6. This is inherited harness behaviour (`platform_database`'s own `pytest.skip`), as the
worker said, and the test file's module docstring already names it — so it is a property to
record, not a defect the worker introduced. It is recorded here because a gate reader
quoting a bare `pytest -q` line would be quoting a run in which criterion 6 did not execute.

## Mutation battery — can each assertion go red?

`[측정]` 30 mutants of `handler.py`, each applied to a pristine copy, run against the full new
test file, then restored. Driver:
`/tmp/claude-1000/-home-user1-github-prj-Main-cosmai/34cff5ca-c82c-4428-8400-15715a3c0196/scratchpad/mutate.py`
and `mutate2.py` (scratchpad, outside the repository).

**Killed (24).** Each of these is a real assertion doing real work:

| Mutant | Change to `handler.py` | Killed by |
|---|---|---|
| `M1` | `results.append(` → `results.insert(0, ` | `TestItIsDeterministic.test_the_order_follows_the_snapshot` |
| `M2` | `SCHEMA_VERSION = "0.3"` → `"0.2"` | 2 cases in `TestTheEnvelopeAndTheRecord` |
| `M3` | `RECORD_TYPE = "product"` → `"document"` | 2 cases |
| `M5` | swap `results_emitted` and `skipped` in the returned outcome | 10 cases, incl. `TestOutcomeCountsAddUp.test_the_individual_counts_are_pinned…` |
| `M6` | `_display_name` returns `value.strip()` | `TestDisplayName.test_a_present_value_is_carried_exactly_as_sent` |
| `M7` | `_external_id` accepts a blank `code` | `test_a_blank_code_is_skipped` |
| `M8` | `_observed_at` converts numeric strings | `test_a_numeric_looking_string_also_abstains` |
| `M9` | `_brands` returns `sorted(...)` | `test_order_is_preserved_exactly_as_the_source_sent_it` |
| `M10` | `_has_ingredients` requires `len(strip()) > 10` | `TestHasIngredients.test_it_is_not_a_quality_judgement` |
| `M11` | `strftime("%Y-%m-%dT%H:%M:%SZ")` → `moment.isoformat()` | 2 cases in `TestObservedAt` |
| `M12` | body gains `"category": "skincare"` | 2 cases |
| `M13` | `notes` loses `skipped_item_keys` | `test_a_missing_code_is_skipped_and_counted` |
| `M14` | `notes={}` | same |
| `M16` | `_require_language` ignores config | `test_language_is_configuration_and_not_detection` |
| `M17` | `emit_result([])` | 31 cases |
| `M18` | a skipped row is named but `skipped` is not incremented | 6 cases |
| `M19` | `bool` accepted as a timestamp | `test_a_boolean_is_not_treated_as_a_numeric_timestamp` |
| `M21` | `_brands` returns `None` when the source has none | `test_an_absent_brands_tags_is_an_empty_list_not_null` |
| `M22` | `_display_name` coerces a non-string with `str()` | 2 cases |
| `M27` | `skipped_item_keys` as a `list` instead of a `tuple` | `test_a_missing_code_is_skipped_and_counted` (see F5) |

`[추론]` Every acceptance criterion that names a *behaviour* has at least one assertion that
dies when that behaviour is broken. Criterion 3 (determinism), 4 (each absence path, skip
counted and named), and 5 (counts, and a swap detectable) are genuinely load-bearing.
Criterion 5's `TestOutcomeCountsAddUp` even carries its own positive control and explains in
its docstring why addition commuting made the sum test insufficient — the exact reasoning this
repository's prior blocking finding was about, applied correctly and unprompted.

**Survived (4), and what each means:**

| Mutant | Change | Verdict |
|---|---|---|
| `M4` | `source_item_key=item.item_key` → `source_item_key=external_id` | **F2 below.** A real gap in criterion 2's lineage clause. |
| `M15` | reorder the body dict literal's first four keys | **Not a gap.** `PoC Contract 0.1` §5 requires byte-identical results *"after canonical serialization"*, and `domain.store.canonical_body` uses `sort_keys=True`. Key insertion order is by design irrelevant. The attack did not land, for the right reason. |
| `M23` | `emit_result` per item instead of once per run | **Not a gap.** Behaviourally equivalent; the host buffers either way. |
| `M24` | `_parse` returns `{}` instead of `None` for a non-dict payload | **F6 below (low).** The row is still skipped — via the "no usable code" branch rather than the "payload is not a JSON object" branch — so only the logged *reason* differs, and no assertion covers the reason. |

## Determinism, measured rather than trusted

`[측정]` The worker claimed determinism; the packet's own tests assert it in-process only, and
`test_two_runs_over_one_snapshot_produce_equal_bodies` compares dicts (order-insensitive), not
bytes. Both stronger readings were measured directly.

Test suite across seven hash seeds:

```sh
export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"
for seed in 0 1 7 42 1337 99991; do
  PYTHONHASHSEED=$seed .venv/bin/python -m pytest -q -p no:cacheprovider \
    experiments/integrated-p0/tests/test_normalizer_obf_product.py | tail -1
done
```

`[측정]` `41 passed` at every one of `0, 1, 7, 42, 1337, 99991`.

Byte-level probe (scratchpad `determinism_probe.py`, a fresh interpreter per seed, three-item
snapshot including one skipped row, bodies serialized in *insertion* order so that a key-order
drift would show):

`[측정]` digest `738a73c3711ef450eb93a0070381102214887fe61a7bdd8673d897a8baa645b2` at all seven
of `0, 1, 7, 42, 1337, 99991, 123456`; emitted key order identical every time
(`schema_version, record_type, external_id, language, display_name, brands, observed_at,
has_ingredients`); `brands` order `["zzz","aaa","mmm"]` preserved unsorted; `results_emitted=2
skipped=1 skipped_item_keys=['k3']` every time.

`[추론]` Determinism holds in the strong reading. `handler.py` contains no iteration over a
`dict` or `set` — every field access is a keyed `row.get(...)` — no clock read (`datetime` is
used only as `fromtimestamp` of a source value), and no random source. The claim is sound and
the mechanism is visible, not accidental.

## Coexistence, and what its test actually proves

`[측정]` The test executes for real (reproduced above). The property it names also holds.
But **the test cannot go red for the clause "with no row updated in place"**, for two
independent reasons:

1. `[확인 사실]` There is no UPDATE path to violate. `grep -ci "update normalized_result"
   experiments/integrated-p0/domain/store.py` → `0`, and
   `domain/migrations/0003_normalized_result.sql` says so in its own header: *"There is no
   UPDATE path and no 'current' flag."* Coexistence is a schema property, not a runtime one.
2. `[측정]` The three rows the test inserts differ in `addon_id` **and** `source_item_key`
   **and** `output_contract_version`. The unique index is `(snapshot_id, addon_id,
   addon_version, output_contract_version, source_item_key)`. Three rows differing in three of
   those five columns could not collide under any implementation, so `assert len(rows) == 3`
   is asserting that three inserts insert three rows.

`[측정]` I ran the sharper case the criterion deserves against a scratch database (scratchpad
`coexist_probe.py`; it creates `cosma_attack_<hex>`, migrates it, and drops it — output
`scratch database dropped: cosma_attack_284addfa`):

```
P1  same source_item_key "8800000000099", normalizer.naver.blog@0.1 and
    normalizer.obf.product@0.3  -> rows=2  versions=['0.1','0.3']  types=['document','product']
P1b one normalizer, two output_contract_versions, one key -> rows=3
P2  the identical tuple a second time -> REFUSED by UniqueViolation on
    "normalized_result_one_per_run_and_item"
final row count: 3
update-normalized_result statements in domain/store.py: 0
```

`[추론]` DP-019 D3's coexistence is **true and stronger than the packet's test shows**: a `0.3`
result coexists with a `0.1` result over the *same* `source_item_key`, two contract versions of
the same normalizer coexist over one key, and a genuine rerun is refused rather than silently
doubling or replacing. So criterion 6's substance holds — verified here independently — while
the assertion the packet ships is the weak version of it. Recorded as **F3**, non-blocking:
the property is established, just not by that test.

## Findings

### F1 — `brands_tags` is not a field SRC-003 measured, and the test file says it is. Severity: **high, blocking a gate claim, not the packet.** Failure class: `evidence`

**Claimed.** `test_normalizer_obf_product.py`'s module docstring: *"Every payload below
reproduces the shape SRC-003 measured — a `code` that looks like a barcode, sparse
`product_name`, **`brands_tags` as a list**, `last_modified_t` as Unix seconds."* DP-028 D3's
table: `brands` ← *"`brands_tags`, the source's own list, order preserved."*

**Why it is false.** `[확인 사실]` SRC-003 never measured `brands_tags` as a response field.

- Its presence measurements name **`brands`**, not `brands_tags`:
  *"`product_name` 19/36, `brands` 25/36, `ingredients_text` 12/36…"* and *"`product_name`
  82/100, `brands` 87/100"* (SRC-003 §Missing and invalid values).
- The three field lists it requested from the API (`F`, `G`, `H` at SRC-003 lines 468, 472,
  476) each name `brands`. None names `brands_tags`.
- `brands_tags` appears in SRC-003 **only as a search facet parameter** —
  `'brands_tags=cosrx'`, `'brands_tags=laneige&categories_tags_en=toner'` — i.e. as query
  syntax, never as a measured response shape.
- SRC-003 also records that the field documentation cannot settle it: *"`…/data-fields.txt`
  returns `404`… The citation above is therefore the sibling Open Food Facts file, and whether
  every OBF-specific field matches it is `UNKNOWN`."*

`[추론]` So the shape of `brands_tags` — that it exists in the export at all, and that it is a
JSON list of strings — is an **assumption**, and the test file presents it as a measurement.
That is evidence named for a source that could not have produced it, which is the failure class
`AGENTS.md` and this repository's review history single out.

**Why it matters beyond the docstring.** `[측정]` The add-on reads `row.get("brands_tags")` and
`_brands` returns `[]` for anything that is not a `list`. `[추론]` If the real export carries
brands as `brands` (a comma-joined string) and not as `brands_tags`, then **every record from
TASK-007's real run carries `brands: []`**, and no test in this file can tell that apart from
"the source has none", because D3 gives `brands` no null state to abstain into. One of the four
body fields would be structurally dead and the suite would stay green. `[측정]` I confirmed the
silent-collapse behaviour directly: `brands_tags` as a string `"brand-alpha"` and as a dict
both yield `brands: []` with no skip, no note, and no log line.

**Falsification / how to settle it.** TASK-007's real capture. If a real OBF export row carries
`brands_tags` as a list of strings, F1 reduces to a documentation defect (the docstring should
say `[가설]`, not "SRC-003 measured"). If it does not, the `brands` field of Schema 0.3 has no
producer and DP-028 D3's `brands` row needs a source-field correction.

**Reproduction.**
```sh
grep -n "brands" experiments/source-probes/SRC-003-open-beauty-facts.md
# every hit is either `brands` (measured) or `brands_tags=` (a facet parameter)
```

**This is not the worker's invention.** DP-028 D3 handed it the field name, and the packet
repeated it. The worker's error is only in attributing it to SRC-003 as a measurement.

### F2 — Criterion 2's lineage clause passes by fixture coincidence. Severity: **medium.** Failure class: `evaluation`

**Claimed.** Acceptance criterion 2: *"…and `source_item_key` traces to the sealed item."*

**Why it is unproven.** `[측정]` Mutant `M4` replaces `source_item_key=item.item_key` with
`source_item_key=external_id` in `handler.py`. **All 41 tests still pass.** The reason is the
fixture: `a_snapshot_item()` defaults `item_key` to `str(payload.get("code", "item"))`, so in
every emitted-row case the snapshot key and the `code` are the same string by construction.
The one test that names the clause,
`test_the_external_id_is_the_code_and_matches_the_lineage_key`, asserts both sides of an
identity the fixture created. Only the *skipped*-row cases use a distinct `item_key`
(`"raw-missing-code"`, `"raw-bad"`), and a skipped row emits nothing.

`[추론]` This matters because `item_key` and `code` are **not** the same thing in the pipeline.
`importer.local.jsonl` sets `item_key=str(key)` where `key = entry.get(key_field)` and
`key_field` is **configuration**. Configure it to anything but `code` and a handler that used
`external_id` would break lineage silently. `str(key)` also coerces: a JSON-numeric `code`
becomes the string `"8801234567890"` as an `item_key`, while this normalizer skips that same
row as a non-string `code` — so the two add-ons already disagree about that input.

**Mitigation that keeps this non-blocking.** `[확인 사실]` `addon_host` enforces the clause
independently: `_check_lineage` in `experiments/integrated-p0/addon_host/capabilities.py`
raises `AddonOutputInvalid` for *"result {key!r} names an item this snapshot does not hold"*,
and `_check_outcome` raises when `outcome.results_emitted != len(self._results)`. `[추론]` So
the platform, not the add-on, is what actually holds criterion 2's lineage half at runtime —
which is the correct place for it. **But this packet's tests never exercise the host at all**:
every case builds a `NormalizeContext` by hand. The criterion is therefore verified by neither
the add-on's tests nor by anything this packet runs. Note the polarity: the 2026-08-18 blocking
finding was a criterion satisfied by the add-on's cooperation instead of the platform; this is
a criterion satisfied by the platform while the packet's evidence points at the add-on.

**Smallest fix (for the follow-up packet, not for me):** one case whose `item_key` is
deliberately unequal to its `code`, asserting `source_item_key == item_key` and
`body["external_id"] == code` separately. `M4` would then die.

**Reproduction.** In `handler.py`, `source_item_key=item.item_key` →
`source_item_key=external_id`; run the file; observe `41 passed`. Restore.

### F3 — Criterion 6's assertion cannot go red for the clause it names. Severity: **medium.** Failure class: `evaluation`

Measured in full under *Coexistence* above. `[추론]` The property is true and I verified it
independently against a real cluster in its hard form; the shipped assertion is the easy form,
and the "no row updated in place" clause is unfalsifiable through `DomainStore` because no
UPDATE path exists. A reader of the P1 Entry Gate should be told that coexistence rests on
`0003_normalized_result.sql`'s absent-UPDATE design plus the unique index, not on this test.

### F4 — Three of the six frozen `[가설]` are labelled where a test reader will not find them, and one test misattributes an assumption to DP-028. Severity: **medium.** Failure class: `assumption`

`[측정]` The review question was whether each assumption is encoded *as* an assumption a later
reader can find, or silently made to look decided. Per gap:

| Gap | Labelled `[가설]` in `handler.py` docstring? | Labelled at the assertion? | Verdict |
|---|---|---|---|
| 1. `display_name` stored untrimmed, trimmed only for the presence test | yes, with a falsification condition | **yes** — `test_a_present_value_is_carried_exactly_as_sent` carries the `[가설]` and its falsifier | **Correct.** This is the model the other five should follow. |
| 2. whitespace-only `code` treated as absent | yes, with a falsification condition | **no** — `test_a_blank_code_is_skipped` has no docstring, and its **class** docstring says *"DP-028 D3: `code` is never null in the output"* | **Finding.** See below. |
| 3. numeric strings rejected for `observed_at` | yes, with a falsification condition | **the label is on the wrong test** — `test_a_non_numeric_value_abstains_rather_than_raising` (the *uncontested* case, `"not-a-number"`) carries the `[가설]`; `test_a_numeric_looking_string_also_abstains`, the case that actually pins the contested reading, has no docstring at all | **Finding.** |
| 4. the ISO literal `%Y-%m-%dT%H:%M:%SZ` | **no label anywhere** | no | **Finding.** See below. |
| 5. what belongs in `NormalizeOutcome.notes` | not labelled; stated as fact | partially — only `skipped_item_keys` is asserted | **Finding.** See F5. |
| 6. skipped item keys in `notes` | stated as fact | asserted | **Packet-directed, not a worker assumption** — the packet's *Included* section asks for a skipped row to be "`skipped`, counted, and named in `notes`". Correctly implemented. The *container type* is the problem: F5. |

**Gap 2 is the sharpest of these.** `[확인 사실]` The worker's own handoff says D3's `code` row
*"only names the fully-absent case"* and does not mention blank strings. Yet
`TestARowWithNoUsableCodeIsSkipped`'s class docstring cites DP-028 D3 as the authority for the
whole class, and `test_a_blank_code_is_skipped` sits inside it with no docstring. `[추론]` A
reader of the test file alone concludes that skipping a whitespace-only `code` is a `[결정]`
recorded in DP-028 D3. It is not; it is the worker's `[가설]`, findable only in `handler.py`'s
module docstring. That is precisely "a `[가설]` that reads as a `[결정]`", and it is made worse
by a citation to a decision that does not say it.

**Gap 4, the ISO literal, is unlabelled and undocumented.** `[확인 사실]` DP-028 D3 says
*"Unix seconds → ISO-8601 UTC"*. `[추론]` `moment.isoformat()` yields
`2025-01-01T00:00:00+00:00`, which is equally valid ISO-8601 UTC, so the `Z` suffix is a choice
that D3 does not make. `[측정]` Mutant `M11` (`strftime` → `isoformat`) is killed by two tests,
so the choice *is* pinned — but nothing anywhere records that it was a choice, or why `Z` over
`+00:00`. `[측정]` No precedent settles it either: the only other normalizer emitting a time,
`normalizer.naver.blog`, emits a bare `yyyy-mm-dd` date via `_iso_date` and never a datetime,
and `DP-019`'s table says only *"ISO-8601 date"*. `[추론]` So this is the first datetime format
in the normalized schema, decided in a `strftime` literal with no `[가설]` label, no
Decision-Packet line, and a test that reads as though the format were contracted.

`[추론]` Classification: none of F4 is an implementation defect. Every reading the worker chose
is defensible, each is pinned by a killing test, and the worker *did* raise three of them in
its handoff — which is the stopping condition working as designed. The finding is that the
tests freeze six assumptions while only one of them announces itself as an assumption at the
place a reader will look.

### F5 — `notes` over-pins a container type its own JSON contract does not preserve, and two of its three keys are untested. Severity: **low-medium.** Failure class: `specification`

**Claimed.** `test_a_missing_code_is_skipped_and_counted` asserts
`outcome.notes["skipped_item_keys"] == ("raw-missing-code",)` — a Python **tuple**.

**Why it is fragile.** `[측정]` `NormalizeOutcome.to_json()` does `dict(self.notes)` and
`from_json` reads it back through `_require_mapping`; JSON has no tuple. Measured
(scratchpad `notes_roundtrip.py`):

```
in-process notes:                   ('raw-missing-code',)   assertion -> True
after to_json / json / from_json:   ['raw-missing-code']    assertion -> False
wire form: {"results_emitted": 0, "skipped": 1,
            "notes": {"schema_version": "0.3", "language": "en",
                      "skipped_item_keys": ["raw-missing-code"]}}
```

`[추론]` The assertion holds only for an in-process outcome. Any consumer that reads the
persisted or transported form sees a list, and the same equality goes red. Mutant `M27` — the
handler returning a `list` instead of a `tuple`, which is what every downstream reader will in
fact see — is **killed** by this test. So the test forbids the shape the contract produces.
`[측정]` `tuple`/`list` is the only difference `M27` introduces; the wire bytes are identical.

`[측정]` Separately, mutant `M26` removes `"schema_version"` and `"language"` from `notes`
entirely and **all 41 tests pass**. Only `skipped_item_keys` is asserted. `[추론]` So "what
belongs in `NormalizeOutcome.notes`" is answered by this add-on in three keys, of which one is
packet-directed and pinned and two are undocumented, unlabelled, and unverified.

### F6 — Two distinct skip reasons are not distinguished by any assertion. Severity: **low.** Failure class: `evaluation`

`[측정]` Mutant `M24` makes `_parse` return `{}` rather than `None` for a payload that parses
but is not an object. All 41 tests pass: the row is still skipped and still counted, but via
the `"no usable code"` branch instead of the `"payload is not a JSON object"` branch, so the
`normalize.skipped` log line now carries a reason that is true of the code and false of the
payload. The test harness passes `log=lambda event, fields: None`, so no case observes any log
line. `[추론]` Low severity — the counts and the skip are correct either way — but the packet
puts weight on a skip being "named", and the *reason* it is named with is unasserted.

### Attacks that did not land

`[측정]` Recorded because a padded finding list is worse than a short one.

- **Determinism, strong reading.** Seven hash seeds, seven fresh processes, identical
  insertion-order digest. Held.
- **Key-order determinism (`M15`).** Survived, and correctly so: `canonical_body` uses
  `sort_keys=True`, and `PoC Contract 0.1` §5 requires byte-identity *after canonical
  serialization*. Held for the right reason.
- **DP-028 D5, the prohibition.** I looked for any field, branch, or default that needs to know
  what a product is. There is none. `[측정]` `handler.py` has eight body keys and five pure
  helpers; the only mentions of "category", "taxonomy", "canonical", or "resolve" anywhere in
  the add-on are in the docstring line *stating the prohibition*. No import beyond `json`,
  `datetime`, `typing`, and `addon_api`. `_brands` carries the source list forward and does not
  dedupe, sort, lowercase, or map it. Mutant `M12`, which adds `"category": "skincare"` to the
  body, is killed by two tests. `[추론]` **D5 holds, and H2 of DP-028 is not falsified**: the
  extraction was written without a category, an ingredient taxonomy, or a brand identity.
- **`has_ingredients` as presence, not quality (D4).** `return isinstance(value, str) and
  bool(value.strip())` — no length, no language, no ingredient count. Mutant `M10` (a
  10-character threshold) is killed by `test_it_is_not_a_quality_judgement`, a test that exists
  for exactly this and uses a one-word ingredient text. The line holds.
- **Counts.** `results_emitted + skipped == item_count` and the swap control both go red
  (`M5`, `M18`); the host additionally refuses `results_emitted != len(results)`. Held.
- **Layer direction.** The add-on imports `addon_api` and nothing else in this project;
  `tests/environment/test_addon_layer_direction.py` passes. Held.
- **Numeric edge cases on `observed_at`.** `NaN`, `Infinity`, `-Infinity`, `10^21`, and a
  201-bit integer all abstain to `None` rather than raising (`ValueError`/`OverflowError`
  caught). `0` → `1970-01-01T00:00:00Z`; `-2208988800` → `1900-01-01T00:00:00Z`; a fractional
  float truncates to the second. No crash, no invented value. Held. (No test covers these; the
  behaviour is correct anyway.)
- **Malformed payloads.** Empty bytes, `not json`, `[1,2,3]`, `null`, invalid UTF-8
  (`b'{"code":"\xff\xfe"}'`), `{"code": null}`, and a nested `product_name` object all skip or
  abstain without raising. Held.

### One robustness gap found while probing, which is not this add-on's to own

`[측정]` A payload containing a **lone surrogate escape** — `{"code":"a\ud800"}` — is accepted
by `json.loads` (`_parse` catches `UnicodeDecodeError` on the *byte* decode, but this is a
valid escape sequence producing an unencodable `str`). The handler emits a record. The failure
then surfaces outside the add-on, in `domain.store.canonical_body`:

```
emitted, but canonical_body RAISED UnicodeEncodeError:
  'utf-8' codec can't encode character '\ud800' in position 49: surrogates not allowed
```

`[추론]` One malformed row would abort a whole normalize run at the persistence boundary rather
than being skipped and counted. `[확인 사실]` This is **not** introduced by TASK-008:
`canonical_body` has no surrogate guard, and `normalizer.naver.blog` carries `title` and
`excerpt` verbatim in exactly the same way, so the exposure predates this add-on and belongs to
`domain/store.py`. `[가설]` Whether a real OBF export can contain such a row is unmeasured;
SRC-003 says the export originates from `mongoexport`, which makes it worth checking rather
than dismissing. Recorded here as a platform-level follow-up, deliberately not counted among
the six findings against this packet.

## Scope and decision-boundary review

- **Allowed-file compliance: `PASS`.** `[측정]` `git status --short -uall --
  experiments/integrated-p0/addons/normalizer.obf.product/` lists exactly `addon.toml` and
  `handler.py` (the directory's `__pycache__` is ignored by `.gitignore:19`). `git diff --stat`
  shows three tracked modifications — `contracts/experimental/POC-CONTRACT-0.1.md`,
  `docs/project-state.md`, `docs/agent-workflow/task-packets/TASK-006-…md` — all of which are
  the orchestrator's and none of which is attributable to this task, exactly as the worker
  described. `experiments/integrated-p0/tests/test_obf_real_data.py` and
  `…/evidence/obf-dataset/` belong to a concurrent TASK-007 session and are not this worker's.
  Nothing under `addon_api`, `addon_host`, `platform_core`, `domain/`, `contracts/`, or
  `normalizer.rule.baseline/` changed.
- **The deleted `README.md`: correct call, and correctly recorded.** `[측정]` The worker's
  precedent claim is exact — of the eight other add-ons, `collector.naver.blog` and
  `normalizer.conformance` keep a `README.md`; the other six do not. `[확인 사실]`
  `addon-authoring.md` documents that `addon_kit new` generates one but imposes no requirement
  to keep it, and `check-addons.sh` passes without it. `[추론]` Deleting a file absent from the
  packet's Allowed-files list, rather than silently adding it, is the packet boundary working;
  the file was never committed, so there is nothing to verify beyond the current absence.
- **Accepted-decision compliance: `PASS` with F1's caveat.** DP-028 D1 (third member), D2
  (no existing normalizer bumped — `[측정]` no other add-on's files changed), D3 (four body
  fields plus the envelope's `external_id`, nothing more — pinned by an exact-set assertion),
  D4 (presence, not quality), D5 (no product identity work) all hold. F1 concerns whether D3's
  `brands` **source field** is the one SRC-003 measured, which is a question about D3 and
  SRC-003, not about the implementation of D3.
- **Unanswered consequential direction: none blocking.** F4's gaps 2, 3, and 4 and F5's
  undocumented `notes` keys are ambiguities the worker resolved with stated `[가설]` rather than
  silently, which is what `AGENTS.md` asks. None of them is a product goal, scope, schema,
  boundary, or policy question. The `[가설]` in F1, if TASK-007 refutes it, *would* become a
  D3 correction and therefore a Decision-Packet matter.
- **Prohibited material exposure: none.** `[측정]` No credential, cookie, token, or URL
  requiring one appears in the add-on or its tests; `[declares]` is empty and
  `test_it_declares_no_host_endpoint_credential_or_stream` pins it;
  `test_addon_credential_hygiene.py` passes. No real Open Beauty Facts row is present — the
  fixture's `8801234567890` and `"Example Whitening Cream"` are invented and the test file says
  so, satisfying DP-022 and DP-027 D3. The Korean strings in the coexistence test's `0.1`/`0.2`
  bodies are invented placeholders for other record types, not source data.
- **The planner error the orchestrator already corrected** (DP-028 D3 / TASK-008 saying "five
  body fields" where the table's first row is the envelope's `external_id`) is treated as
  handled and is not re-reported.

## Schema 0.3 has no real-data producer yet, and F1 cannot be settled in this tree

`[측정]` TASK-007 completed while this review was in progress. Its evidence record,
`experiments/integrated-p0/evidence/obf-dataset/README.md`, was read (not modified) to see
whether it settles F1 and what it establishes about Schema 0.3. Two results, both from
`grep` over that file:

1. **It names `brands`, not `brands_tags`.** `[확인 사실]` Its only field enumeration reads
   *"`code`, `product_name`, `brands`, timestamps, `rev` — no credential-shaped field"*.
   `grep -niE "brands_tags"` over the file returns nothing, as it does over
   `tests/test_obf_real_data.py`. `[추론]` This is a **second** independent document about
   this source naming `brands` where DP-028 D3 and this add-on read `brands_tags`. It
   strengthens F1 but does not close it: the line is about redaction of what was captured,
   and no real row is committed (the directory holds `README.md` only, correctly — DP-027 D3
   and the recorded `.jsonl` digest keep the rows out of the tree). So the decisive question —
   does the export carry a `brands_tags` array at all — **remains `[가설]` and cannot be
   answered by any artifact currently in this repository.**

2. **No real row has ever passed through this add-on.** `[확인 사실]`
   `grep -niE "obf\.product|0\.3|normaliz"` over TASK-007's evidence record returns **zero
   hits**. That capture ends at Raw and a sealed snapshot; it does not run a normalizer and
   does not mention Schema 0.3.

`[추론]` So the two halves of the dataset flow exist and have never been joined: TASK-007
produced real Raw and a real sealed snapshot from a real delta export, and TASK-008 produced
the only normalizer that can emit Schema 0.3, verified exclusively against structural
fixtures **invented by the same worker that wrote the handler**. Every `product` record that
has ever existed came from `a_row()` in the test file.

`[결정]` This does **not** reduce the packet result. TASK-008's *Excluded* section says so in
as many words — *"Real data, network access, and `/var/`. TASK-007 owns the real run."* — and
an attacker may not fail a packet for a scope its planner removed. It is recorded because it
is the single fact a P1 Entry Gate reader most needs and neither packet states: the union's
third member is implemented and well tested, and it is untested against the source it exists
for.

## What this review did not measure

`[측정]` This session was interrupted twice — once by a session limit, once by a `529
Overloaded` — and the following were either out of scope or not reached. None of them is a
qualifier on the `PASS`; each is a named gap.

- **The add-on through `addon_host`, end to end.** Not measured, and no test in this packet
  measures it. Every case in the new file builds a `NormalizeContext` by hand. F2's
  mitigation — that `_check_lineage` and `_check_outcome` hold criterion 2's lineage clause
  at runtime — is `[확인 사실]` **read from `addon_host/capabilities.py`, not `[측정]` from a
  run.** I did not execute the host path, so I did not prove that the host is wired into a
  normalize job such that those two guards fire. A follow-up should measure it rather than
  inherit my reading of it.
- **A real Open Beauty Facts row through this add-on.** Not measured; excluded by the packet
  and, per the section above, not available in this tree.
- **Whether a real export row can contain a lone surrogate.** The crash is `[측정]`; its
  reachability from real data is `[가설]`.
- **`addon_kit run`.** Not exercised, by me or by the worker. Per `addon-authoring.md` it is
  not integration evidence for a normalizer in any case.
- **The full test suite.** Deliberately not run: the instructions forbid it while another
  session holds the database.
- **Mutants of the test file.** I mutated `handler.py` only (30 mutants). I did not mutate
  the test file to check that each test's *fixture* can reach the branch it claims — F2 is
  the one instance of that class I found, and I found it through a handler mutant rather than
  a systematic fixture audit. A more complete review would audit all 41 fixtures the way F2's
  was audited.

## Conclusion

**`PASS`.** All eight named acceptance criteria survived the attacks performed, and I could not
break the implementation. `[추론]` The implementation is, on the evidence, the strongest add-on
I have attacked in this tree: 24 of 30 mutants die, every abstention path has an assertion that
kills its mutant, criterion 5 ships its own positive control with a written explanation of why
the sum test alone was insufficient, determinism holds across seven hash seeds and seven
processes at the byte level, and DP-028 D5 is respected without a single field, branch, or
default that needs to know what a product is — so DP-028's H2 stands unfalsified.

What the pass does **not** cover:

- **F1** is the one finding a gate reader must see. The `brands` field's source name is an
  assumption presented as an SRC-003 measurement, and if it is wrong then one of Schema 0.3's
  four body fields is structurally dead in every real record while the suite stays green.
  Nothing in this packet can settle it, and — measured above — **neither does TASK-007's
  completed capture**, which names `brands` and commits no row. F1 is open and currently
  unanswerable inside this repository.
- **F2** and **F3** are the two criteria whose *tests* prove less than their wording. Both
  underlying properties hold — I verified lineage enforcement in `addon_host._check_lineage`
  and coexistence against a real cluster in its hard form — but a reader who trusts the two
  assertions rather than those two independent facts is trusting the wrong thing.
- **F4** and **F5** are documentation and specification debt, not defects. Six readings are
  frozen into tests; one of them announces itself as a `[가설]` where a test reader will find
  it. One test cites DP-028 D3 for a rule D3 does not contain.

`[추론]` None of the six is a reason to rework the add-on. F1 is a reason not to write "the
dataset half is closed with all four body fields populated" into the gate — which is also what
DP-028 D6 already says, in different words. And the section above is a reason not to write
"Schema 0.3 has a producer proven on the selected dataset": it has a producer proven on
invented rows, over a real snapshot it has never been pointed at.

## Required follow-up

- **New or revised packet:**
  1. **F1, first and cheapest.** Read TASK-007's real capture for `brands_tags`. If present as
     a list: correct the test docstring to `[가설]` and stop citing SRC-003 for it. If absent:
     a Decision Packet correcting DP-028 D3's `brands` source field, and a decision about what
     `brands` means when the export's field is `brands` (a comma-joined string).
  2. **F2.** One test case whose `item_key` differs from its `code`, so that mutant `M4` dies.
     Optionally one host-level case, so that some test in this packet's lineage exercises
     `_check_lineage` rather than relying on it unseen.
  3. **F3.** Extend `TestCoexistenceOverOneLineage` to a shared `source_item_key` across two
     contract versions, and assert the rerun `UniqueViolation`. Both behaviours are already
     true (measured above); the test should say so.
  4. **F4/F5.** Move each `[가설]` label onto the assertion that pins it; remove DP-028 D3's
     citation from the blank-`code` class docstring; label the `Z`-versus-`+00:00` choice, or
     record it in a contract line since it is the schema's first datetime format; relax
     `skipped_item_keys` to a sequence comparison and assert the two unasserted `notes` keys.
  5. **Platform-level, separate from TASK-008.** A surrogate guard in
     `domain.store.canonical_body`, or a documented decision that a lone surrogate is a
     permanent failure of the run. `normalizer.naver.blog` has the same exposure.
- **Open Question or Decision Packet update:** OQ-003 gains the datetime-format question (F4
  gap 4) and the `notes` content question (F5). A DP-028 D3 correction depends on F1's outcome.
- **Project State or contract update:** `PoC Contract 0.1` §5 currently reads *"No installed
  add-on emits a `product` record yet… a reader should not take it as evidence that the dataset
  half of §1 has run."* On acceptance of this packet the first clause becomes false and needs
  editing; the second remains true until TASK-007 produces the run. `[추론]` DP-028 D6 and
  DP-027 D2 (zero Korean sunscreen and toner rows) both still bound what this add-on's
  existence may be claimed to prove.

## Where this file belongs

Beside the experiment it attacks. Link it from
[`TASK-008`](../../docs/agent-workflow/task-packets/TASK-008-obf-product-normalizer.md)'s
`Review` section — which this attacker did not edit, per its packet constraints.
