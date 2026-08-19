# Judgment debt — opened 2026-08-18

`[결정]` The operator asked for the first goal to be reached in one pass, deciding
consequential-but-not-blocking questions at whatever point seemed most reasonable rather
than stopping at each, **on the condition that every such decision is written down here and
re-evaluated together once the goal is met.** This file is that condition. It is not a
Decision Packet and does not carry a Decision Packet's authority: an entry here is a choice
made under time pressure by the party who also implemented it, which is precisely the shape
`ADVERSARIAL-REVIEW-2026-08-18.md` exists to distrust.

**How to read an entry.** Each names what was decided, what the alternative was, what would
falsify the choice, and what it would cost to reverse. An entry whose reversal cost is high
is the one to look at first, because it is the one that stops being a choice soonest.

**The first goal**, as stated: the Naver API collector is really exercised, a normalizer
built to match it really runs, and both are really operable from the dashboard. The second
goal is the evaluation this file feeds.

`[측정]` **Reviewed on 2026-08-19.** Every entry below was re-examined against what has
happened since, in [DEBT-REVIEW-2026-08-19.md](DEBT-REVIEW-2026-08-19.md): D5 is resolved by
real-data runs, D2 is confirmed and worse than it predicted, D3 is unchanged and now
duplicated, and D1, D4, D6, D7, D8 are unchanged and untested. P1's own question — whether a
watched red would have caught anything the mutation checks missed — was answered **yes**:
the review found a fifth guard, copied rather than written, that the whole suite could not
see. Five new entries (N1–N5) are opened there rather than here, so that this file stays the
record of what was decided under the first goal.

---

## D1 — An exception from enlisted work is classified as permanent, not by SQLSTATE

**Where.** `platform_core/jobs/runner.py::_execute` (F2).

**Decided.** Enlisted durable work that raises goes down the same classification path as any
other handler failure: a `PlatformError` keeps its class, and anything else becomes
`PLATFORM_PERMANENT` via `_unclassified`.

**Alternative not taken.** Route `psycopg.Error` through
`platform_core.db.connection.classify`, so a serialization failure or a deadlock — genuinely
transient, and genuinely likely once several workers write domain tables concurrently —
would be retried instead of failing the job permanently.

**Why not.** `classify` needs `describe(config)` and the runner holds no config. Threading
one in is a change to `JobRunner`'s constructor and therefore to P0-A's evidence, and the
review's work item asked only that the exception stop escaping.

**Falsified by.** A P0-B concurrency run in which two collect jobs deadlock or serialize
against each other and are recorded `PLATFORM_PERMANENT`. `[가설]` Believed unlikely at P0-B's
scale — one worker, distinct sources — and this is the belief to test.

**Reversal cost.** Low. One classification branch inside `_execute`.

---

## D2 — The add-on-hosting worker is a second entrypoint, not the platform one

**Where.** New `addon_host/worker.py`; new `RegistryFor` seam in `platform_core/worker.py` (F3).

**Decided.** `python -m platform_core.worker` remains the source-neutral P0-A worker and runs
no add-ons. `python -m addon_host.worker` is the P0-B worker. `main()` is duplicated between
them, about two dozen lines.

**Alternative not taken.** One entrypoint that installs add-ons when the directory holds any.

**Why not.** DP-008 D1, enforced by `tests/environment/test_addon_layer_direction.py`:
`platform_core` may import nothing local. A single entrypoint means either the platform
importing `addon_host`, or a common helper module that both import — and the second is the
first with an extra file, because the helper would have to name both layers.

**What this costs, concretely.** Every document, script, and scenario that says "the worker"
now has two referents. `docs/p0-execution-plan.md` and the dashboard's operator instructions
have not been re-read for that ambiguity.

**Falsified by.** Anyone — a person or an agent — starting `platform_core.worker` for a
collect job and reading `HANDLER_UNKNOWN` as a defect rather than as the wrong entrypoint.

**Reversal cost.** Medium, and it rises. Every reference to an entrypoint written from here
on is a reference to disambiguate later.

---

## D3 — The durable-scope precondition tests the transaction, not the connection

**Where.** `addon_host/capabilities.py::_CollectRun._require_completion_transaction` (F3).

