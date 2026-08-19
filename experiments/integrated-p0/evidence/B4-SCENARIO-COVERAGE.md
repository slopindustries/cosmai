# P0-B B4 — real-data integration and failure evidence

- Status: `COMPLETE with named gaps`
- Date: 2026-08-19
- Work package: [`docs/p0-execution-plan.md`](../../../docs/p0-execution-plan.md) B4
- Suite at the time of writing: **1192 passed, 14 skipped**; `ruff` and `mypy --strict` clean

B4 lists ten failure classes P0-B must *deliberately exercise*. This file is the map from
that list to the executable evidence, and — more usefully — to the places where there is
none. `[결정]` A row saying `NOT EXERCISED` is the point of the document. A coverage table
that only listed hits would be the same table for a suite that tested nothing.

Every named test is in `experiments/integrated-p0/tests/` unless stated.

---

## 1. Identical and changed input

| | |
|---|---|
| Covered | `test_naver_real_data.py::TestTheNormalizerRunsOnRealData::test_normalizing_the_same_snapshot_twice_is_refused_rather_than_doubled` — the unique index on `normalized_result`, against real captured data |
| | `test_normalized_results.py::TestDeterminism` — the same snapshot and version produce byte-identical canonical results |
| | `test_domain_store.py::TestCursor::test_a_cursor_is_stored_opaquely_and_returned_unchanged` |
| | `test_migrations.py::test_applying_the_shipped_migration_twice_is_safe` |
| Gap | `[측정]` **A second collection over changed remote data is not exercised.** Blog search returns whatever is most recent, so a re-run *does* produce changed input — but no test asserts what the pipeline does with the overlap, because the digests differ by design and there is nothing stable to assert against. What identity means across two captures of a moving source is unmeasured. |

## 2. Retryable and permanent source failures

| | |
|---|---|
| Covered | `test_job_failure_paths.py::test_job_002_*` (retryable, rescheduled), `test_job_003_*` (exhaustion is terminal), `test_job_004_*` (permanent is not retried) |
| | `test_capabilities.py::TestTheGuardRefuses::test_a_transport_failure_is_transient_rather_than_permanent` |
| | `test_collector_naver_blog.py::TestPagination::test_a_result_missing_its_documented_link_field_is_a_permanent_failure` |
| | `test_durable_scope.py::TestEnlistedWorkThatFails::test_a_retryable_failure_inside_enlisted_work_returns_the_job_to_the_queue` |
| Gap | `[측정]` **No real source failure was ever observed.** Every failure above is synthetic or a stub. `SRC-001` returned `200` to every request that was well-formed and a real `401`/`SE01` to those that were not; it never rate-limited, never timed out, and never returned `5xx`. The retry machinery is tested; it has not met a real provider failing. |

## 3. Malformed and partially invalid dataset rows

| | |
|---|---|
| Covered | `test_importer_local_jsonl.py::TestMalformedAndPartiallyInvalidRows` — five cases: malformed JSON; valid JSON that is not an object; a row missing the key field; a file of nothing but bad rows; blank lines as the control |
| | `test_input_registry.py` — 15 cases on the approved-input registry itself |
| Note | `[확인 사실]` This row was **impossible to exercise before 2026-08-19**. `importer` was refused by name until [DP-024](../../../docs/decisions/DP-024-local-input-registry.md) defined the registry of approved local inputs. |
| Gap | `[측정]` **The rows are self-authored** ([SRC-002](../../source-probes/SRC-002-local-jsonl.md)). Encoding surprises, embedded newlines inside quoted strings, and duplicate row identities within one file are **not** exercised. |

## 4. Duplicate delivery and process interruption around durable effects

