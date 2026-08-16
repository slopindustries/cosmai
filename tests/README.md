# Tests

Three roles live under this directory. They are not interchangeable.

## `acceptance/`

Promotable scenario documents written from [SCENARIO-TEMPLATE.md](acceptance/SCENARIO-TEMPLATE.md) using the `ACQ`, `RAW`, `JOB`, `SNP`, `NRM`, `OPS`, and `SEC` families. They describe behavior before it binds to a particular P0 implementation and are eligible for promotion to P1. They remain documents until P0 provides something to execute them against.

## `fixtures/`

Inputs classified by [Data Handling](../docs/conventions/data-handling.md). `public/` is committed; `local/` keeps only metadata, content hashes, and retrieval procedures in Git.

## `environment/`

Executable tests for repository infrastructure — the development environment, launchers, and guards. These verify the repository itself rather than P0 behavior, so they are not promotion candidates.

## Running

```sh
uv run pytest
```

Two marker families are skipped by default so that a default run never requires a credential or a network.

| Marker | Enable with |
|---|---|
| `requires_credential` | `uv run pytest --run-credential` |
| `network` | `uv run pytest --run-network` |

[`conftest.py`](conftest.py) also refuses to start a session when `COSMA_SECRET_SOURCE` points inside the working tree. That is the test-session half of the guard described in [Secret Setup](../docs/conventions/secret-setup.md); the application-startup half waits for P0 application code.
