# Integrated P0 tests

Executable tests for the disposable platform core. They live here rather than in the repository's `tests/` tree because they are P0 code, and [DP-001](../../../docs/decisions/DP-001-p0-lifecycle.md) keeps P0 code under `experiments/integrated-p0/`. [DP-006](../../../docs/decisions/DP-006-p0a-platform-foundation.md) D1 records the placement.

The distinction matters at the P0-B artifact disposition step. Everything here is `ARCHIVE_REFERENCE_ONLY` by default. The promotable material is elsewhere:

| Location | Role | Promotion |
|---|---|---|
| `tests/acceptance/` | Scenario documents describing behavior before it binds to an implementation | Eligible |
| `tests/environment/` | Checks on the repository itself — the environment, its launchers, its guards | Not a candidate |
| here | Executable checks on this disposable implementation | Not a candidate |

A test here executes an acceptance scenario; it does not replace one. When a scenario's `Verification` section names a command, that command runs a test in this directory, and the scenario's `Result` section records what the run observed.

## Running

```sh
./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests
```

### The two opt-in flags need the `tests` path, and nothing said so

`[확인 사실]` This section was added by the orchestrator on 2026-08-20, outside any active
task packet's allowed files — recorded here per
[`ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md`](../ADVERSARIAL-REVIEW-2026-08-20-OBF-REAL-DATA.md)
F8, so the file does not carry anonymous provenance.

`[측정]` Recorded 2026-08-20, after it cost two workers time. `--run-network` and
`--run-credential` are defined by `tests/conftest.py`'s `pytest_addoption`, and pytest loads
a directory's conftest only when it was given a path under that directory. So a command
naming a real-data test **here** and nothing else is rejected before it runs:

```sh
# Fails: unrecognized arguments: --run-network
.venv/bin/python -m pytest experiments/integrated-p0/tests/test_obf_real_data.py --run-network

# Works: `tests` is what loads the conftest that defines the flag.
.venv/bin/python -m pytest tests experiments/integrated-p0/tests/test_obf_real_data.py --run-network
```

`[확인 사실]` This applies to every network or credential test in this directory —
`test_naver_real_data.py` and `test_obf_real_data.py` — and neither file's docstring nor any
committed command recorded it before this note. `[추론]` The failure is a flag-parsing error
rather than a skip, so it is loud rather than silent; it costs a reader a few minutes, not a
false pass. Recorded here because the fix is not discoverable from the error message.

Tests that start more than one worker process against a single database carry the `concurrency` marker. They are isolation-sensitive by design — they are the evidence for the charter's parallel-claim criterion — and must not be given a private database.

Every other test gets its own database, cloned from a template that has the migrations already applied.
