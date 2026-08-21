#!/usr/bin/env bash
#
# OQ-006's two carried measurements, rerun against the new (apps/) tree.
#
#   1. JOB-007 case B (200 jobs, four worker processes) — ten repetitions,
#      each a fresh `pytest` process, matching how the P0 baseline (0/30
#      normal, 1/3/1 under CPU contention) was measured.
#   2. The correlation-id test that produced P0's finding F16
#      (`test_job_002_shares_one_correlation_id_across_both_attempts`) — its
#      apps/ counterpart, `test_job_002_shares_one_correlation_id_and_counts_both_transitions`
#      in tests/acceptance/test_job_scenarios.py — twenty repetitions under
#      `pytest -n 4`.
#
# Every repetition is a separate `pytest` invocation (not a parametrize loop
# inside one process), so a passing repetition cannot be explained by state a
# previous repetition happened to leave warm. Raw pass/fail counts are printed
# at the end and are not smoothed, averaged, or otherwise summarized away —
# per task instructions, a reproduced failure is a result to record, not a
# reason to retry until green.
#
# Usage (run from apps/, with the shared server reachable):
#
#   COSMA_DB_HOST=127.0.0.1 COSMA_DB_PORT=5434 COSMA_DB_NAME=cosmai_test \
#     COSMA_DB_USER=cosmai_runtime ../scripts/with-secret-source.sh \
#     tests/concurrency/run_measurements.sh
#
# COSMA_DB_NAME=cosmai_test, not the production `cosmai` an earlier revision of this line
# named: tests/conftest.py's `platform_config` fixture forces `cosmai_test` regardless of what
# the environment names, so the wrong value was harmless but unchecked, not correct (REVIEW-M1
# F8, same correction made in docs/open-questions/OQ-006-job-concurrency.md's recipes).
#
# Every setting above is documented in docs/conventions/secret-setup.md and
# apps/db/provision.md; nothing here reads or prints a credential value.
#
# Sandbox note: this script is DB- and process-heavy (spawns four worker
# processes per JOB-007 repetition, and a `pytest -n 4` xdist session for the
# F16 rerun) — run it with the sandbox disabled, the same as any other
# DB-touching command in this milestone.

set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."  # apps/

JOB_007_REPETITIONS="${JOB_007_REPETITIONS:-10}"
F16_REPETITIONS="${F16_REPETITIONS:-20}"

F16_TEST_PATH="tests/acceptance/test_job_scenarios.py"
F16_TEST_NAME="test_job_002_shares_one_correlation_id_and_counts_both_transitions"

echo "=== OQ-006 carried measurements — $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "host: $(uname -a)"
echo

# --------------------------------------------------------------------------- #
# Measurement 1 — JOB-007 case B, 200 jobs x 4 workers, N repetitions
# --------------------------------------------------------------------------- #

echo "--- JOB-007 case B: ${JOB_007_REPETITIONS} repetitions ---"
job_007_failures=0
job_007_results=()
job_007_started=$(date +%s)
for i in $(seq 1 "$JOB_007_REPETITIONS"); do
  echo ">>> JOB-007 repetition $i/$JOB_007_REPETITIONS"
  if uv run python -m pytest tests/concurrency/test_job_007_parallel.py -q -s; then
    job_007_results+=("$i:PASS")
  else
    job_007_results+=("$i:FAIL")
    job_007_failures=$((job_007_failures + 1))
  fi
done
job_007_elapsed=$(( $(date +%s) - job_007_started ))

echo
echo "=== JOB-007 case B result ==="
echo "repetitions: ${JOB_007_REPETITIONS}"
echo "failures: ${job_007_failures}/${JOB_007_REPETITIONS}"
echo "per-repetition: ${job_007_results[*]}"
echo "wall-clock: ${job_007_elapsed}s"
echo

# --------------------------------------------------------------------------- #
# Measurement 2 — F16, the correlation-id test under -n 4, N repetitions
# --------------------------------------------------------------------------- #

echo "--- F16 rerun: ${F16_TEST_NAME} under -n 4, ${F16_REPETITIONS} repetitions ---"
f16_failures=0
f16_results=()
f16_started=$(date +%s)
for i in $(seq 1 "$F16_REPETITIONS"); do
  echo ">>> F16 repetition $i/$F16_REPETITIONS"
  if uv run python -m pytest "${F16_TEST_PATH}::${F16_TEST_NAME}" -n 4 -q; then
    f16_results+=("$i:PASS")
  else
    f16_results+=("$i:FAIL")
    f16_failures=$((f16_failures + 1))
  fi
done
f16_elapsed=$(( $(date +%s) - f16_started ))

echo
echo "=== F16 rerun result ==="
echo "repetitions: ${F16_REPETITIONS}"
echo "failures: ${f16_failures}/${F16_REPETITIONS}"
echo "per-repetition: ${f16_results[*]}"
echo "wall-clock: ${f16_elapsed}s"
echo

echo "=== summary (raw, unsmoothed) ==="
echo "JOB-007 case B: ${job_007_failures}/${JOB_007_REPETITIONS} failed"
echo "F16 (${F16_TEST_NAME}, -n 4): ${f16_failures}/${F16_REPETITIONS} failed"
