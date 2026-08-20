# Adversarial review — TASK-011, the dataset record's repairs and F1's positive control

- Subject: `docs/agent-workflow/task-packets/TASK-011-obf-record-repairs.md` (`WORKER_DONE`)
- Files reviewed: `experiments/integrated-p0/evidence/obf-dataset/README.md`,
  `experiments/integrated-p0/tests/test_obf_real_data.py`,
  `experiments/integrated-p0/tests/README.md`
- Attacker: `adversarial-reviewer`, 2026-08-20
- Result: `PASS` — one Medium and two Low findings, none blocking; one command `BLOCKED` by the sandbox

## Environment

- Repo `dev`, working tree as left by TASK-011's worker plus a concurrent
  `normalizer.rule.baseline` worker (not this subject).
- `[측정]` This session's command sandbox denies reading
  `.venv/lib/python3.13/site-packages/certifi/cacert.pem`:
  `.venv/bin/python -c "import httpx; httpx.get('https://static.openbeautyfacts.org/...')"`
  → `PermissionError: [Errno 13] Permission denied`. **The sandbox was not disabled for
  this review.** The gated command
  `.venv/bin/python -m pytest -q tests experiments/integrated-p0/tests/test_obf_real_data.py --run-network`
  therefore could not be executed here; F1 was attacked by an offline harness described
  under Finding A, and that substitution is stated as a limitation, not hidden.
