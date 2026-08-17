# Environment for the 2026-08-17 P0-A evidence capture

Follows the Environment section of `experiments/EXPERIMENT-TEMPLATE.md`. Every value
here is `[확인 사실]` unless labelled otherwise: each was read back from the tool or
the cluster that produced it, not copied from a document.

## Code revision

- Commit `f83fe3c9f9a0cf13de1d2d34995a1d45654cf00c` (`f83fe3c`), branch `p0a/platform-core`. The directory name carries this
  short hash.
- **What the name claims, and how a reviewer checks it.** These artifacts were captured
  by the code at this commit, and the commit that adds them changes no code — so the
  claim is verifiable rather than asserted:

  ```sh
  git diff 07b0688..HEAD -- experiments/integrated-p0/platform_core \
                          experiments/integrated-p0/tests \
                          experiments/integrated-p0/dashboard/src   # must be empty
  ```

  Two earlier attempts got this wrong — first naming the base revision the work started
  from, then naming a commit whose tree could not have produced the artifacts at all.
  Both were caught by review rather than by me. The rule that removes the class of error
  is the one above: fix the revision, then commit artifacts without touching code.
- Capture is **opt-in** (`--capture-evidence=DIR`). An ordinary run rewrites nothing in
  this directory, which is what makes the hashes below verifiable at all.

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

`[측정]` 2026-08-17, at this revision: `520 passed, 2 skipped in 54.3s` sequential. The
two skips are the evidence-capture tests, which run only under `--capture-evidence=DIR`;
with capture requested the suite is 522. `ruff check .` clean; `mypy .` strict clean over
46 source files; `pytest tests/environment` 21 passed.

`[측정]` Per-scenario selectors at this revision: `ops_001` 14, `ops_002` 11, `ops_003` 8,
`ops_004` 11, `sec_001` 25, `sec_002` 25, `sec_003` 44, `sec_004` 72. Each matches the
count in that scenario's own `Result` section.

Two statements that used to stand here are gone because the conditions they described
are gone. This file recorded `472 passed` and 45 source files, measured during S3 and
never re-measured, so a reviewer following the gate's pointer found a number
contradicting the gate's. It also described the three data artifacts as products of an
uncommitted throwaway collector, which would have made them unreproducible. They are now
written by the scenarios that assert over them, under the opt-in flag above, so their
producer is committed and runnable.
