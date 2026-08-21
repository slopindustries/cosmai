"""Guard: nothing under ``apps/`` imports ``experiments`` by name.

``apps/README.md`` has said since the tree was opened that "`experiments` must
never appear as an import path here," and until now that was a convention with
no test behind it — REVIEW-M1 F7 named the gap: `grep -rn "apps" tests/environment/*.py`
returned zero, so the 81-test root guard would have stayed green if a P1
module had grown ``from experiments... import x``. AGENTS.md's own rule is
explicit that P0 code may be read, copied, and adapted, but never imported —
"P0 code must not become a runtime or package dependency of P1" — and a rule
with no control degrades the first time someone reaches for a P0 helper
instead of copy-adapting it, exactly the decay ``test_addon_layer_direction.py``'s
own docstring names for its own rule.

This is the mirror image of ``test_addon_layer_direction.py``: that guard
walks P0's tree and bounds what points *out* of ``platform_core`` toward the
add-on layer; this one walks P1's tree and bounds what points *back* into P0.
Import only, not vocabulary — ``test_p0a_boundary_guard.py`` already owns the
question of which words ``platform_core`` may contain, and repeating that
scan here against a tree DP-008 never restricted would be the wrong guard for
the wrong boundary.

Parsed with ``ast``, not matched with a substring search, so a docstring or
comment that says "copy-adapted from ``experiments/integrated-p0/...``" —
every file in ``apps/`` has one — is not itself a violation. Only an actual
``import`` or ``from ... import`` statement naming ``experiments`` as the
module counts; a relative import (``from . import experiments``, ``level``
> 0) cannot reach the repository-root ``experiments/`` directory at all and is
skipped, the same way ``test_addon_layer_direction.py`` skips its own.

**What this guard does not catch.** It reads ``import``/``from ... import`` statements only —
a dynamic reference built from a string (``importlib.import_module("experiments" + ...)``,
``__import__``) or a path dependency named in ``pyproject.toml``/``uv.lock`` rather than a Python
import statement would cross the same boundary invisibly to this guard. And it is not defensive
against a file it cannot parse: a syntax error under ``apps/`` makes ``ast.parse`` raise, which
this guard lets propagate as a test error rather than catching and reporting it as a violation —
a broken file fails the run, but not with this guard's own message.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APPS_ROOT = REPO_ROOT / "apps"

#: The one module name this guard forbids.
FORBIDDEN_MODULE = "experiments"

SKIPPED_DIRECTORY_NAMES = frozenset(
    {"node_modules", "__pycache__", ".venv", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)

Violation = tuple[Path, int, str]
"""(path, line, the import statement's own source text)."""


def python_files() -> Iterator[Path]:
    """Every ``.py`` file under ``apps/``, skipping generated directories."""
    if not APPS_ROOT.is_dir():
        return
    stack = [APPS_ROOT]
    while stack:
        for entry in sorted(stack.pop().iterdir()):
            if entry.is_dir():
                if entry.name not in SKIPPED_DIRECTORY_NAMES:
                    stack.append(entry)
            elif entry.suffix == ".py":
                yield entry


def imports_experiments(tree: ast.Module) -> Iterator[int]:
    """Yield the line number of every absolute import that names ``experiments``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == FORBIDDEN_MODULE:
                    yield node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                continue
            if node.module.split(".")[0] == FORBIDDEN_MODULE:
                yield node.lineno


def collect_violations() -> list[Violation]:
    violations: list[Violation] = []
    for path in python_files():
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        lines = text.splitlines()
        for line in imports_experiments(tree):
            source = lines[line - 1].strip() if 0 < line <= len(lines) else "<unavailable>"
            violations.append((path, line, source))
    return violations


def format_violations(violations: list[Violation]) -> str:
    lines = [
        "apps/ (P1) must never import experiments/ (P0) — AGENTS.md: \"P0 code "
        "must not become a runtime or package dependency of P1.\" Copy-adapt "
        "the logic instead of importing it.",
        "",
    ]
    for path, line, source in violations:
        lines.append(f"  {path.relative_to(REPO_ROOT)}:{line}: {source}")
    return "\n".join(lines)


def test_apps_never_imports_experiments() -> None:
    violations = collect_violations()
    assert not violations, format_violations(violations)