- `[측정]` No database was left behind. `pg_database` before and after this review is
  identical: `cosma_p0`, `cosma_p0_template`, `cosma_p0_test_main_8_17` (a concurrent
  worker's, not touched), `postgres`, `template0`, `template1`.
- `[측정]` Nothing was written to `handler.py` or any add-on file during this review. The F1
  mutations were applied by rebinding module attributes in a throwaway process; the on-disk
  digest is unchanged and is shown below to equal the pre-TASK-011 baseline.

## Result

**`PASS` with two Low findings and one Medium.** Every repair F1, F3, F4, F5, F6, F8 holds
under attack; F7's deviation is a correct call and is verified independently. The new
per-field control is a real control: it went red for four mutations the packet never named,
including both directions of an off-by-one. What it does **not** cover is stated as
Finding B, and that gap is narrower than the one F1 closed.

| # | Finding | Severity | Blocking? |
|---|---|---|---|
| A | F1's per-field control is genuine — red on 6 of 10 mutations, including 4 the packet did not name; no hard-coded counts | `PASS`, no defect | no |
| B | The control is presence-only: three value-fabrication mutations stay green, and the record's "25 individual tag values" is guarded by nothing | Medium | no |
| C | The run-time computation is not delta-proof in the two ways its docstring implies: an out-of-range `last_modified_t`, or a duplicate `code` inside one delta file, makes it red for a non-defect | Low | no |
| D | F4's disclaimer is correct, complete, and placed before the evidence — but the softening clause the first attack named still stands in the paragraph above it, and in the test module docstring, uncorrected | Low | no |
| E | Acceptance criterion 5's `git status --short` check is not verifiable in this shared tree; the add-on digest check substitutes for it and passes | informational | no |
| F | The gated verification command could not be run: sandbox denies the certifi read | `BLOCKED` on that command only | no |

## Finding A — F1's positive control, attacked with mutations the packet did not name

### Why an offline harness, and what it does not replace

`[측정]` The live command is blocked (see Environment). Instead of reporting F1 unverified,
the assertion was attacked offline:
`experiments/integrated-p0/tests/test_obf_real_data.py`'s two blocks — the `presence`
dict computed from emitted bodies, and the `expected` dict computed from the delta file —
were copied **verbatim** into a harness that runs the installed
`addons/normalizer.obf.product/handler.py` over delta A's 121 rows through a real
`addon_api.NormalizeContext`, with `SnapshotItem.payload` set to the file's own lines.

`[추론]` This is a faithful proxy for the emitted side because the record already measures
(and the suite already asserts) that each `raw_item.payload` is byte-identical to its line
in the source file, and the snapshot is 121 members over 121 unique `code`s. It is **not** a
substitute for the live run: it exercises the handler, not the importer, the seal, or
`JobRunner`. A defect confined to those three layers is outside what this harness can see.

`[측정]` The harness reproduces the record's field-presence table exactly, from the delta
file that is still on disk (`5cefb426…`, the digest the record pins):
`display_name 27, brands 22, observed_at 121, has_ingredients_true 16` on both sides —
independent confirmation of the four numbers in *Field presence, per DP-028 D3's four body
fields*, and of the *`brands_tags`, confirmed* section's 22 records / 25 tag values.

### Mutation results

`[측정]` "RED" = the new per-field assertion fails; "green" = it passes. The `not all(...)`
column is the pre-existing guard F1 called decorative.

| Mutation | new per-field assert | old `not all(...)` guard |
|---|---|---|
| M0 baseline, unmutated | green | green |
| M1 `_display_name(...) or "FABRICATED"` — the packet's own | **RED** (121 vs 27) | green |
| M2 **different field**: `_brands` invents a tag when the source has none | **RED** (121 vs 22) | green |
| M3 **off-by-one down**: drop `display_name` on the first row that has one | **RED** (26 vs 27) | green |
| M4 **off-by-one up**: fabricate `display_name` on one empty row | **RED** (28 vs 27) | green |
| M8 `display_name` forced to `None` everywhere | **RED** (0 vs 27) | green |
| M10 one row skipped at `_external_id` | **RED** (`observed_at` 120 vs 121) | green |
| M5 `display_name` replaced by a constant on rows that have one | green | green |
| M6 `observed_at` replaced by a constant epoch on every row | green | green |
| M7 `brands` replaced by one invented tag when the source list is non-empty | green | green |
| M9 `language` forced to `"ko"` | green | green |

`[확인 사실]` The packet's stop condition — no hard-coded counts — is met.
`grep -n "121\|\b27\b\|\b22\b\|\b16\b"` over the test file returns three hits, all inside
prose (a docstring citing the mutation proof, a docstring citing TASK-008's 26/121, and the
F6 note's `16:16` timestamp). No literal count appears in an assertion.

`[추론]` The control is real and it is stronger than the packet asked for. M3 and M4 are the
important ones: a one-row shift in either direction goes red, so the assertion is pinning a
count, not merely detecting saturation. M10 shows `observed_at`'s 100% presence doubles as a
row-count guard — any dropped or skipped row moves it.

### Does the assertion derive both sides from the same wrong place?

`[확인 사실]` No. The emitted side reads `normalized_result` bodies produced by
`handler.py`'s `_display_name`/`_brands`/`_observed_at`/`_has_ingredients`; the computed
side is an independent reimplementation of the *presence rules* over `row.get(...)` in the
test file. Neither calls the other. The one thing they share is the delta file on disk, and
that is the source of truth by definition — the emitted side reaches it through
`_fetch_delta` → import → seal → normalize, the computed side by `json.loads` on the same
path.

`[가설]` One residual shared-origin weakness: the computed side re-reads
`first.jsonl_path` from disk at assertion time and never re-checks it against
`first.jsonl_sha256`, which the fixture already captured. If that file were replaced between
import and assertion, both sides would still be compared against *a* file, just not
provably the one the record pins. Cheap to close (`assert _sha256(first.jsonl_path.read_bytes()) == first.jsonl_sha256`),
and not a defect today.

## Finding B (Medium) — the control pins presence, and three numbers in the record are not presence

`[측정]` M5, M6, and M7 above each fabricate a *value* while leaving presence untouched, and
the whole suite stays green:

- **M6** replaces every `observed_at` with `1970-01-01T00:00:00Z`. The record's
  `observed_at 121 / 121, 100%` row stays literally true, and its `[추론]` — *"OBF's
  mongoexport apparently stamps every row with a modification time"* — stays green while
  every stamp in the database is invented.
- **M7** replaces each non-empty `brands` with `["xx:FABRICATED"]`. Per-field presence is
  unchanged (22 records), and
  `test_the_brands_tags_prefix_measurement_is_confirmed_or_contradicted` **also** passes,
  because the fabricated tag carries the `xx:` prefix it asserts on. The tag count moves
  from 25 to 22 — and the record's sentence *"25 individual tag values were present"* is
  asserted by nothing at all. `[추론]` This is the same defect F1 named, one section lower
  in the same file, still open.
- **M9** rewrites `language` to `"ko"` on every record. It is one of DP-028 D3's five body
  fields; nothing in this file watches it.

`[추론]` Not blocking, and materially narrower than what F1 closed: the four numbers F1 was
about are now pinned, and a value fabrication does not make the record's presence table
wrong. But a gate reader should know the record's *content* claims (`observed_at` is a real
modification time; 25 tag values; the `xx:` prefix came from the source) rest on one manual
reading, not on a guard. The cheapest closure is a count assertion on the tag total computed
the same run-time way — `sum(len(tags) for tags in tagged)` against the source's own
`brands_tags` lengths — which would have caught M7.

## Finding C (Low) — "computed at run time" is not the same as "cannot fail on a later delta"

The new docstring says a run-time computation avoids the false failure a hard-coded 27 would
cause on the next delta. `[측정]` Two source shapes make it red anyway, neither of them a
defect:

1. **An out-of-range `last_modified_t`.** `handler._observed_at` returns `None` on
   `OverflowError`/`OSError`/`ValueError` — documented, deliberate behavior. The test's
   `expected` counts any non-`bool` number as present. Verified directly:
   `_observed_at(1e300)` → `None`, while `expected`'s predicate → `True`. One such row in a
   future delta and the assertion fails while the add-on is behaving exactly as its own
   docstring promises.
2. **A duplicate `code` within one delta file.** `expected` counts file *rows*; `presence`
   counts *snapshot members*, and the seal collapses duplicates (`DP-019` D5). Delta A is
   121/121 unique today, so this does not bite now; it is a property of the source, not of
   the code, and nothing records that the assertion depends on it.

`[추론]` Both err toward red, so the control is not weakened — but a future worker meeting
either will read a red as a regression. Worth one sentence in the docstring, not a code
change.

## F4 — the section that matters for the gate: `PASS`, with Finding D

`[확인 사실]` **Content is complete and correct against its sources.** *What this does not
establish* (lines 19–39) carries all four required elements, and each checks out verbatim
against the decision it cites:

| Required by the packet | In the record | Verified against |
|---|---|---|
| DP-027 D2's two zeroes | line 25: "zero Korean sunscreen and zero Korean toner rows" | `DP-027` line 80, and its measurement table lines 39–40 (`0`, `0`) |
| 26.5%, with the missing threshold named | lines 28–31: "26.5%, database-wide — and no threshold exists anywhere in this repository to judge that number against" | `DP-027` lines 82 and 127 |
| "closed" ≠ "useful" | lines 32–36 | `DP-028` D6, lines 128–131, quoted verbatim at line 21 |
| DP-026 moved the product question to P1 | lines 37–39 | `DP-026` D1, lines 63–69 |

`[확인 사실]` **Placement is right.** The section is the third thing in the file — after the
licence note and *Why this exists*, and **before** every evidence table, the TASK-010
section, and the counts. It is a disclaimer a reader passes through, not one appended after
the evidence.

`[측정]` **The hostile-reader test.** I tried to build "this record says the dataset is
useful" out of the file as it stands. Against the evidence sections it cannot be done: every
one of them is `[측정]`-labeled and mechanical (bytes, digests, counts, manifests), and the
word "closed" appears exactly once outside the disclaimer, at line 21 inside D6's own quote.

`[추론]` **Finding D (Low).** One quotable softener survives, and it is the one the first
attack named. *Why this exists*, lines 12–17 — the paragraph **immediately above** the new
section — still reads: *"`SRC-003` … recommended `NO-GO` on Korean sunscreen/toner
**coverage** — but that recommendation is about product content, and `DP-026` moved the
product scope to P1."* Quoted alone, that is a sentence whose plain reading is "the `NO-GO`
does not apply here," and it is stated before the reader reaches the correction. The same
clause is in `test_obf_real_data.py`'s module docstring, lines 3–11, with no counterweight
at all — and that file was in this packet's allowed set and was edited for F6, so the
docstring could have carried the D6 line at no extra cost.

`[추론]` Not blocking: a reader who reads the file in order meets the disclaimer two
paragraphs later, and the disclaimer is unambiguous. Blocking would require the misreading
to survive a full read, and it does not.

## F3 — the fetch-time column: `PASS`

`[확인 사실]` The column header is now `Local file read (\`raw_envelope.retrieved_at\`)`. The
word "Fetched" is gone from the table. The note at lines 64–70 states which line of code sets
it (`addon_host/capabilities.py:548`), that `FetchedDelta.fetched_at` is the real acquisition
time, that **this run did not persist it anywhere**, and that the earlier label "claimed a
quantity this table does not carry."

`[추론]` This is the honest half of the packet's either/or, not a relabel that still reads as
a fetch time: the header names the event (a local file being read), the parenthetical names
the field, and the note names what is missing. A reader cannot take the value for an HTTPS
delivery time. `[확인 사실]` `_fetch_delta` does compute `fetched_at`
(`test_obf_real_data.py:120`) and the dataclass carries it, so a future run can record the
real value without touching `capabilities.py` — the packet's forbidden change is not
required, and the record does not pretend otherwise.

## F5 — "a day earlier": `PASS`

`[확인 사실]` Corrected in both places (lines 49 and 72–78) to "the same day, ~7 hours
earlier," with the exact timestamp `2026-08-20T08:30:48+09:00`. Verified against
`experiments/source-probes/SRC-003-open-beauty-facts.md` lines 326–327 and its *Capture
ledger* line 516, both of which record `0af0a0e5…` at `2026-08-20T08:30:48`. `[확인 사실]`
Visible **as a correction**: line 74 says "not 'a day earlier' as an earlier version of this
line said," and explains that the 2026-08-19 date belongs to the delta's content
(`Last-Modified 2026-08-19T00:18:24Z`, `SRC-003` line 327), which is where the error came
from.

## F6 — the docstring that contradicted the record: `PASS`

`[확인 사실]` `test_obf_real_data.py:147–155` now says the opposite of what it said, names
F6 and the report it came from, and gives the reason (a fixed archived export, not a live
query). The record was the one that was right, and it is the docstring that moved.

`[확인 사실]` The three retrievals are real and independently sourced, not asserted:

| Retrieval | Evidence | Digest |
|---|---|---|
| 08:30:48 | `SRC-003` *Capture ledger*, line 516 | `0af0a0e5…` |
| 15:36 | `var/samples/obf/…1787012322_1787098703.json.gz`, mtime `2026-08-20 15:36`, TASK-007's capture | `0af0a0e5…` (verified by `sha256sum` in this review) |
| 16:16 | `ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md` lines 87–104, 260 | `0af0a0e5…` |

`[측정]` `sha256sum var/samples/obf/*` in this session returns
`0af0a0e5297c50d9b2acfadec21b23fc6ba515db20721dc9ec0222a180c4aea5` for delta A's `.gz` and
`5cefb426f7d94afd0bd3c743e38f13f70e2f7720d7f2277c51bc28901a3b3337` for its `.jsonl` — the
record's values, unchanged, a fourth day-of confirmation.

## F7 — the deviation: the worker's call is correct, and the name really is gone

The packet said "add" a database name. The worker did not, and said so. I was asked to judge
that, and specifically to check whether the name is unrecoverable rather than inconvenient.

`[측정]` **It is unrecoverable from this machine.**

1. The cluster no longer holds it: `pg_database` contains `cosma_p0`, `cosma_p0_template`,
   `cosma_p0_test_main_8_17` (a concurrent task's), `postgres`, `template0`, `template1`.
   None of TASK-007's four kept databases survive either.
2. `log_statement` is off on this cluster, so `create database` never reached the log. The
   only lines in `var/postgres.startup.log` that carry a test database name are
   `FATAL: database "…" does not exist` errors. `[측정]` Of the 27 such lines dated
   2026-08-20, the **last is at 14:23:28** — TASK-010's run is at ~18:06–18:09 (the delta
   files were rewritten at 18:08, `handler.cpython-313.pyc` at 18:08:58), so no line in the
   log falls in that window.
3. The name is in no document: `grep -rn "1ce74fc5"` over the tree returns two hits, the
   record's own gap line and the packet's handoff — neither carries a database name.

`[추론]` **The call was right.** The alternative to recording the gap was writing a
plausible-looking `cosma_p0_test_main_NNNNN_0`, which is precisely the *"evidence named for a
revision that could not have produced it"* failure. A fabricated identifier is worse than a
named absence, because a gate reader cannot tell the two apart from the outside.

`[추론]` **And the gap is stated in a way a reader can act on** — but only just. The line
(`README.md:283`) names what is missing, contrasts it with the four sections that do carry a
name, and says it replaces a vaguer earlier phrasing. What a reader gains from it is the
right conclusion: *the TASK-010 normalizer run's rows cannot be re-inspected in place; only
its snapshot id, manifest digest, and counts survive, and those are reproducible from the
delta file, which is still on disk.* What the line does **not** do is close the criterion —
and it does not claim to. It is not "we did not record it, therefore it does not matter": the
handoff states the remedy explicitly (a new, authorized re-run of
`TestTheNormalizerRunsOnTheRealSnapshot` with `--keep-database`) and hands the decision to the
orchestrator.

`[가설]` The orchestrator should decide whether the gate needs that re-run. My reading is that
it does not: `manifest_sha256 82c27a07…` is the same value four independent seals produced,
the 121-row counts were reproduced by this review's harness from the delta file directly, and
a database name is a pointer to rows that would have been dropped after the record was
written in any case. But that is a disposition call, not mine.

## F8 — attribution: `PASS`

`[확인 사실]` `experiments/integrated-p0/tests/README.md` gained
*"This section was added by the orchestrator on 2026-08-20, outside any active task packet's
allowed files — recorded here per `ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md` F8, so
the file does not carry anonymous provenance."* The line names the author, the date, the
irregularity (outside any packet's allowed files), and the report that required it. The
`git diff` for this file is that block and nothing else.

## Scope — what was and was not touched

`[확인 사실]` **`normalizer.obf.product` is byte-identical to its pre-mutation state, proven
against a baseline the worker did not write.**
`experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md:22` — the *previous*
attack report, written before TASK-011 existed — records
`71156e6fff17d8a78a9a6333d37b8a449d5bbd1456ad8a57836d18483c86a33f  addons/normalizer.obf.product/handler.py`.
`[측정]` `sha256sum` today returns the same digest, and `addon.toml` is
`aa308cd284632a62ea65a03ea3f21e4eaf1c99c7b7ca241804f32ffeacd030b7`.
`[측정]` `grep -rn "FABRICATED" experiments/integrated-p0/addons/` → no match, in source or in
`__pycache__/handler.cpython-313.pyc` (checked for the byte string directly). The `.pyc`'s
recorded source mtime and size (`1787216797`, `8035`) match the file on disk, so the compiled
artifact is not a survivor of the mutated version either.

`[측정]` `git diff --stat -- experiments/integrated-p0/addons/` shows only
`normalizer.rule.baseline` (`addon.toml`, `handler.py`) — the concurrent worker's, explicitly
out of this subject.

**Finding E (informational).** Acceptance criterion 5's *"`git status --short` shows only the
allowed files"* is **not verifiable in this tree**: a second worker and the orchestrator have
modifications in flight (`contracts/experimental/POC-CONTRACT-0.1.md`,
`docs/open-questions/OQ-004-snapshot-boundary.md`, `docs/project-state.md`,
`TASK-006-…`, `normalizer.rule.baseline/*`). None is attributable to TASK-011, and the
digest check above is the stronger substitute for the part of criterion 5 that matters. The
criterion should be written as a digest check rather than a `git status` check when tasks run
concurrently.

`[확인 사실]` **OBF payload.** Four files sit under `var/samples/obf/` (two `.gz`, two
`.json`). They are OBF payloads and they are inside the working tree; what is true is that
`/var/` is gitignored (`.gitignore:45`) and they are therefore not committed, and that
`../evidence/obf-dataset/README.md`'s *Usage basis* row states the rule precisely — *"no OBF
row … enters the working tree, tracked or untracked, **outside `var/`**"*. `[추론]` The
worker's handoff phrasing — *"No OBF payload in the working tree: `var/samples/obf/*` all
`git check-ignore` to `/var/`"* — is loose: `check-ignore` proves *ignored*, not *absent*. The
record's own wording is the correct one, and the condition it states holds. Not a finding
against the record; noted so the handoff's sentence is not quoted later as if it were.

## Commands run

```sh
sha256sum experiments/integrated-p0/addons/normalizer.obf.product/*      # 71156e6f… / aa308cd2…
sha256sum var/samples/obf/*                                              # 0af0a0e5… 5cefb426… 333d98a7… 91631c0a…
.venv/bin/ruff check experiments/integrated-p0/tests/test_obf_real_data.py    # All checks passed!
.venv/bin/mypy  experiments/integrated-p0/tests/test_obf_real_data.py         # Success: no issues found in 1 source file
export COSMA_DB_HOST="$PWD/var/postgres" COSMA_DB_NAME=cosma_p0 COSMA_DB_USER="$(id -un)"
.venv/bin/python -m pytest -q -p no:cacheprovider tests \
  experiments/integrated-p0/tests/test_obf_real_data.py --run-network --collect-only   # 123 tests collected
.venv/bin/python -m pytest -q -p no:cacheprovider tests \
  experiments/integrated-p0/tests/test_obf_real_data.py --run-network -k field_presence
#   → ERROR … ssl.py:729: PermissionError: [Errno 13] Permission denied   (the `deltas` fixture)
```

`[측정]` `--collect-only` returning **123** matches the worker's reported `123 passed`
exactly, so the count in the handoff is at least the right denominator; it is not proof the
123 passed, and this review does not claim to have reproduced that run.

`[확인 사실]` **`BLOCKED`, Finding F**: the packet's own verification command cannot run in
this session. `.venv/bin/python -c "import httpx; httpx.get('https://static.openbeautyfacts.org/data/delta/index.txt')"`
→ `PermissionError: [Errno 13] Permission denied` at
`ssl.create_default_context` → `load_verify_locations`. This is the fifth session to record
it. The sandbox was **not** disabled; F1 was attacked offline instead, and the limits of that
substitution are stated in Finding A.

## What I could not break

- The per-field assertion, with any presence-shifting mutation I could construct — including
  a different field, both directions of an off-by-one, a total wipe, and a row skip.
- F4's disclaimer, read as a hostile reader looking for "the dataset is useful." The
  softening clause in *Why this exists* is the closest thing to a quotable misreading, and it
  does not survive a full read of the file.
- F7's claim that the database name is gone. It is gone from the cluster, from the postgres
  log, and from every document in the tree.
