# Review of the judgment debt and the process failure — 2026-08-19

- Reviews: [JUDGMENT-DEBT-2026-08-18.md](JUDGMENT-DEBT-2026-08-18.md), entries D1–D8 and P1
- Reviewer: **the party that wrote every entry and every line they are about.** This is not
  an independent axis and does not claim to be — see below.
- Outcome: **one entry falsified, one confirmed, one materially worsened, five unchanged.**
  One new defect found and repaired, and **five new debt entries** opened.

## What a self-review can and cannot establish

`[결정]` The whole reason `ADVERSARIAL-REVIEW-2026-08-18.md` exists is that *"the implementer
and the author of every claim under review are the same party, so `27f712b` had no
independent axis."* That is exactly the position this document is in, and stating it is not
a formality: the failure mode it warns about — an author's blind spot surviving their own
inspection — is the one this review is least able to detect.

So the review is built to depend on opinion as little as possible. Every entry below is
resolved by one of three things:

1. **A measurement taken now.** A mutation re-run, a line count, a file count.
2. **An event since the entry was written.** A real-data run, a new module, a guard firing.
3. **"Unchanged and untested"**, said plainly where neither of the first two applies.

`[추론]` What that still cannot reach is a decision that is wrong in a way none of these
measurements is shaped to notice. Four of the eight entries end in "unchanged and untested",
and those four are where an independent reviewer would be worth the most.

---

## The finding

### A guard with nothing behind it, written after reading the review that named that shape

`[측정]` Re-running F3's own mutation against the current tree:
`_NormalizeRun._require_completion_transaction` — the check that a normalizer's results are
written inside the transaction that completes the attempt — **could be deleted entirely and
all 1070 tests still passed.**

```
call sites remaining: 1     (the collector's; the normalizer's removed)
1070 passed, 14 skipped
```

`[추론]` This is F1's and F3's shape precisely: a control that exists, reads correctly, and
is held up by nothing. It was written on 2026-08-18, *after* the review that named that
failure mode, by the party that had just repaired two instances of it. The mechanism is
worth stating because it is not carelessness and will recur: `_NormalizeRun` was written as
a sibling of `_CollectRun` and the guard was copied across with the rest. **Copying a guard
duplicated the code and not the evidence** — the collector's test still passed, so nothing
about the copy looked untested.

**Repaired.** `TestTheDurableScopeRequirementIsCheckedForNormalizersToo` now runs a
normalize job with its `DomainStore` on a separate autocommit connection, and it is
mutation-checked in both directions: with the guard removed the refusal case fails, with it
restored both cases pass.

`[결정]` The generalisation is recorded as **N5** below rather than fixed once: any guard
that exists in two places needs a test in two places, and nothing in this repository checks
that today.

---

## The eight entries

### D1 — enlisted-work exceptions classified as permanent, not by SQLSTATE — **unchanged, untested**

No concurrency run has happened. `[가설]` The entry predicted the case is unlikely at P0-B's
scale — one worker, distinct sources — and nothing since has tested it either way. The
operator loop runs two workers **sequentially**, so it is not the falsifier.

`[추론]` Its falsification is now *cheaper* than when it was written: two DataLab sources
plus a blog source exist, and a scenario that collects all three concurrently would produce
the contention this entry is about. Recorded as the next cheap experiment rather than done.

### D2 — the add-on worker is a second entrypoint — **confirmed, and worse than predicted**

The entry said the reversal cost was "medium, and it rises". `[측정]` It has:

```
platform_core/worker.py        platform_core/api/__main__.py
addon_host/worker.py           addon_host/__main__.py
```

**Four entrypoints, not two.** The domain API surface hit the same DP-008 D1 wall the worker
did and took the same shape — a source-neutral seam in `platform_core`
(`create_app(extend=…)`, matching `RegistryFor`) plus a composing entrypoint in
`addon_host`. The pattern is now consistent, which is the good half; the ambiguity the entry
warned about has doubled, which is the other.

`[측정]` The predicted symptom has already appeared once: `test_operator_loop.py` starts
`python -m addon_host` and `python -m addon_host.worker`, and a reader who reaches for
`platform_core.worker` gets `HANDLER_UNKNOWN` — the entry's own falsifier, now reachable
from a test file rather than hypothetically.