**Decided.** Before the durable work writes anything, the domain connection must report an
open transaction (`INTRANS`/`ACTIVE`/`INERROR`). Anything else is `ConfigurationInvalidError`.

**Alternative not taken.** Compare connection identity — `domain.connection is
job_store.connection` — which is the property H2a actually rests on.

**Why not.** The capability layer never sees the `JobStore`; giving it one couples the
add-on host to the platform's job internals, and passing the connection down to it through
`JobContext` would put a database handle within reach of an add-on, which DP-008 D4 forbids
in as many words.

**What it does not catch.** A `DomainStore` on a *different* connection that happens to be
inside a transaction of its own. Contrived, and not impossible: a future host that wraps its
own work in a transaction would pass this check while writing outside the fence.

**Falsified by.** Any wiring in which two connections are both in transactions during one
attempt.

**Reversal cost.** Low while there is one host. It rises the moment a second one exists.

---

## D4 — Add-on discovery re-runs on every database reconnection

**Where.** `addon_host/worker.py::capability_registry` (F3).

**Decided.** The handler table is rebuilt per connection, so `load_addons` re-reads the
directory and re-runs the version gate after every transient database failure.

**Why.** It is the price of D3's stricter property: a table built once outlives the
connection its handlers write on.

**What it costs.** Directory I/O and module re-import on a path that is meant to be rare. An
add-on directory edited between a failure and a reconnection changes what the process runs,
mid-life, with nothing announcing it.

**Falsified by.** A reconnection storm making discovery visible in the worker's latency, or
a scenario in which mid-life reload produces a result nobody can attribute.

**Reversal cost.** Low.

---

## D5 — `max_request_seconds` is 60, chosen rather than derived

**Where.** `domain/outbound.py::DEFAULT_LIMITS` (F5).

**Decided.** One `fetch` — every redirect hop and every connection attempt — gets 60 seconds.

**Alternative not taken.** Derive it as `(connect_timeout_s + read_timeout_s) × (max_redirects
+ 1)`, which is 140s under the defaults and needs no new number.

**Why not.** The derivation is the arithmetic of the worst case rather than a bound anyone
wants, and it moves when unrelated limits move — a bound that drifts with its neighbours is
the shape F5 was about.

**What is not known.** Whether 60s is enough for the real Naver API under ordinary latency.
No capture of that source exists; the collector's own docstring says so.

**Falsified by.** A real-data run in which a legitimate page is cut off at the budget.

**Reversal cost.** Trivial — one number, and a per-source override already exists.

---

## D6 — A dot segment in a redirect is refused, not normalized

**Where.** `domain/outbound.py::comparable_segments` (F4).

**Decided.** A `Location` whose path carries `.`, `..`, `%2e`, or `%2f` is refused as
`PATH_NOT_ALLOWED` rather than resolved and then compared.

**Alternative not taken.** Apply RFC 3986 §5.2.4 remove_dot_segments and compare the result.

**Why not.** Normalizing means predicting which of several defensible decodings the far end
performs — nginx, Apache, and a bare application server do not agree about `%2f` — and being
wrong in the permissive direction is the hole F4 walked through. Refusing is wrong only in
the direction that costs a collection.

**What it costs.** A source whose server legitimately redirects through a dot segment cannot
be collected at all, and the refusal will read as a security event rather than as an
incompatibility.

**Falsified by.** A real source doing exactly that. `[가설]` Believed rare; untested.

**Reversal cost.** Low, and the refusal is loud, so the falsifying case reports itself.

---

## D7 — An approved path that cannot be compared is refused at `resolve`, not only at redirect

**Where.** `domain/outbound.py::resolve` (F4). Changed the meaning of an existing test.

**Decided.** A `source.outbound_profile` endpoint path carrying a dot segment is refused on
the *first fetch*, rather than being sent and then making every redirect from it undecidable.

**What this changed.** `test_a_path_traversal_in_an_approved_path_cannot_leave_the_host`
asserted that such a path is prepared and sent, on the reasoning that where it lands is the
operator's business as long as the host is approved. That reasoning is still sound and is
now insufficient. The test was rewritten and the property it used to carry was kept as a
separate assertion, so tightening one rule did not quietly retire another.

