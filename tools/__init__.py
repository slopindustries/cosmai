"""Repository tooling that outlives P0.

A real package rather than an implicit namespace one, deliberately. `tests/` is a namespace
package at the repository root *and* a real package under `experiments/integrated-p0/`, and
the real one wins — which is why `tests.structural_fixture` was unimportable and this module
moved here. An `__init__.py` makes `tools.*` mean one thing to the interpreter, to mypy, and
to a reader.

Nothing here may be imported by `experiments/integrated-p0/`: DP-005 keeps P0 disposable and
P0 code must not become a dependency of P1, so the dependency has to point this way and not
back.
"""
