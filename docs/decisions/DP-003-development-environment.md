# DP-003 — Development Environment and Python Packaging

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-16
- Owners: Project team
- Related Open Questions: OQ-001
- Closes part of: DP-002 remaining uncertainty, "Exact Python packaging and process entrypoints"

## Decision question

Where does the development environment live, and does any part of it become something P1 inherits?

## Decision

- `[결정]` A single root `pyproject.toml` defines the development environment. It declares no importable package (`[tool.uv] package = false`).
- `[결정]` `uv` is the supported dependency and environment manager. `uv.lock` is committed.
- `[결정]` Python is pinned to 3.13 through `.python-version`.
- `[결정]` `pytest` is the test runner. Executable repository-infrastructure tests live under `tests/environment/`.
- `[결정]` A Nix flake provides an optional development shell. It is supplementary: nothing in the repository requires it.
- `[결정]` The development environment is project infrastructure, not a P0 artifact. The P0 Charter's "not promoted by default" list does not apply to it.

## Rationale

The pre-P1 program requires validated local configuration before P0-A can produce executable platform evidence. That condition does not hold without a runnable toolchain.

Declaring no importable package is what keeps this compatible with DP-001. No module named after the product exists for P0 code to accumulate inside, so P1 cannot inherit one by accident. Experiments stay plain modules under `experiments/`, reachable through the pytest path configuration and nothing else.

Nix supplies system runtimes; uv owns every Python package. This is what prevents the two paths from drifting into different tool versions, and it is why `ruff`, `mypy`, and `pytest` are deliberately absent from the flake.

## Rejected alternatives

- **uv workspace with `experiments/*` as members.** Would allow per-experiment dependency sets under one lock file, but has zero members today. Speculative structure that reduces no named uncertainty. Reconsider when two experiments need conflicting dependencies.
- **A `pyproject.toml` per experiment.** Most faithful to disposability, but charges environment setup cost at the start of every experiment — friction neither P0-A nor P0-B needs.
- **Nix as the primary environment.** Would make the flake a prerequisite for contribution and couple the project to a toolchain no decision has selected.

## Tradeoffs and risks

- Benefits: one lock file, one entry command, no importable surface for P0 code to grow into.
- Costs: a root-level manifest can be misread as a P1 foundation. This packet exists to remove that reading.
- Failure modes: the flake drifting into a second, divergent environment. Mitigated by keeping Python packages out of it entirely, and verified by running the same test command through both paths.
- Reversibility: full. Removing the flake affects nobody who did not opt in; moving to a workspace later is an additive change to the same file.

## Remaining uncertainty

- Process entrypoints for API, worker, and dashboard. DP-002 listed packaging and entrypoints together; this packet closes packaging only.
- Whether experiments will need conflicting dependency sets.
- PostgreSQL and Node project files, deferred to P0 entry.
- CI environment, not yet defined.
