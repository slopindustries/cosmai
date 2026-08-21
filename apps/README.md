# apps/

This is the P1 reconstruction tree. It is a separate `uv` project (`cd apps && uv run ...`),
with its own `.venv`, and it does not import from `experiments/` (P0) — P0 code may be read,
copied, and adapted, but `experiments` must never appear as an import path here;
[`tests/environment/test_p1_isolation.py`](../tests/environment/test_p1_isolation.py) enforces
that mechanically (`ast`-parsed, so a docstring naming `experiments/...` in prose is not a
violation) — a real root-guard test, not only this paragraph.

The gate that authorized starting this tree is recorded in
[`../docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md`](../docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md);
the rebuild plan this tree follows is
[`../docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md`](../docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md).