| | |
|---|---|
| Covered | `test_job_interruption.py::test_job_005_*` — a killed process leaves the attempt open and the lease held; recovery abandons the first attempt and succeeds on the second; **exactly one effect in both cases**; the correlation id survives the restart |
| | `test_domain_store.py::TestCollectionIsAtomic::test_an_interruption_before_completion_leaves_no_raw_and_no_cursor`, plus its own negative control `test_the_interruption_test_is_not_passing_because_nothing_was_written` |
| | `test_capabilities.py::TestACollectionIsAtomicThroughAnAddOn` — the same property through a real add-on |
| | `test_ops.py::test_ops_002_case_a_the_effect_count_is_unchanged_and_the_suppression_counted` |
| Strength | `[측정]` Reverting the F2 `_settle` repair produced **91 failures and 111 errors**. This area is the most thoroughly pinned in the suite. |

## 5. Parallel claims and lease recovery

| | |
|---|---|
| Covered | `test_db.py::test_isolation_holds_under_parallel_workers`, `test_a_lease_belongs_to_a_running_job_and_to_no_other` |
| | `test_job_concurrency.py::test_job_007_*` — 200 jobs across 4 processes |
| | `test_domain_store.py::TestCollectionIsAtomic::test_a_worker_that_lost_its_lease_persists_neither_raw_nor_cursor` and its positive control |
| | `test_capabilities.py::TestACollectionIsAtomicThroughAnAddOn::test_a_reclaimed_worker_persists_neither_raw_nor_cursor` |
| Fixed here | `[측정]` `job.claim_conflict` reported conflicts that never happened and made `test_job_002` fail 2 times in 30 runs. Repaired 2026-08-19 by folding the probe into `CLAIM_NEXT`; **0 failures in 30 runs** after. |
| Gap | `[측정]` **JOB-007 is load-sensitive.** Its 30-second settle budget for 200 jobs × 4 processes times out under CPU contention — three standalone runs under load gave 1, 3 and 1 failures; unloaded it passes. The scenario measures the machine as well as the code. |

## 6. Normalization failure after Raw persistence

| | |
|---|---|
| Covered | `test_normalizer_capability.py::TestOutputIsChecked` — a normalizer that miscounts, one naming an item the snapshot does not hold, one returning the wrong type (refused **by name**, not merely failing) |
| | `test_normalizer_capability.py::TestTheDurableScopeRequirementIsCheckedForNormalizersToo` |
| | `test_normalizer_capability.py::TestTheNormalizersOwnSourceRowIsChecked` — added 2026-08-19; the four guard clauses that were GREEN on this side |
| Property | `[확인 사실]` Raw is sealed before normalization starts (DP-019 D6), so a normalization failure cannot destroy Raw. That is structural, not a test outcome. |

## 7. Snapshot or manifest mismatch

| | |
|---|---|
| Covered | `test_normalizer_capability.py::TestTheInputIsSealedAndVerified::test_a_tampered_snapshot_fails_the_run_before_the_add_on_sees_a_byte`, with `test_an_untampered_snapshot_of_the_same_shape_runs` as the control |
| | `test_domain_api.py::TestSealingASnapshot::test_a_tampered_snapshot_says_so_and_names_the_problem` |
| | `test_domain_store.py::TestSnapshot::test_a_sealed_snapshot_verifies`, `test_a_sealed_snapshot_reads_back_in_the_order_it_fixed` |
| Real data | `[측정]` Two real captures were sealed and their manifest digests recorded — `sha256:03b9b9a0…` and `sha256:9120748d…`. |

## 8. Invalid normalizer output

| | |
|---|---|
| Covered | See row 6 — `MISCOUNTING`, `ORPHANING`, `WRONG_RETURN` |
| | `test_addon_harness.py::TestConformanceNormalizer` — strict and lenient modes over unparseable items |
| | `test_normalized_results.py` — the schema discriminated union, Schema 0.1 and 0.2 |

## 9. Dashboard diagnosis and safe retry

| | |
|---|---|
| Covered | `test_ops.py::test_ops_001_*` — six diagnostic questions answered from API responses alone |
| | `test_ops.py::test_ops_002_*` — safe retry: a refused retry leaves the job row unchanged **field by field**; an accepted retry keeps the correlation id and numbers the attempt above every earlier one; the effect count is unchanged and the suppression counted |
| | `test_dashboard.py::test_sec_004_*` — ten cases, including that a refused retry shows the current and the required state, and that no marker under a redacted key reaches the markup of any screen |
| | `test_operator_loop.py` — the four-act operator loop end to end |
| Real data | `[측정]` The dashboard rendered real normalized rows from the NAVER captures on 2026-08-19. |

