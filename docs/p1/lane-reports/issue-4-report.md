# Issue #4 — `apply_effect` carried no fence

- Branch: `platform/issue-4-effect-fence`
- Date: 2026-08-21

## Verdict

**CONFIRMED.**

`APPLY_EFFECT` (`experiments/integrated-p0/platform_core/jobs/store.py:346-351`, copy-adapted
byte-for-byte into `apps/platform_core/jobs/store.py`) was a bare
`insert into cosmai.platform_effect ... on conflict (effect_key) do nothing`, built from no fence
and taking no `attempt_id`/`worker_id`. Every caller (`JobContext.apply_effect`, wired in
`runner.py`'s `_effect_applier`, which closed only over `claimed.job_id`) invoked it directly from
inside a handler, mid-attempt — never through the DP-010 buffered-emit path
(`enlist_durable_work`/`durable_scope`), which only ever carries `addon_host/capabilities.py`'s
`_flush(...)` calls and was already correctly fenced (it runs inside the same transaction as the
completion). Reused `effect_key_for`'s attempt-independence, which the abandoned attempt's insert
exploited exactly the way CONTRACT-JOB-0.1's fencing rule (§Semantics:126-128) exists to prevent
for every other write.

## Mechanism

An abandoned attempt's `apply_effect` bypassed the ownership check the platform applies to every
other write (job `RUNNING`, lease held by the calling worker, that worker's own attempt still
open). Because the insert used `on conflict do nothing` with no such check, whichever call
*arrived* at the database first — not whichever attempt the platform currently credits with
finishing the job — was the one that landed; a later, legitimate write from the actually-current
attempt was silently treated as "the duplicate" and suppressed.

## Reproduction (Phase 1, against the real database)

Run unsandboxed against `cosmai_test` on `127.0.0.1:5434` (`COSMA_DB_HOST=127.0.0.1
COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test COSMA_DB_USER=cosmai_runtime
../scripts/with-secret-source.sh uv run python -m pytest`), before any fix:

```
job = create_job("succeed", {}, max_attempts=3)
stale     = claim_next("worker-A", lease_seconds=0.0)   # expires immediately
reclaimed = claim_next("worker-B", lease_seconds=30.0)   # reclaims; closes A's attempt ABANDONED

complete_success(reclaimed.job_id, reclaimed.attempt_id, "worker-B")
# -> accepted; job SUCCEEDED

complete_success(stale.job_id, stale.attempt_id, "worker-A")
# -> REFUSED (fence works correctly for completions): "the completion was refused:
#    this worker no longer holds the lease, or its attempt is already closed"

apply_effect(job.id, f"job/{job.id}", {"applied_by": "worker-A", "attempt_no": 1})
# -> True. Inserted without complaint.
#    platform_effect row: {"applied_by": "worker-A", "attempt_no": 1}

apply_effect(job.id, f"job/{job.id}", {"applied_by": "worker-B", "attempt_no": 2})
# -> False. Suppressed as "already present" -- B's own, legitimate write never lands.
#    platform_effect still has exactly the row A wrote.
```

Observed rows matched the issue's "How to see it" section exactly: the completion fence correctly
refused worker A everywhere it was checked; `apply_effect` had no equivalent check anywhere, and
the abandoned attempt's payload was what stayed durable.

## Fix (Phase 2, P1 tree only — `apps/`)

`apps/platform_core/jobs/store.py`:

- Split the old `_FENCE` into `_FENCE_CHECK` (the ownership check — job `RUNNING`, lease held by
  this worker, this worker's attempt still open, under `for update of j`) and `_ATTEMPT_CLOSE`
  (the completion-only half that closes the attempt). `_FENCE = _FENCE_CHECK + _ATTEMPT_CLOSE`
  reproduces the prior three `COMPLETE_*` statements byte-for-byte.
- `APPLY_EFFECT` is now `_FENCE_CHECK` plus an insert gated on the `fenced` CTE, in the same
  CTE-concatenation style as the three `COMPLETE_*` statements. `on conflict (effect_key) do
  nothing` stays *inside* the fenced write — I1's idempotency is still the primary key's job, the
  fence's job is only to stop a stale attempt's insert from being the one that lands. The
  statement also returns a `fenced_ok` boolean (via a scalar subquery against the
  at-most-one-row `fenced` CTE) so a fence miss and a duplicate-suppression — both of which leave
  the insert's own `returning` empty — can be told apart.
- `apply_effect(job_id, attempt_id, worker_id, effect_key, payload=None) -> bool` gained the two
  identifiers the fence needs. A fence miss is refused the same shape a rejected completion is:
  `REJECTED_REASON` (reworded generically for "a write," since it now covers both), counted via a
  new `MetricsRegistry.record_rejected_effect()` / `reading.rejected_effects`, and logged as
  `job.effect_rejected` — distinct from the pre-existing `job.effect_suppressed` (I1's duplicate
  path, unchanged in shape).
- `runner.py`'s `_effect_applier` now closes over `claimed.attempt_id` and `claimed.worker_id` in
  addition to `claimed.job_id`. `JobContext.apply_effect`'s handler-facing type
  (`Callable[[str, Any], bool]`) is unchanged — the identifiers are platform state a handler never
  sees, the same as `complete_success`. No handler code (`synthetic.py`) needed to change.

`apps/platform_core/obs/metrics.py`: added `rejected_effects` alongside `rejected_completions`
(counter, `MetricsReading` field, `as_dict()` key, `reset()`).

## Contract check

CONTRACT-JOB-0.1 §Semantics:126 already states the obligation unqualified by which write: "A
worker's attempt to record any outcome — success, failure, or reschedule — is accepted only if
that worker still owns the current lease and its own attempt row is still open. Otherwise the
write is refused." §Semantics:151 separately calls `platform_effect` a "durable effect." **No
contract change** — the code was out of contract; this fix brings it into contract, at the same
version (`0.1`), with no scenario re-run required because no `PASS`ed result is invalidated (only
`APPLY_EFFECT`'s implementation changed, and no scenario's recorded result depended on its being
unfenced).

## Deviation named

`store.py`'s own module docstring previously claimed P0 and P1's SQL differ only by schema
qualification. That is no longer true for `APPLY_EFFECT` — P1's version is fenced and its
signature grew two parameters; P0's is unchanged (read-only archive; the issue stays open against
it by design). The docstring and `docs/p1/M1-RECORD.md`'s contract deviation ledger (item 10) both
record this explicitly, including that the root `tests/acceptance/JOB-006-...md` scenario document
is a P0-A gate record and is left untouched: it accurately describes what P0's code did, and this
fix does not retroactively change that.

`apps/tests/acceptance/test_job_scenarios_concurrency.py::test_job_006_...`'s own assertions
changed from `suppressed_duplicate_effects == 1` for the stalled worker to `rejected_effects ==
1`: under the old code, worker A's late `apply_effect` call in that scenario happened to be
suppressed because it arrived *after* B's write; under the fix, A's attempt is fenced out
regardless of arrival order (A's own attempt row was already closed `ABANDONED` by B's reclaim by
the time A calls `apply_effect`), which is the actual mechanism the scenario is meant to
demonstrate.

## Tests added (`apps/tests/test_jobs_store.py::TestApplyEffect`)

- `test_the_first_application_is_accepted` — positive control, updated to claim first and pass
  the new identifiers; a live attempt's `apply_effect` still succeeds.
- `test_a_repeat_key_is_suppressed_and_counted` — same-key second write still no-ops, now also
  asserting `rejected_effects == 0` (the suppression path is unaffected by the fence).
- `test_two_different_jobs_can_share_one_key` — updated for the new signature.
- `test_an_abandoned_attempts_effect_is_refused_and_the_reclaiming_attempts_lands` — the Phase-1
  reproduction as a regression test: B applies its effect while its own attempt is open (the real
  `runner._execute` order) and completes; A wakes only afterward and is refused, counted, and
  logged; B's write is the only row that ever lands.
- `test_the_fence_tests_ownership_not_expiry_for_effects_too` — a lease that ran out but was never
  reclaimed still belongs to its worker; `apply_effect` succeeds, mirroring the existing
  completion-fencing test of the same name.
- `test_a_rejected_effect_write_leaves_the_job_row_unchanged` — the fence refusal is a no-op,
  field by field, not merely "no exception."

`apps/tests/test_obs.py::TestMetrics` — extended for the new `rejected_effects` counter (fresh
registry reads zero, independent counting, `as_dict()` key set, reset).

## Gates

- `cd apps && uv run mypy --strict .` — clean, 104 source files.
- `cd apps && uv run ruff check .` — all checks passed.
- `cd apps && uv run python -m pytest -q` (unsandboxed, real DB) — **1130 passed, 1 skipped**
  (1127 baseline + 3 new `TestApplyEffect` tests).
- Root guard: `.venv/bin/python -m pytest tests/environment -q` — **87 passed**.

## Files changed

- `apps/platform_core/jobs/store.py`
- `apps/platform_core/jobs/runner.py`
- `apps/platform_core/obs/metrics.py`
- `apps/tests/test_jobs_store.py`
- `apps/tests/test_obs.py`
- `apps/tests/acceptance/test_job_scenarios_concurrency.py`
- `docs/p1/M1-RECORD.md` (contract deviation ledger, item 10)
- `.superpowers/sdd/2026-08-21-m2-m7-batch/issue-4-report.md` (this file)
- `docs/p1/lane-reports/issue-4-report.md` (copy)
