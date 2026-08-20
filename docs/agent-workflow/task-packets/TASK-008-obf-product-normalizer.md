# TASK-008 — `normalizer.obf.product@0.1`, and the third member of the union

- Status: `WORKER_DONE`
- Phase: P0-B, charter closure
- Planner: orchestrator session, 2026-08-20
- Worker: `addon-author`
- Attacker: `adversarial-reviewer`
- Orchestrator: project owner's session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

An installed add-on turns a sealed snapshot of Open Beauty Facts product rows into
`Normalized Schema 0.3` records with `record_type: "product"` — deterministically, abstaining
wherever the source is silent, and deciding nothing about what the product is.

`[확인 사실]` [DP-028](../../decisions/DP-028-schema-0-3-product-records.md) is the accepted
decision behind this packet. It fixes the record type, the body fields, and what the
add-on may not do. This packet implements it and does not re-open it.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §4 (DP-028), §5 hypothesis 5 —
  whose strong form is already refuted and whose weak form this is a third test of
- Accepted decisions: [DP-028](../../decisions/DP-028-schema-0-3-product-records.md) D1–D6,
  [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md) (envelope,
  `normalized_result`, determinism, coexistence),
  [DP-021](../../decisions/DP-021-schema-0-2-trend-points.md) (the union and D5's
  no-false-version-bump rule), [DP-022](../../decisions/DP-022-structural-fixtures.md)
  (a fixture reproduces structure and carries no content),
  [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md) (no product
  semantics in P0), [DP-027](../../decisions/DP-027-dataset-standard-and-share-alike.md) D3
  (P0 publishes nothing built from this source)
