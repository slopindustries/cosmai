# Environment for the 2026-08-17 P0-A evidence capture

Follows the Environment section of `experiments/EXPERIMENT-TEMPLATE.md`. Every value
here is `[확인 사실]` unless labelled otherwise: each was read back from the tool or
the cluster that produced it, not copied from a document.

## Code revision

- Commit `60807cba3e65e094c5870e46499dffe4577bdfd7` (`60807cb`), branch `p0a/platform-core`. The directory name
  carries this short hash, and every artefact here was produced by this text.
- Working tree clean at capture, apart from the artefacts in this directory, which the
  scenarios rewrite when they run.

An earlier version of this file recorded a caveat that no longer applies: the
artefacts were first captured from a working tree ahead of its base commit, and the
directory was named for that base. Both are now resolved — the code is committed and
the directory is named for it. Three of the four artefacts are additionally written by
the tests that assert over them (`-k ops_003`, `-k sec_004`), so they cannot describe
behaviour the assertions did not check.

## Runtime and dependency versions

| Component | Version | How it was read |
|---|---|---|
| Python | 3.13.15 | `sys.version` inside the project environment |
| psycopg | 3.3.4 (libpq 180000) | `psycopg.__version__`, `psycopg.pq.version()` |
| FastAPI | 0.141.1 | `fastapi.__version__` |
| uvicorn | 0.52.3 | `uvicorn.__version__` |
| httpx | 0.28.1 | `httpx.__version__` |
| pytest | 9.1.1 | `pytest.__version__` |
| pytest-xdist | in the `dev` group of `pyproject.toml` | used as `-n 4` |
| uv | 0.12.3 (aarch64-apple-darwin) | `uv --version` |

## External service versions

- PostgreSQL **18.4** — `select version()` returned
  `PostgreSQL 18.4 on aarch64-apple-darwin25.6.0, compiled by clang version 21.1.8, 64-bit`.
- The cluster is the repository-local one `scripts/with-database.sh` manages under
  `var/postgres`. It has **no TCP listener**: `listen_addresses = ''`, reachable only
  through the Unix socket directory. See `sec-002-listeners.txt`.

## Host

- macOS 26.6.1 (build 25G76), `arm64`, `macOS-26.6.1-arm64-arm-64bit-Mach-O`.
- Single host. P0-A declares single-host execution, so nothing here was run across
  machines or against clock skew larger than a lease.

## Relevant configuration, secrets removed

Everything is read from `COSMA_`-prefixed environment variables. No credential
exists to resolve: the cluster is passwordless over a local socket, and P0-A
resolves no `credential_ref`.

| Setting | Value at capture | Source |
|---|---|---|
| `COSMA_DB_HOST` | `<repo>/var/postgres` (socket directory, not a hostname) | `scripts/with-database.sh` |
| `COSMA_DB_NAME` | `cosma_p0_evidence` for the capture; per-test clones under pytest | this capture / `tests/conftest.py` |
| `COSMA_DB_USER` | the invoking local account | `scripts/with-database.sh` |
| `COSMA_API_HOST` | unset, so the `127.0.0.1` default applies (`SEC-002`) | default |
| `COSMA_API_PORT` | an ephemeral free port per process | chosen by the capture |
| `COSMA_LOG_LEVEL` | unset, so `INFO` applies | default |
| `COSMA_LOG_FILE` | `platform.jsonl` in this directory | this capture |
| `COSMA_LEASE_SECONDS` | `1` for the interruption timeline; `30` default elsewhere | this capture |
| `COSMA_POLL_MS` | `20` for the capture; `200` default | this capture |
| `COSMA_SECRET_SOURCE` | not set. P0-A reads only its *location*, never its contents | `docs/conventions/secret-setup.md` |

`COSMA_LOG_FILE` is new in T5a and is the transport choice `OPS-003` leaves open: it
must end in `.jsonl`, because `.gitignore` excludes `*.log` and a log the evidence
directory silently dropped would be worse than none.

## Reproduction commands

The suite, which is what the `Result` sections of the four scenarios were measured
from:

```sh
./scripts/with-database.sh uv run pytest                     # whole suite, sequential
./scripts/with-database.sh uv run pytest -n 4                # the same, in parallel
./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_001
./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_002
./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_003
./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_004
uv run ruff check .
uv run mypy .
```

`[측정]` 2026-08-17: `472 passed in 48.37s` sequential and `472 passed in 18.51s`
under `-n 4`; `ruff` clean; `mypy` strict clean over 45 source files; the four
selectors returned 14, 11, 8 and 11 passed respectively.

The three data artefacts beside this file were produced by a throwaway collector
that drives the same code paths outside pytest, so that a log sample and a captured
response exist as files rather than only inside a test process. It is not committed —
it reduces no uncertainty and would be a second, undeclared copy of the scenario. To
regenerate equivalent artefacts, run `-k ops_003` and read the same values from the
assertions, or re-derive the timeline from `tests/test_ops.py::ops_003_run`, which is
the authority on what the sequence is.
