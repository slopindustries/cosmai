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


# --------------------------------------------------------------------------- #
# The apps/ layer's own dependency direction — M3 batch 3c
#
# ``test_addon_layer_direction.py`` (``tests/environment/``) proves DP-008 D1
# inside P0's tree (``experiments/integrated-p0/``); nothing proved the same
# claim inside ``apps/`` until now, and P1's own copy of the add-on layer
# (``addon_api``, ``addon_host``, ``addon_kit``, and — once M4 installs one —
# ``apps/addons/``) is exactly where that claim would decay first, the same way
# the guard above exists because the *other* boundary decayed with no control
# behind it. Same ``ast`` approach as both existing guards: parsed, not
# substring-matched, so a docstring naming ``platform_core`` in prose is not a
# violation.
# --------------------------------------------------------------------------- #

#: Every local top-level package under ``apps/`` the layer-direction rules govern.
#: ``domain`` and ``platform_core`` are already covered by ``python_files()`` above;
#: this reuses that same walk rather than a second one.
LOCAL_PACKAGES = frozenset(
    {"platform_core", "domain", "addon_host", "addon_api", "addon_kit", "addons"}
)

#: What each package may import from :data:`LOCAL_PACKAGES`, besides itself.
#: Mirrors ``test_addon_layer_direction.py``'s table exactly — DP-008 D1 draws one
#: boundary and both trees implement it — with one difference this tree's own
#: history explains: P0's table permits ``domain`` no ``addon_api`` import "as a
#: judgement rather than a necessity" (that file's own docstring); nothing in
#: this batch revisits that judgement, so the table is copied unchanged rather
#: than re-derived.
ALLOWED_IMPORTS: dict[str, frozenset[str]] = {
    "addon_api": frozenset(),
    "platform_core": frozenset(),
    "domain": frozenset({"platform_core"}),
    "addon_host": frozenset({"platform_core", "domain", "addon_api"}),
    "addon_kit": frozenset({"addon_api"}),
    "addons": frozenset({"addon_api"}),
}

#: Loaded by path, never imported by name (DP-008 D2). No package may name it —
#: ``apps/addons/`` holds nothing yet (M4), but the rule is checked now so the
#: first add-on that lands there is already covered rather than grandfathered.
NEVER_IMPORTED = "addons"

LayerViolation = tuple[Path, int, str, str]
"""(path, line, imported package, reason)."""


def imported_local_packages(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield the top-level local package of every absolute import, with its line.

    Relative imports are skipped: ``from .thing import x`` cannot leave its own
    package, so it can never cross a boundary this guard cares about — the same
    reasoning ``imports_experiments`` above and ``test_addon_layer_direction.py``
    both give for skipping theirs.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                head = alias.name.split(".")[0]
                if head in LOCAL_PACKAGES:
                    yield head, node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module is None:
                continue
            head = node.module.split(".")[0]
            if head in LOCAL_PACKAGES:
                yield head, node.lineno


def owning_layer_package(path: Path) -> str | None:
    """Which rule set applies to this file, or ``None`` if it has none.

    Only a file directly under one of :data:`LOCAL_PACKAGES` at the ``apps/``
    root is covered — ``apps/tests/*.py`` (which legitimately imports all of
    them together to exercise cross-layer behavior) and ``apps/db/*.py`` own no
    entry in the table and are therefore not scanned, the same way
    ``test_addon_layer_direction.py`` does not scan P0's own ``tests/``.
    """
    try:
        relative = path.relative_to(APPS_ROOT)
    except ValueError:
        return None
    head = relative.parts[0]
    return head if head in ALLOWED_IMPORTS else None


def collect_layer_violations() -> list[LayerViolation]:
    violations: list[LayerViolation] = []
    for path in python_files():
        package = owning_layer_package(path)
        if package is None:
            continue
        allowed = ALLOWED_IMPORTS[package] | {package}
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for imported, line in imported_local_packages(tree):
            if imported == NEVER_IMPORTED and package != NEVER_IMPORTED:
                violations.append(
                    (path, line, imported, "add-ons are loaded by path, never imported by name")
                )
            elif imported not in allowed:
                permitted = ", ".join(sorted(allowed)) or "nothing local"
                violations.append(
                    (path, line, imported, f"{package} may import only {permitted}")
                )
    return violations


def format_layer_violations(violations: list[LayerViolation]) -> str:
    lines = ["The apps/ add-on layer's dependency direction is fixed by DP-008 D1.", ""]
    for path, line, imported, reason in violations:
        lines.append(f"  {path.relative_to(REPO_ROOT)}:{line}: imports {imported!r} — {reason}")
    return "\n".join(lines)


def test_the_apps_layer_points_one_way() -> None:
    violations = collect_layer_violations()
    assert not violations, format_layer_violations(violations)


def test_the_layer_guard_reads_the_packages_it_claims_to_read() -> None:
    """An absence assertion over a guard that never ran is vacuous — the same
    control ``test_addon_layer_direction.py`` runs for its own P0-side scan."""
    reviewed = {owning_layer_package(path) for path in python_files()} - {None}
    assert "addon_api" in reviewed, "apps/addon_api was not scanned"
    assert "platform_core" in reviewed, "apps/platform_core was not scanned"
    assert "addon_host" in reviewed, "apps/addon_host was not scanned"


def test_a_violating_import_is_actually_caught() -> None:
    """The positive control. An absence assertion without one is vacuous."""
    module = ast.parse("from platform_core.jobs import registry\nimport addon_api\n")
    found = {name for name, _ in imported_local_packages(module)}
    assert found == {"platform_core", "addon_api"}

    # ...and the rule that uses it rejects the first for an add-on.
    allowed = ALLOWED_IMPORTS["addons"] | {"addons"}
    assert "platform_core" not in allowed
    assert "addon_api" in allowed


def test_no_package_may_import_add_ons_by_name() -> None:
    """D2's rule, checked as a rule rather than only as a scan result."""
    for package, allowed in ALLOWED_IMPORTS.items():
        if package == NEVER_IMPORTED:
            continue
        assert NEVER_IMPORTED not in allowed, package


def test_platform_core_never_imports_domain_or_the_add_on_layer() -> None:
    """DP-008 D1's sharpest edge, named as its own assertion rather than left to be
    inferred from the table: ``platform_core`` predates the add-on layer entirely
    (M1) and must gain no dependency on it, ever, in either direction from the
    add-on side's own ``domain``/``addon_*`` imports."""
    assert ALLOWED_IMPORTS["platform_core"] == frozenset()
