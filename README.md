# CosmaSignal

CosmaSignal is an evidence-bearing data ingestion and normalization experiment for beauty R&D signal intelligence.

## Current phase

The repository is currently in **P0-A — Platform Core Construction and Verification**. The next gate is the **P0-A Completion Gate**.

P0 is not the long-lived product foundation. P0-A builds only source- and normalization-independent platform behavior. P0-B then owns source exploration and selection, acquisition and normalization contracts and implementations, real-data verification, Architecture Synthesis, and artifact disposition. Only accepted evidence, contracts, fixtures, tests, and decisions may be promoted into the cleanly reconstructed P1 prototype.

## Current-stage goal

P0-A must prove only that the source-neutral platform can:

1. run handler-neutral jobs with claims, leases, retries, terminal states, interruption, and recovery;
2. expose platform health, generic job state, logs, metrics, failure inspection, and safe retry through a minimal dashboard;
3. preserve correlation, redaction, loopback binding, and repository-external secret-store guards;
4. produce replayable `JOB`, platform `OPS`, and platform `SEC` evidence without selecting or imitating a source or normalizer.

P0-B later owns real REST and dataset inputs, Raw and snapshot behavior, deterministic normalization, real-data verification, Architecture Synthesis, and `PoC Contract 0.1`.

The final product meaning of “trend” and the final `Normalized Schema 1.0` remain open questions.

## Repository map

```text
docs/            Project state, open questions, decisions, and synthesis
contracts/       Experimental and later accepted versioned contracts
experiments/     Disposable source probes and integrated P0 code
tests/           Promotable fixtures and scenarios, plus environment tests
config/          Committed configuration templates; never real secret values
scripts/         Local developer helpers
```

Credentials are never stored in this repository. See [Secret Setup](docs/conventions/secret-setup.md).

Start with [Project State](docs/project-state.md) and [P0 Charter](docs/p0-charter.md).
Before P0 work, read the [P0 Execution Plan](docs/p0-execution-plan.md).
Before using external data, read [Data Handling](docs/conventions/data-handling.md) and the [P0 Security Baseline](docs/conventions/p0-security.md).
The curated, non-authoritative project history is available in [Project History](docs/history/README.md).

## Development environment

Python and every Python package are managed by [uv](https://docs.astral.sh/uv/). The interpreter is pinned in `.python-version`.

```sh
uv sync
uv run pytest
```

The repository defines no importable package; experiments stay plain modules under `experiments/`. The reasoning is in [DP-003](docs/decisions/DP-003-development-environment.md).

### Optional: Nix shell

A flake provides `uv`, Node, PostgreSQL, and Git for anyone who would rather not install them:

```sh
nix develop
```

To enter the shell automatically, run `direnv allow` once. The committed `.envrc` does nothing until you do, and skips the shell entirely on a machine without Nix. Per-user tweaks belong in `.envrc.local`, which is ignored. [nix-direnv](https://github.com/nix-community/nix-direnv) is worth installing if you use this path — it caches the shell instead of re-evaluating it on every `cd`.

This path stays supplementary. No script, test, or document requires Nix, and uv resolves the same environment inside the shell as outside it.

## Lifecycle

```text
P0-A source-neutral platform implementation and verification
→ P0-A Completion Gate
→ P0-B source exploration and selection
→ Domain contracts and collector/importer/normalizer implementation
→ Real-data integration and failure evidence
→ Architecture Synthesis and artifact disposition inside P0-B
→ PoC Contract 0.1 and P1 reconstruction plan
→ P1 Entry Gate
→ Clean reconstruction P1
→ Observe, debug, and harden
```

## Status

No application exists yet. P0-A now builds the platform core without selecting or imitating a source, collector, dataset importer, Raw model, snapshot, or normalizer. All of that domain work begins in P0-B after the P0-A gate. `uv run pytest` exercises the repository's own environment tests.