`[결정]` **Not reversed.** DP-008 D1 is enforced by a test and the alternative is either
breaking it or introducing a helper module that names both layers, which is the same
coupling with an extra file. What is done instead is naming: `README.md` now states the
P0-B entrypoints in its own section rather than leaving them to be discovered. The P1
reconstruction plan should decide whether P1 has one entrypoint or keeps the split, and it
should decide it deliberately rather than inheriting this.

### D3 — the durable-scope precondition tests the transaction, not the connection — **unchanged, and now duplicated**

The check is still the weaker of the two — it would pass a second connection that happened
to be inside a transaction of its own. Nothing since has produced that case.

`[측정]` What has changed is that there are now **two copies** of it, and until today only
one was tested. See the finding above. The entry predicted "reversal cost low while there is
one host; it rises the moment a second one exists" — a second *run* rather than a second
host, and the cost landed as predicted.

### D4 — add-on discovery re-runs on every reconnection — **unchanged, untested**

No reconnection has happened in any scenario. `[추론]` The cost is still theoretical and the
mid-life-reload concern still unobserved.

### D5 — `max_request_seconds` is 60, chosen rather than derived — **falsified as a worry, confirmed as a number**

`[측정]` The entry's open question was *"whether 60s is enough for the real Naver API under
ordinary latency"*, with the falsifier "a real-data run in which a legitimate page is cut
off at the budget." Three collectors have now run against the real API, and none came close:
one blog collection of two pages, one Search Trend call, and one Shopping Insight call all
completed inside single-digit seconds, with no `TransportUnavailable` and no retry.

`[결정]` **Resolved for the selected sources.** The number stays 60 and the per-source
override stays available. What this does *not* establish is behaviour under a degraded
network or against a source that streams a large body — the drip case is covered by a stub
and not by the provider.

### D6 — a dot segment in a redirect is refused, not normalized — **unchanged, untested**

`[측정]` No real response from any of the three endpoints carried a redirect at all, so the
refusal has never fired against a real source. `[가설]` "Believed rare" is still believed and
still untested.

### D7 — an approved path that cannot be compared is refused at `resolve` — **unchanged**

No committed profile carries a dot segment. The entry flagged itself as the one to be most
suspicious of, because it changed an existing test to match new code; that assessment stands
and nothing has moved it either way.

### D8 — page and record limits refuse rather than stop — **unchanged, and the DataLab collectors do not exercise it**

`[측정]` Both DataLab collectors make **exactly one request per run**, so `max_pages` is
never approached and the refusal path is untested against them. The blog collector stops
voluntarily at `max_pages` as before, and the platform's counter is exercised only by the
deliberately-uncooperative add-ons in `test_capabilities.py`.

`[추론]` So the entry's cost — "an add-on author who treats the limit as advice loses a whole
collection rather than part of one" — remains a real risk that no real add-on has met. The
new collectors have a *different* stopping shape worth noticing: when the cursor has caught
up they return zero items and make **no request at all**, which is the behaviour D8's
alternative (stop quietly, report `more_available`) would have produced everywhere. Neither
path has been wrong yet.

---

## P1 — the process failure

`[측정]` All four units that carry the weaker mutation-only evidence were re-checked, and
all four still die when their guard is removed:

| Guard removed | Result |
|---|---|
| `if header.lower() not in PROTECTED_HEADERS` (DP-018 D3) | RED |
| `if not _KEY_NAME.match(ref)` | RED |
| `if self._registry_for is not None` (F3's seam) | RED |
| `_require_completion_transaction()` — **collector's copy** | RED |
| `_require_completion_transaction()` — **normalizer's copy** | **GREEN — the finding above** |

`[추론]` So the entry's own question — *"whether any defect later found in these four units
was of a kind a watched red would have caught"* — has an answer, and it is **yes, in the
fifth**. The four originals held. The one that did not is the one that was *copied* rather
than written, and copying is precisely the act a watched red would have interrupted: a test
written first for `_NormalizeRun` would have had to fail first, and a copied guard cannot
fail a test that does not exist.

**Two counter-observations, recorded because they cut the other way:**

`[측정]` Writing test-first caught two real defects in this session that no review would
have. `normalizer.naver.blog` never called `emit_result` — its outcome reported one result
and it emitted none — and the watched RED found it at the add-on rather than leaving it to
the host's count cross-check. And `test_dashboard.py`'s section-delimiter guard caught a
refactor that moved a constant out of the file it was reading.

`[측정]` The repository's existing guards fired **four times** this session without being
asked to: the `allow_loopback` scan twice, the domain-table list once, and the delimiter
guard once. Each time the correct response was to read the guard and register the change,
not to widen the scan. `[추론]` That is evidence that this repository's convention of
listing rather than globbing is paying for itself, and it is the strongest thing the session
produced in favour of the existing process.

**Status: the entry stands, with its question answered.** It should not be closed — it is
the record of how the fifth guard got there.

---

## Five new entries, opened by this session

### N1 — the two DataLab collectors are 72% identical, and must be

`[측정]` Ignoring docstrings and comments: 210 code lines in `collector.naver.searchtrend`,
244 in `collector.naver.shoppinginsight`, **153 identical** — 72% of the smaller. Date
parsing, the day-after arithmetic, the cursor protocol, the segment filter, the response
classification, and the unrolling are the same code twice.

**Why it cannot be factored.** An add-on may import `addon_api` and nothing else in this
project (DP-008 D1, enforced by `test_addon_layer_direction.py`). A shared module would be a
fourth local package that add-ons import, which is the coupling the add-on boundary exists
to prevent.

`[추론]` **This is architectural evidence and belongs in the Architecture Synthesis rather
than in a refactor.** DP-008's premise is that a new source is a directory, not platform
code. It is — and the cost, measured, is that the third add-on against one provider
duplicates two thirds of the second. The options are a code generator, a documented
template, a vendored helper copied per add-on, or widening the import rule; each answers a
different question about what an add-on *is*, and P0-B should not pick one by accident.

**Reversal cost.** Rising with every add-on. Two exist today.

### N2 — three config fields carry JSON inside a string

`[측정]` `keyword_groups`, `categories`, and `keywords` are structured values in
`type = "string"` fields, because `[config.field]` has only `string`, `integer`, and
`boolean`. Each add-on re-implements the same parse-and-validate.

`[추론]` The visible consequence is that an operator form cannot render them, so the
dashboard shows a JSON blob in a text box and a typo is a runtime `AddonConfigInvalid`
rather than a form error. That is a **contract gap in `addon_api`**, not an add-on defect,
and it is the first one found by writing an add-on the contract's authors did not have in
mind. Falsified by an add-on whose structured configuration fits the three scalar types.

### N3 — Schema 0.1 and 0.2 coexist, and nothing states which a reader should expect

`[결정]` DP-021 D5 keeps `normalizer.naver.blog` at `output_contract_version 0.1` and puts
`normalizer.naver.trend` at `0.2`, which is correct per-add-on and means the
`normalized_result` table holds both. `[추론]` That is coexistence working as DP-019 D3
intends, and it also means a reader querying the table gets two record shapes with no
declared rule for which. The dashboard reads fields by name and tolerates absence, so
nothing breaks — and "nothing breaks" is not the same as "a consumer knows what it has".

### N4 — Shopping Insight is 2 of about 10 documented endpoints

`[결정]` `categories` and `category/keywords` are implemented; the age, gender, and device
breakdowns are not. Deliberate — nothing in P0-B needs them and an add-on declaring
endpoints no source uses would be requesting a grant nobody reviewed — and recorded because
"the Shopping Insight collector works" is true of a fifth of that API.

### N5 — nothing checks that a duplicated guard is duplicated in its tests

The finding above, generalised. `[가설]` A cheap check exists — every call site of a
`_require_*` guard should appear in at least one mutation-killed test — and nothing
implements it. Falsified by a third copy of a guard appearing untested.

---

## What this review did not do

- **It did not re-examine the decisions themselves**, only what has happened to them. D6 and
  D7 in particular are choices about outbound policy that would benefit from someone who did
  not make them.
- **It did not run the adversarial mutations F6 listed.** Those seven findings are still
  open in `ADVERSARIAL-REVIEW-2026-08-18.md`, and F6 is the one that would most likely find
  another N5.
- **It measured no performance and no failure behaviour under load.** D1 and D4 both end in
  "untested" for that reason.
