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

Tests that start more than one worker process against a single database carry the `concurrency` marker. They are isolation-sensitive by design — they are the evidence for the charter's parallel-claim criterion — and must not be given a private database.

Every other test gets its own database, cloned from a template that has the migrations already applied.
