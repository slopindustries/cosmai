# CosmaSignal

CosmaSignal is an evidence-bearing data ingestion and normalization experiment for beauty R&D signal intelligence.

## Current phase

The repository is currently in **M0 — Project Bootstrap**. The next gate is **M1 — Source Capability Exploration**. M1 selects and measures real REST API and dataset inputs before **M2** executes P0, the deliberately disposable integrated architecture prototype.

P0 is not the long-lived product foundation. Its code will be archived after Architecture Synthesis. Only accepted evidence, contracts, fixtures, tests, and decisions may be promoted into the cleanly reconstructed P1 prototype.

## Current-stage goal

Prove that CosmaSignal can:

1. ingest one real REST API source and one existing dataset as untrusted Raw data;
2. preserve source provenance and replayable inputs;
3. run collection and normalization as independently controlled jobs;
4. normalize a sealed snapshot with at least one deterministic rule-based provider;
5. expose job control, state, logs, metrics, and debugging evidence through a minimal dashboard;
6. produce enough evidence to synthesize `PoC Contract 0.1` before P1 is rebuilt.

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

This path is supplementary. No script, test, or document requires Nix, and uv resolves the same environment inside the shell as outside it. To enter it automatically with direnv, copy `.envrc.example` to `.envrc` and run `direnv allow`.

## Lifecycle

```text
Source and schema exploration
→ Disposable integrated prototype P0
→ Evidence and Architecture Synthesis
→ PoC Contract 0.1
→ Clean reconstruction P1
→ Observe, debug, and harden
```

## Status

No application exists yet. That is intentional: M0 establishes the decision boundary, the evidence protocol, and a working toolchain before source probes and P0 implementation begin. `uv run pytest` exercises the repository's own environment tests.
