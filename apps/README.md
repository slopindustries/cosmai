# apps/

This is the P1 reconstruction tree. It is a separate `uv` project (`cd apps && uv run ...`),
with its own `.venv`, and it does not import from `experiments/` (P0) — P0 code may be read,
copied, and adapted, but `experiments` must never appear as an import path here;
`tests/environment/test_addon_layer_direction.py`-style guards exist to keep P0 and P1
mechanically separated even though this direction is enforced by convention rather than a
dedicated test in this tree yet.

The gate that authorized starting this tree is recorded in
[`../docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md`](../docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md);
the rebuild plan this tree follows is
[`../docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md`](../docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md).