## 10. Credential, redaction, outbound-policy, redirect, DNS, response-bound, loopback

| Sub-scenario | Evidence |
|---|---|
| Credential | `test_outbound_transport.py::test_the_gateway_received_both_credential_headers`, `test_no_recorded_envelope_carries_a_credential_value`, `test_no_recorded_envelope_carries_a_protected_header`, `test_without_the_store_the_run_fails_rather_than_collecting_an_error_body`; `test_credentials.py`; `test_secret_store_guard.py`; `test_addon_credential_hygiene.py` (every installed add-on, added 2026-08-19) |
| Redaction | `test_redaction.py` including the contract key-set pin added 2026-08-19; `test_dashboard.py::test_sec_004_*`; `test_api.py` |
| Outbound policy | `test_outbound_policy.py` — an unapproved host, an unapproved path, a profile approving no host, a second host through the body, method allowlist, protected-header precondition |
| Redirect | `test_a_redirect_inside_policy_is_followed_and_recorded`; `test_a_redirect_out_of_policy_is_refused_and_not_followed`; `test_a_redirect_to_another_host_is_refused`; `test_a_redirect_out_of_the_approved_path_range_is_refused` (the F4 dot-segment repair) |
| Address range | `test_a_blocked_range_is_refused`, `test_a_public_address_passes`, `test_every_address_must_pass_not_merely_the_first`, `test_something_that_is_not_an_address_is_refused_rather_than_raising` |
| Response bound | `test_an_oversized_response_is_refused_by_rule`, `test_a_body_inside_the_limit_is_not_refused`, `test_a_drip_ends_at_the_request_budget_rather_than_at_the_body_limit`, `test_the_budget_does_not_scale_with_the_body_limit` (the F5 deadline repair) |
| Loopback | `test_with_the_flag_off_a_loopback_address_is_actually_refused`; `test_no_source_or_add_on_in_the_repository_sets_it`; `test_api.py::test_sec_002_*`; `test_config.py::test_sec_002_*` |
| **DNS** | `[측정]` **NOT EXERCISED as a failure.** Address *ranges* are checked and tested; DNS itself is not. There is no test for a name that fails to resolve, resolves to several addresses of differing legitimacy, or resolves differently between the check and the connect. The transport resolves once and connects to an address it checked, which closes the rebinding window by construction — but no test demonstrates it. |

---

## What B4 does not establish

`[추론]` Three things, stated here so a synthesis cannot imply them:

1. **No real source ever failed.** Rows 2 and 10 are exercised against stubs. `SRC-001` never
   throttled, timed out, redirected, drifted, or returned `5xx`.
2. **No real dataset exists.** Row 3 runs against rows this project wrote
   ([SRC-002](../../source-probes/SRC-002-local-jsonl.md)).
3. **The `200`-with-an-error-body case has no real subject.** `accept_status` was built for
   it after a measured incident, and `SRC-001` is not a source that does it.

`[결정]` `SEC-006` is **waived, not satisfied**
([DP-023](../../../docs/decisions/DP-023-sec-006-waived-for-p0.md)). Row 10's outbound
evidence is entirely application-layer; the sandbox second line of defence does not exist.

## Where a P0-A premise was tested and held

`[측정]` B4 says a P0-B failure that invalidates a P0-A premise sets the P0-A gate to
`REOPENED`. **No such failure occurred.** The fence, the lease, the effect key, the
correlation rule, and the error classification all held under a real add-on, real data, and
a real credential. The three defects found in `platform_core` during P0-B — the runner's
classification boundary (F2), the registry seam (F3), and `job.claim_conflict` (B6) — were
defects in the implementation of premises that themselves held.