**`[추론]` This is the entry a reviewer should be most suspicious of**, because it is the one
where the implementer changed an existing test to match new code. The old assertion is
preserved verbatim in the new test's docstring so the change can be judged rather than taken.

**Reversal cost.** Low.

---

## D8 — The page and record limits refuse rather than stop

**Where.** `addon_host/capabilities.py::_fetch`, `::_emit_raw` (F1).

**Decided.** Running past `max_pages` or `max_records` is an outbound `Refusal` — the job
fails permanently and unswallowably, exactly like an unapproved host.

**Alternative not taken.** Stop the run quietly at the limit and report success with
`more_available=True`, which is what `CollectOutcome` already has a field for.

**Why not.** A run that reported success at the limit is indistinguishable from one that
reached the end of the data, and the cursor it leaves behind says nothing about which. The
committed Naver collector already stops at `max_pages` on its own and sets
`stopped_reason="max_pages"`, so the cooperating path is unaffected — the refusal is what
happens to an add-on that does *not* cooperate.

**What it costs.** An add-on author who treats the limit as advice loses a whole collection
rather than part of one.

**Falsified by.** A source whose natural paging cannot be bounded in advance, where the
operator wants partial collection rather than a failure.

**Reversal cost.** Low, but it is a contract change: `addon_api.context.Limits` now promises
enforcement in the present tense, and that sentence has been wrong once already.

---

## P1 — Process failure: production code written before a watched failing test

**Not a judgment call. A discipline failure, recorded here because this file is where the
things done under time pressure go.**

`[확인 사실]` `domain/secrets.py` and the credential half of `domain/outbound.py` were
written **after** their tests existed but **before** any of those tests had been watched to
fail for a behavioural reason. The only red observed was an `ImportError` at collection —
which is an error, not a failure — and all twenty assertions passed on their first run. The
same happened to `addon_host/worker.py` and the `RegistryFor` seam, whose only observed red
was `ModuleNotFoundError`.

`[추론]` The failure mode this invites is precise and is the one the whole repository is
organised against: a test written beside its implementation asserts what the code does, and
a test that has never failed is not evidence that it can fail. `ADVERSARIAL-REVIEW-2026-08-18.md`
F1 is exactly that shape — an integration test that passed while proving only that the
add-on cooperated.

**What was done about it.** Both units were deleted and rebuilt from their tests in three
steps, each step watched: a skeleton with the names and no behaviour produced **15 failing
assertions**, then store reading took it to 5, then the two store guards to 2, then the
outbound half to 0. Nothing was kept as reference.

**What was done about the ones already written.** Deleting and rebuilding
`platform_core/worker.py`'s seam would have discarded work whose tests do pass, so instead
each claim was checked by mutation — the cheaper substitute, and a weaker one:

| Guard removed | Result |
|---|---|
| `if header.lower() not in PROTECTED_HEADERS` (DP-018 D3) | RED |
| `if not _KEY_NAME.match(ref)` | RED |
| `if self._registry_for is not None` (F3's seam) | RED |
| `_require_completion_transaction()` call (F3's guard) | RED |

`[추론]` A mutation surviving would have proved the test vacuous; a mutation dying proves
only that *something* in the test reaches the line. It is weaker evidence than a watched
red, and the four above are recorded as carrying that weaker evidence rather than as being
equivalent to the rest.

**Reversal cost.** None — the debt is informational. What it costs is confidence, and the
re-evaluation should ask whether any defect later found in these four units was of a kind a
watched red would have caught.

---

## Open, and not decided here

These were met and deliberately left alone, because deciding them silently is what
`AGENTS.md` forbids rather than what it tolerates:

- **Credential attachment (OQ-009).** No add-on and no source can carry a working credential
  yet. This blocks a real request to the Naver API and is the first thing the goal needs.
- **Where normalized results live (OQ-004).** `_UNBOUND_KINDS` still refuses every
  normalizer, and it refuses with the reason stated: `0002_domain.sql` creates no table for
  a result. A normalizer that really runs needs that table, which is a contract question.
- **Multi-stream cursors (OQ-010).** Unchanged.
- **Findings F6 to F10** of the adversarial review remain unrepaired and are listed with
  their status in that document.
