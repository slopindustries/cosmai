# ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA — Attack report on TASK-007 and TASK-010

- Packets: `docs/agent-workflow/task-packets/TASK-007-obf-dataset-end-to-end.md`,
  `docs/agent-workflow/task-packets/TASK-010-obf-real-snapshot-normalized.md`
- Worker revision: working tree on `dev` at `70fa293` (both packets' artifacts untracked)
- Attacker: `adversarial-reviewer`, 2026-08-20
- Result — TASK-007: `PASS`
- Result — TASK-010: `PASS`

*(Written incrementally through `Bash`. This attacker holds no `Write`/`Edit`; the two
mutations it made were backed up byte-exactly and restored, proof in the report.)*

## Measurements

### Payload-level reconciliation of every count in the record (no database needed)

`[측정]` From the two delta files under `var/samples/obf/`, read directly:

```sh
sha256sum var/samples/obf/* ; wc -c var/samples/obf/*
```

| Recorded | Recomputed | Match |
|---|---|---|
| delta A `.gz` 81,135 / `0af0a0e5…` | 81,135 / `0af0a0e5297c50d9b2acfadec21b23fc6ba515db20721dc9ec0222a180c4aea5` | yes |
| delta A `.jsonl` 665,658 / `5cefb426…` | 665,658 / `5cefb426f7d94afd0bd3c743e38f13f70e2f7720d7f2277c51bc28901a3b3337` | yes |
| delta B `.gz` 114,812 / `333d98a7…` | 114,812 / `333d98a72a69789d114b28bf58e872250f6c668840278ad90be28beec022bd50` | yes |
| delta B `.jsonl` 898,166 / `91631c0a…` | 898,166 / `91631c0a30ad325a3ce1a608db3b1b9bec49f292b9f1aa78820d055dd413dd05` | yes |
| A 121 products / 121 unique `code` | 121 / 121 | yes |
| B 126 / 126 | 126 / 126 | yes |
| overlap = `7891010974312`, `5906721183488`, `4047196060247` | exactly those three | yes |
| snapshot `item_count` 244 = 121+126−3 | union of codes = 244 | yes |
| `display_name` 27/121 | `product_name` non-blank on 27 (key present on 28 — one blank) | yes |
| `brands` non-empty 22/121 | `brands_tags` non-empty on 22 | yes |
| `observed_at` 121/121 | `last_modified_t` present, `int`, on 121/121 | yes |
| `has_ingredients=true` 16/121 | `ingredients_text` non-blank on 16 | yes |
| TASK-010: 25 tag values, all `xx:` | delta A: 25 values, 25 prefixed | yes |
| TASK-008 Review: 26 rows carry `brands_tags`, 70 values across both deltas | A key present 26; A 25 values + B 45 values = 70; 70/70 prefixed | yes |

`[확인 사실]` **The two `brands_tags` measurements do not contradict each other, and the
stated explanation is exactly right.** Delta A has 26 rows carrying the `brands_tags` key,
of which 4 hold `[]` and 22 hold a non-empty list — which is precisely the "present in one
reading, absent in the other" the record names. 25 values in delta A alone; 70 across both.
Both numbers are reproducible from the same bytes.

### The sandbox block, measured a third time

`[측정]` In-sandbox, the documented command yields `111 passed, 12 errors`, every error a
`PermissionError: [Errno 13]` raised from `ssl.py:729 context.load_verify_locations`. Two
workers recorded this; this is the third independent observation. With the sandbox disabled
the same command yields `123 passed` (111 + the 12 network tests) — reproduced by this
attacker on 2026-08-20.

`[측정]` **Newly discovered question 1 is real.** `pytest -q experiments/integrated-p0/tests/test_obf_real_data.py --run-network`
with no `tests` path fails with `error: unrecognized arguments: --run-network`. Reproduced.

### The three priority questions, measured against this attacker's own run

`[측정]` This attacker re-ran the documented command with `--keep-database` (sandbox
disabled), producing 12 databases `cosma_p0_test_main_110402_0..11`. Every number below is
from **this** run, not from the worker's — the worker's databases were already dropped.

Map: `_6` is the identical-replay scenario (2 envelopes / 242 `raw_item` / 2 snapshots),
`_7` the changed-content scenario (2 envelopes / 247 `raw_item` / 1 snapshot of 244),
`_8`–`_11` the four normalizer tests (121 `normalized_result` each).

**1. `observed_at` 121/121 is real, not an artifact.**

```sql
select count(*) filter (where body->>'display_name' is not null),
       count(*) filter (where jsonb_array_length(coalesce(body->'brands','[]'::jsonb))>0),
       count(*) filter (where body->>'observed_at' is not null),
       count(*) filter (where (body->>'has_ingredients')::bool),
       count(*) from normalized_result;   -- 27|22|121|16|121
```

Identical to the recorded table, from a different run and a different database. At the
payload layer, `last_modified_t` is present as an `int` on 121 of 121 rows of delta A (and
126 of 126 of delta B). `[추론]` OBF's mongoexport stamps every row with a modification
time; the field is universal for the same reason `code` is, and the sparse fields are
operator-supplied. The record's reading is correct.

**2. Identical replay: the snapshot layer really is what absorbs it, and the result does
not depend on the tie-break.**

```
snapshot | 121 | 82c27a07b12d62a6bc455f58c8c8c112227dd43055a41136ccaca041ca70b770 | 16:16:55.580923
snapshot | 121 | 82c27a07b12d62a6bc455f58c8c8c112227dd43055a41136ccaca041ca70b770 | 16:16:55.665495
raw_item : 2 envelopes × 121 = 242
select count(*) from (select item_key, count(distinct md5(payload)) d from raw_item group by item_key) t where d>1;  -- 0
```

`[측정]` The manifest digest `82c27a07…` is the *same value the worker recorded* — reproduced
across two sessions, two processes, and two databases. No `item_key` has two distinct
payloads, so both duplicate Raw rows are byte-identical and the manifest would be identical
whichever one the selection picked. `[추론]` Criterion 3's result is therefore robust: it
does not rest on the tie-break at all.

**3. The 3-code selection was decided by the selection rule, not by the random tie-break.**

```
item_key      | emitted_at                    | envelope
4047196060247 | 2026-08-20 16:16:55.771472+09 | delta A
4047196060247 | 2026-08-20 16:16:55.830678+09 | delta B     ← 59 ms later
(same shape for 5906721183488 and 7891010974312)
```

`emitted_at` is `now()` — the *transaction* timestamp — so it is constant within one
envelope (121 rows share one value, 126 share another) and differs between the two imports.
`SELECT_SNAPSHOT_MEMBERS`'s `order by item_key, emitted_at desc, id desc` therefore resolves
on `emitted_at` and never reaches `id desc`. Independently confirmed by byte comparison: the
three sealed members' md5s (`7b0e8e99…`, `d1276f2b…`, `1c896e1a…`) equal **delta B's** lines
and differ from delta A's. The known random-`uuid4` tie-break was **not** what produced this
result.

**3b. …but the tie-break was made to fire, and it chose wrong.** `[측정]` On a template
copy of `_7` (`cosma_attack_tie`, dropped after), `update raw_item set emitted_at =
'2026-08-20 12:00:00+09'` — forcing the exact tie the two imports narrowly avoided — then
re-sealing 12 times:

```
outcomes over 12 re-seals, emitted_at tied: {('A','A','B'): 12}
distinct manifests: 1
```

`[추론]` With `emitted_at` equal, `id desc` decides. `id` is a `uuid4` already fixed on the
row, so the outcome is *stable within one database* but **arbitrary across databases** — and
here it selected delta **A**'s stale payload for two of the three shared codes. Criterion 4's
"the later observation wins" is therefore true at **import granularity** (two imports, two
transactions, two `now()` values ~59 ms apart) and **not** at row granularity. Nothing in the
test or the record asserts the two imports must be separate transactions; `emitted_at`'s
`default now()` is the transaction timestamp, so a future path that batched two imports into
one transaction would silently invert this result. This is not an error in the evidence —
the evidence reports what happened, accurately — but it is a qualification the charter
criterion should carry.

### Tamper detection: the negative control exists *outside* the test

`[측정]` The fixture chain produced two sibling databases for the two tamper-class tests,
differing only in the mutation:

| | `_4` (`test_the_snapshot_verifies_as_sealed`) | `_5` (`test_a_mutated_member_is_detected_and_named`) |
|---|---|---|
| `manifest_sha256` | `82c27a07…` | `82c27a07…` (identical — sealed over the same clean rows) |
| `snapshot_item` ordinal 0 payload | the real OBF row for `code` `00036151` | `{"code": "tampered"}` |
| `payload_sha256` at ordinal 0 | `f87d3e49…` | `f87d3e49…` (unchanged — written at seal time) |
| `domain.snapshot_tampering(...)` | `()` | `("member 0 ('00036151') no longer matches its digest", 'the recomputed manifest digest differs from the sealed one')` |

`[확인 사실]` `f87d3e491e27e392592caaa80fdc1b356096504a80495cbdfede6d44fa0a8ead` is the
SHA-256 of `00036151`'s own line in delta A, computed from the file. **The answer to "would
verification still have passed if the mutation had not been made" is measured, not argued:
`_4` is that run, and it returns `()`.** Criterion 4's fail-capability requirement is met.

### Criterion 2: payloads are the source's own bytes — checked harder than the test checks it

`[측정]` The test asserts each stored payload's digest is *a member of* the file's line
digests. Stronger check, on `_0`:

```
select count(*), count(distinct encode(sha256(payload),'hex')) from raw_item;  -- 121|121
```
and the sorted set of 121 stored digests is **equal** to the sorted set of the file's 121
line digests (`identical set: True`). Nothing was re-serialized, dropped, or duplicated.

### Deliberate breaks: does the suite go red for the right reason?

`[측정]` Both mutations were made through `Bash`, backed up byte-exactly, and restored;
restoration proved by SHA-256 and `git status`.

| Mutant | Where | Result |
|---|---|---|
| `payload=line` → `payload=json.dumps(entry, sort_keys=True).encode()` | `addons/importer.local.jsonl/handler.py` | **killed** — `2 failed, 121 passed`: `test_the_payload_is_the_sources_own_line_bytes_not_a_reserialization` and `test_the_second_later_delta_advances_shared_codes_without_editing_raw_in_place` |
| `"display_name": _display_name(...)` → `... or "FABRICATED"` | `addons/normalizer.obf.product/handler.py` | **SURVIVED** — `123 passed` |

The first is the acceptance criterion doing its job. The second is F1 below.

---

## Findings

### F1 — Major (non-blocking). The field-presence table has no positive control.

**Claimed.** `evidence/obf-dataset/README.md`, TASK-010 section: `display_name` 27/121,
`brands` 22/121, `observed_at` 121/121, `has_ingredients=true` 16/121, presented as `[측정]`
gate evidence.

**Why it is unproven going forward.** The only test over those numbers,
`test_field_presence_over_real_rows_is_recorded_not_smoothed`, asserts
`not all(count == len(results))` — it fires only if *every* field is full on *every* record.
The four numbers themselves are asserted nowhere; they were measured out of band and typed in.

**Reproduction.**
```sh
# in addons/normalizer.obf.product/handler.py
-                    "display_name": _display_name(row.get("product_name")),
+                    "display_name": _display_name(row.get("product_name")) or "FABRICATED",
.venv/bin/python -m pytest -q -p no:cacheprovider tests \
  experiments/integrated-p0/tests/test_obf_real_data.py --run-network   # → 123 passed
```
`display_name` becomes 121/121 — the record's `27/121` becomes false — and the suite is
green, because `brands` and `has_ingredients` stay sparse and `all(...)` stays false.

`[추론]` Not a packet violation: TASK-010 asked the worker to **record** presence, and it
recorded it correctly (I reproduced all four numbers twice, from the payload and from my own
`normalized_result` rows). But this is the repository's named failure mode — a number in gate
evidence with nothing that would notice it drifting. A P1 reader should treat the table as a
2026-08-20 measurement, not as a maintained invariant.

### F2 — Major (non-blocking). Criterion 4's "later wins" holds per import, not per row.

**Claimed.** *"`seal_snapshot_from_raw`'s 'latest `emitted_at` wins' rule selected the newer
observation"* for each of the 3 shared codes.

**True as measured, and I confirmed the tie-break did not decide it** (§3 above). But
`raw_item.emitted_at` is `default now()` — the **transaction** timestamp — so it is constant
across all 121 rows of one import and separates the two imports only because they ran in two
autocommit transactions ~59 ms apart. Force the tie and the rule falls through to
`id desc` on a `uuid4`:

```sql
update raw_item set emitted_at = '2026-08-20 12:00:00+09';
-- re-seal ×12 → snapshot selects ('A','A','B') every time; 1 distinct manifest
```

Two of the three shared codes then seal with delta **A**'s stale payload. Nothing in the test
or the record asserts that two imports must occupy two transactions.

`[결정]` Recommended: the charter's criterion 4 line should read *later **import** wins*, and
the `uuid4` tie-break should stay on the open-items list TASK-003 put it on rather than being
treated as retired by this evidence.

### F3 — Moderate. The recorded "Fetched" time is the import time, not the fetch time.

TASK-007 criterion 1 requires *"fetch time with timezone"*. The record's *What was captured*
table gives `raw_envelope.retrieved_at` — set at `addon_host/capabilities.py:548`
(`self._clock().isoformat()`) when the importer opened the **local** decompressed file. The
actual HTTPS retrieval time is `FetchedDelta.fetched_at`, computed in `_fetch_delta` and never
persisted or written down anywhere. The two differ by however long decompression and job
dispatch took — small here, but the record labels the wrong quantity.

### F4 — Moderate. DP-028 D6's line is not in the record.

D6: *"DP-027 D2 recorded zero Korean sunscreen and zero Korean toner rows in this source… no
gate claim may read 'the dataset half is closed' as 'the dataset is useful for the product
question'."*

`grep -n "Korean\|NO-GO\|sunscreen\|toner\|does not establish"` over
`evidence/obf-dataset/README.md` returns **one** line — a subordinate clause that raises the
`NO-GO` and immediately deflects it (*"but that recommendation is about product content, and
DP-026 moved the product scope to P1"*). The zero counts are never stated, and the record has
no *What this does not establish* section. The record does not make the forbidden claim; it
also does not carry the line, and this is the file a P1 Entry Gate reader opens first.

### F5 — Minor (factual). "A day earlier" is wrong.

The record: *"Delta A's `.gz` digest is byte-identical to the one `SRC-003` recorded for this
same filename a day earlier."* `SRC-003` §*Capture ledger* records it at
**2026-08-20T08:30:48+09:00** — the same day, ~7 hours before. The 2026-08-19 date belongs to
the delta's *content*, not to `SRC-003`'s capture. `[측정]` The byte-identity claim itself is
true and now measured three times (08:30, 15:36, 16:16 — all `0af0a0e5…`), and the record's
reasoning (an archived file, not a live query) is supported by exactly that.

### F6 — Minor. The test module contradicts the evidence record, and the record is right.

`test_obf_real_data.py`'s `deltas` fixture docstring: *"OBF's export is regenerated nightly,
so a second fetch could not reproduce these bytes anyway (`SRC-003`)."* The record says the
opposite and matches measurement. `SRC-003`'s "a re-run will not reproduce these digests"
is about its live **API** samples; its own ledger shows the archived delta reproducing.

### F7 — Minor (traceability). TASK-010's section names no database.

Every TASK-007 scenario names its kept database (`…_79244_0`, `…_80669_0`, `…_80881_0`,
`…_81154_0`). TASK-010's says only *"(kept db, this run's own)"*. Nothing is unproven — I
reproduced all of its numbers independently — but it is the traceability the same file
insists on two screens above.

### F8 — Minor (scope). An unattributed change outside every packet's allowed files.

`experiments/integrated-p0/tests/README.md` gained a section *"The two opt-in flags need the
`tests` path, and nothing said so"*, entirely about `test_obf_real_data.py`, and cited by
TASK-010's own Verification block. It is in the allowed-files list of **no** active packet
(TASK-007, TASK-009, TASK-010 all checked), and TASK-007's worker handoff says *"Nothing
else."* Non-blocking — `agent-workflow/README.md` exempts a documentation correction that
changes no accepted claim — but its author is unrecorded.

---

## What I tried to break and could not

- **Every digest and byte count in the record.** All four recomputed exactly.
- **Every count.** 121/121, 126/126, the three overlapping codes by name, union 244.
- **All four field-presence numbers**, twice: from the payload, and from `normalized_result`
  in my own kept database. `observed_at` 121/121 is real — `last_modified_t` is an `int` on
  121 of 121 rows of delta A and 126 of 126 of delta B.
- **The two `brands_tags` measurements.** They reconcile exactly and the record's explanation
  is correct: delta A carries the key on 26 rows, 4 of them `[]`, 22 non-empty; 25 values in
  A plus 45 in B is TASK-008's 70; 70 of 70 carry `xx:`. **Not a contradiction.**
- **The manifest digest.** `82c27a07…` reproduced across two sessions, two processes, two
  databases, and both packets' runs.
- **The tamper control's fail-capability**, from outside the test: sibling databases with
  identical manifests, one clean (`()`), one mutated (both named problems).
- **The payload-identity claim**, harder than the test does: set equality, not membership.
- **Re-serialization**: mutant killed by the test that claims to catch it.
- **Allowed-file compliance and payload leakage.** Both delta files `git check-ignore` to
  `/var/`; no OBF row anywhere in the tree; the only paths belonging to these two packets are
  their allowed ones. `normalizer.rule.baseline`'s modifications are the concurrent
  attacker's, per instruction, and are not reported here.

## Scope and decision-boundary review

- **Allowed-file compliance:** clean for both packets, with F8's one unattributed exception.
- **Accepted-decision compliance:** DP-027 (nothing published, `data_class = 'local'`) holds;
  DP-028 D3's five fields are what the records carry; DP-028 D6 is F4.
- **Unanswered consequential direction:** the `xx:` prefix is correctly routed to the owner
  and not decided.
- **Prohibited material exposure:** none. Bare `code` identifiers appear in the record and in
  this report, as `SRC-003` already does; no row, in any form, is in the tree.

## Conclusion

- **TASK-007: `PASS`.** Criteria 1–9 were each tested against a fresh run of my own, not
  against the handoff. The flow does reach end to end through the claimed paths — `POST
  /sources/{id}/import` + `JobRunner` + the installed `importer.local.jsonl`, then `POST
  /sources/{id}/snapshots` — and every digest, count, identifier, and manifest in the record
  survives recomputation. F3 qualifies criterion 1's *fetch time*; F2 qualifies criterion 4's
  *later wins*. Neither is a defect in what was measured.
- **TASK-010: `PASS`.** The normalization ran through the host's normalize path against the
  installed `normalizer.obf.product@0.1`, not a hand-built `NormalizeContext`; `121 + 0 ==
  121`; all 121 rows are `0.3`/`product` and trace to the sealed snapshot; the field table and
  the `brands_tags` reconciliation are correct. F1 is the one to carry forward: the numbers
  are right today and nothing would notice them going wrong.

`[결정]` **Neither packet is `BLOCKED`.** Every item I was asked to verify was verified,
including the three the coordinator prioritized.

## Required follow-up

- New or revised packet: one, small — assert the four field-presence counts (or a floor and
  ceiling on each) so F1's mutant dies; and correct F6's fixture docstring.
- Open Question / Decision Packet: F2 belongs on TASK-003's `uuid4` tie-break open item, not
  retired by this evidence. F4 needs D6's sentence added to
  `evidence/obf-dataset/README.md` — orchestrator's edit, not the attacker's.
- Project State / contract: `PoC Contract 0.1` limitation 3 (*"No real dataset source
  exists"*) can be lifted on this evidence, with F4's line attached.