- Contracts: [`CONTRACT-ADDON@1.3`](../../../contracts/experimental/CONTRACT-ADDON-1.3.md);
  [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §5
- Open Questions: [OQ-003](../../open-questions/OQ-003-normalization-protocol.md),
  [OQ-013](../../open-questions/OQ-013-addon-responsibility-boundary.md)
- Owner decisions required: `none`
- Required evidence or environment: `docs/conventions/addon-authoring.md`;
  [`SRC-003`](../../../experiments/source-probes/SRC-003-open-beauty-facts.md) for the
  measured field presence rates. No network and no credential. A database is needed only for
  the coexistence test.

## Scope

### Included

- A new add-on `experiments/integrated-p0/addons/normalizer.obf.product/` — `addon.toml` and
  `handler.py` — with `kind = "normalizer"`, `output_contract_version = "0.3"`, and a
  `language` config field defaulting to `en`. `[측정]` DP-028 records why `en`: 0/36 rows
  carried `product_name_ko` and no Hangul appeared in any sampled name. It is a stated
  configuration value, never detected (DP-019 D2).
- The body fields exactly as DP-028 D3's table fixes them, on top of the envelope every
  record carries: `schema_version`, `record_type`, `external_id`, `language`. `[확인 사실]`
  An earlier revision of this line called them "the five body fields", which counted the
  envelope's `external_id` as a body field; the worker flagged it and DP-028 D3 now says
  four. No field changed.
- **Abstention where the source is silent.** `display_name` and `observed_at` are `null`
  when the source omits them; `brands` is an empty list; a row with no usable `code` is
  `skipped`, counted, and named in `notes` — never invented, never guessed. `[측정]` This is
  the ordinary case, not the edge: `product_name` was present in 19 of 36 real rows.
- `has_ingredients` as a **presence** flag over `ingredients_text` (DP-028 D4).
- Tests in `experiments/integrated-p0/tests/test_normalizer_obf_product.py`:
  - determinism — the same snapshot and version produce byte-identical results;
  - each absence path, asserted individually rather than through one all-null row;
  - a row without `code` is skipped and the count is asserted;
  - `brands` preserves the source's order;
  - `observed_at` converts Unix seconds to ISO-8601 UTC, and a non-numeric value abstains
    rather than raising;
  - **coexistence** — a `0.3` result stands beside a `0.1` and a `0.2` result over one Raw
    lineage without either being replaced (DP-019 D3, and a charter exit criterion).
- **Structural fixtures, built inline in the test file.** DP-022's rule applies: reproduce
  the shape observed in `SRC-003` — a `code` that looks like a barcode, sparse
  `product_name`, `brands_tags` as a list, `last_modified_t` as Unix seconds — and carry no
  row anyone actually contributed. DP-027 D3 keeps P0 publishing nothing from this source,
  so no real row is committed even though ODbL would permit it with obligations.

### Excluded

- **`normalizer.rule.baseline` and its tests.** An attacker is reviewing that add-on in a
  separate session. Do not read from it by copying, do not edit it, and do not run its suite.
- Any product, category, ingredient, or brand **identity** work: no category field, no
  ingredient parsing, no brand resolution, no canonicalization. DP-026 assigned all of it to
  P1, and DP-028 D5 forbids it here by name.
- Any quality judgment. This add-on reshapes and abstains; it does not report violations.
  That is `rule-baseline`'s job and it is out of scope in both directions.
- Any change to `addon_api`, `addon_host`, `platform_core`, `domain/`, or any migration.
  `normalized_result` already holds `body`, `notes`, and a schema version string.
- Any change to a contract, a Decision Packet, or `project-state.md`.
- Bumping `normalizer.naver.blog` or `normalizer.naver.trend`. DP-028 D2: a new version
  number on identical bytes is the version axis saying something false.
- Real data, network access, and `/var/`. TASK-007 owns the real run.

### Allowed files

- `experiments/integrated-p0/addons/normalizer.obf.product/addon.toml` (new)
- `experiments/integrated-p0/addons/normalizer.obf.product/handler.py` (new)
- `experiments/integrated-p0/tests/test_normalizer_obf_product.py` (new)
- this packet's `Status` line and `Worker handoff` section

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- `experiments/integrated-p0/addons/normalizer.rule.baseline/**` and its test file
- every other existing add-on, `addon_api`, `addon_host`, `platform_core`, `domain/`
- `contracts/**`, `docs/decisions/**`, `docs/project-state.md`
- any real Open Beauty Facts row, in the fixture or anywhere else

## Acceptance criteria

1. `./scripts/check-addons.sh` reports the new add-on `ok`, and
   `tests/environment/test_addon_layer_direction.py` still passes — the add-on imports
   `addon_api` and nothing else in this project.
2. Every emitted record carries the full envelope with `schema_version = "0.3"` and
   `record_type = "product"`, and `source_item_key` traces to the sealed item.
3. Determinism is asserted in a way that could go red: mutate the emission order or a field
   and show the test fails, then restore. State this in the handoff.
4. Each absence path has its own assertion, and no assertion passes because two defects
   cancel. A row missing `code` is skipped, counted, and named.
5. `NormalizeOutcome`'s counts are asserted and add up: `results_emitted` plus `skipped`
   equals the snapshot's item count, and a deliberate swap of the two goes red.
6. The coexistence test shows a `0.3` result beside `0.1` and `0.2` results over one lineage,
   with no row updated in place.
7. `ruff` and `mypy` are clean on the three new files.
8. No file outside the allowed list is modified. `git status --short` proves it.

## Verification

```sh
export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"

./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.obf.product

.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_normalizer_obf_product.py \
  tests/environment/test_addon_layer_direction.py

# The add-on-wide guards, which a new add-on is exactly what would break.
.venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_addon_duplicated_helpers.py \
  experiments/integrated-p0/tests/test_addon_credential_hygiene.py \
  experiments/integrated-p0/tests/test_addon_api_contract.py \
  experiments/integrated-p0/tests/test_addon_harness.py

.venv/bin/ruff check experiments/integrated-p0/addons/normalizer.obf.product \
  experiments/integrated-p0/tests/test_normalizer_obf_product.py
.venv/bin/mypy experiments/integrated-p0/addons/normalizer.obf.product/handler.py \
  experiments/integrated-p0/tests/test_normalizer_obf_product.py
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop and report if the documented contract does not say what you need to know.** You are
  writing this from `addon-authoring.md`, `CONTRACT-ADDON@1.3`, and DP-028. Where they are
  silent or ambiguous, the gap is the finding — record it in the handoff rather than reading
  another add-on's source to infer the answer. Measuring that gap is half of why this packet
  goes to an add-on author.
- **Stop if a body field cannot be filled without knowing what the product is.** That would
  falsify DP-028 D5 and is a result, not an obstacle to work around.

## Worker handoff

- Changed files:
  - `experiments/integrated-p0/addons/normalizer.obf.product/addon.toml` (new)
  - `experiments/integrated-p0/addons/normalizer.obf.product/handler.py` (new)
  - `experiments/integrated-p0/tests/test_normalizer_obf_product.py` (new, 41 cases)
  - This packet's `Status` line and `Worker handoff` section
  - `experiments/integrated-p0/addons/normalizer.obf.product/README.md` was generated by
    `addon_kit new` and then **deleted**: it is not in this packet's Allowed files list and
    most other add-ons in this tree do not keep it (`collector.naver.blog` and
    `normalizer.conformance` are the only two that do, so precedent is mixed — kept out
    rather than silently added).

- Commands and results (all run 2026-08-20, `.venv` at repo root, `COSMA_DB_HOST=$PWD/var/postgres COSMA_DB_NAME=cosma_p0 COSMA_DB_USER=$(id -un)`):

  ```
  $ ./scripts/check-addons.sh experiments/integrated-p0/addons/normalizer.obf.product
  normalizer.obf.product          ok

  $ PYTHONPATH=experiments/integrated-p0 .venv/bin/python -m pytest -q -p no:cacheprovider \
      experiments/integrated-p0/tests/test_normalizer_obf_product.py \
      tests/environment/test_addon_layer_direction.py
  46 passed in 0.73s

  $ PYTHONPATH=experiments/integrated-p0 .venv/bin/python -m pytest -q -p no:cacheprovider \
      experiments/integrated-p0/tests/test_addon_duplicated_helpers.py \
      experiments/integrated-p0/tests/test_addon_credential_hygiene.py \
      experiments/integrated-p0/tests/test_addon_api_contract.py \
      experiments/integrated-p0/tests/test_addon_harness.py
  92 passed in 0.12s

  $ .venv/bin/ruff check experiments/integrated-p0/addons/normalizer.obf.product \
      experiments/integrated-p0/tests/test_normalizer_obf_product.py
  All checks passed!

  $ .venv/bin/mypy experiments/integrated-p0/addons/normalizer.obf.product/handler.py \
      experiments/integrated-p0/tests/test_normalizer_obf_product.py
  Success: no issues found in 2 source files

  $ git status --short   # confirms nothing outside the allowed list changed
  (only this packet's own file, the new addon directory, and the new test file appear
   as changes attributable to this task; pre-existing modifications to
   contracts/experimental/POC-CONTRACT-0.1.md, docs/project-state.md, and
   TASK-006-rule-baseline-claims-repair.md were already present before this task began
   and were not touched by it)
  ```

  **Acceptance criterion 3 (determinism must be shown to be able to go red):** verified by
  mutation, not only by a passing assertion. `results.append(...)` in `handler.py`'s `run`
  was temporarily changed to `results.insert(0, ...)` (reverses emission order for a
  multi-item snapshot). Re-running just the order test:

  ```
  $ PYTHONPATH=experiments/integrated-p0 .venv/bin/python -m pytest -q -p no:cacheprovider \
      "experiments/integrated-p0/tests/test_normalizer_obf_product.py::TestItIsDeterministic::test_the_order_follows_the_snapshot"
  F
  AssertionError: assert ['8800000000002', ...] == ['8800000000001', ...]
  1 failed in 0.03s
  ```

  The mutation was then reverted (`git status --short` on the handler shows only the
  original untracked file, byte-identical to what `ruff`/`mypy` were checked against
  above) and the full suite re-run green (41 passed).

- Evidence locations: the six command blocks above are the evidence; nothing else was
  captured to a separate file. The task packet directs results into this handoff rather
  than into `experiments/integrated-p0/evidence/`.

- Limitations and remaining risks:
  - The coexistence test (`TestCoexistenceOverOneLineage`) needed and found a reachable
    PostgreSQL cluster at `$PWD/var/postgres` in this environment, so it ran for real
    rather than skipping — all 41 cases in the new test file, including that one, are
    reported above as passed. If a later run of this same command has no reachable
    cluster, that one class will report as `SKIPPED` via `platform_database`'s own skip
    rather than as a failure or a silent pass; that is inherited harness behavior, not
    something this add-on's tests add.
  - No real Open Beauty Facts capture exists in this repository or was read while writing
    this add-on (TASK-007 owns that). Every `[가설]` below is untested against a real row
    and states what a real row would have to show to falsify it.
  - `addon_kit run` (the authoring-loop harness) was not used to exercise this add-on
    end-to-end; per `addon-authoring.md`, it is not integration evidence for a normalizer
    in any case (its four documented gaps are about outbound guard, atomicity,
    retry/lease, and persistence — none of which a normalizer's harness path touches
    differently). The unit tests against a hand-built `NormalizeContext`, in the same
    style as `normalizer.naver.trend`'s test file, are what this packet asked for.

- Newly discovered questions or blockers: see the "Questions the documentation could not
  answer" section of the worker's report to the orchestrator, delivered alongside this
  handoff. In summary, none of them blocked implementation — each was resolved with a
  stated `[가설]` inside `handler.py`'s module docstring and pinned by a test — but three
  are genuine documentation gaps worth the attacker's and orchestrator's attention:
  1. Whether `display_name`'s "verbatim" means untrimmed-when-stored or only
     trimmed-for-the-presence-check (DP-028 D3 states the null condition, not the stored
     transformation).
  2. Whether a blank-after-trim `code` should be skipped (mirroring `display_name`'s rule)
     or is outside DP-028 D3's stated null condition for `code`, which only names the
     fully-absent case.
  3. Whether "non-numeric" for `observed_at` should admit a numeric-looking string, since
     SRC-003 only measured `last_modified_t` as a JSON number and never as a string.

## Review

- Attack report: [ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md)
- Result: `PASS`
- Orchestrator disposition: `ACCEPTED`, with F1 resolved by measurement and the real gap
  routed to [TASK-010](TASK-010-obf-real-snapshot-normalized.md) rather than back to this
  worker.

`[측정]` **F1 is falsified as a defect and stands as a record error.** The orchestrator read
the two delta files this repository already retrieved (`var/samples/obf/`, TASK-007's
capture, 247 rows across both):

| Field | Present | Type |
|---|---|---|
| `brands_tags` | 26 / 121 in delta A | `list` in every case |
| `brands` | 26 / 121, the same rows | `str` in every case |

So `brands_tags` **is** a real field of the delta payload, it **is** list-shaped, and D3's
choice of it over the string-valued `brands` is right for a field the schema declares as a
list. The attacker's "structurally dead in every real record" scenario does not occur. What
survives of F1 is the part it was surest about: the test docstring attributes the field name
to `SRC-003`, which measured `brands`, not `brands_tags`. That attribution is wrong and is
corrected in TASK-010.

`[측정]` **The measurement found something nobody had decided.** Every one of the 70
`brands_tags` values across both deltas carries a language prefix — `xx:Hismile`, prefix
`xx` at 70 of 70 — and 9 rows carry more than one tag. Nothing in DP-028, this packet, or
the add-on says whether `brands` should carry `xx:Hismile` or `Hismile`. The add-on stores
the tag verbatim, which is defensible and undecided. TASK-010 records it; whether to strip
the prefix is a schema question and is **not** a worker's call.

`[결정]` F2 through F6 are accepted as recorded and not repaired. `[추론]` Each is a test
whose assertion is weaker than its name suggests, in a P0 add-on that `DP-026` already
dispositions `ARCHIVE_REFERENCE_ONLY`; the attacker measured that the properties themselves
hold — `_check_lineage` in the host for F2, migration `0003`'s absent UPDATE path plus a
live-cluster check for F3. Strengthening a fixture to prove what a run already proves is
work P1 rebuilds anyway. The findings are the record; the report is where they live.

`[확인 사실]` The platform-level surrogate crash the report names — `{"code":"a\ud800"}`
reaching `domain.store.canonical_body` and raising `UnicodeEncodeError`, aborting a run
instead of skipping a row — predates this packet and exposes `normalizer.naver.blog`
identically. It is not this add-on's and is not repaired here; it goes to the gate as an
inherited platform defect.
