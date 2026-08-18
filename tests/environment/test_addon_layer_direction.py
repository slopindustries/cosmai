"""Guard: the add-on layer's dependencies point one way.

DP-008 D1 is the claim that makes "loosely coupled" mean something:

    addon_host  -> platform_core, domain, addon_api
    addon_kit   -> addon_api
    addons/*    -> addon_api, and nothing else local
    domain      -> platform_core
    addon_api   -> nothing local
    platform_core -> nothing in the add-on layer

A claim like that decays the first time someone reaches for a helper that is
almost in the right place. This turns it into a failing test.

Two rules carry most of the weight.

``addon_api`` importing nothing local is what lets an add-on depend on the
contract without depending on the platform. If the contract could import
``platform_core``, every add-on would too, transitively, and the direction would
be decorative.

**Nothing imports ``addons`` by name.** D2 loads add-ons by path through
``importlib``, so a static import of one would mean the platform knows an add-on
exists — the exact coupling the layer removes. This is the rule most likely to be
broken by accident, because importing a module you can see is the obvious thing
to do.

``domain`` is not permitted to import ``addon_api``, which is the one rule here
that is a judgement rather than a necessity. Raw persistence should not change
when the add-on contract version changes, so ``addon_host`` translates at the
boundary instead. If B0.2 finds that translation is pure ceremony, that is
evidence about the contract and belongs in the record — not a reason to widen
this quietly.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = REPO_ROOT / "experiments" / "integrated-p0"

#: Every package the direction rules talk about. A name outside this set is a
#: third-party or standard-library import and is not this guard's business.
LOCAL_PACKAGES = frozenset(
    {"platform_core", "domain", "addon_host", "addon_api", "addon_kit", "addons"}
)

#: What each package may import from :data:`LOCAL_PACKAGES`, besides itself.
ALLOWED_IMPORTS: dict[str, frozenset[str]] = {
    "addon_api": frozenset(),
    "platform_core": frozenset(),
    "domain": frozenset({"platform_core"}),
    "addon_host": frozenset({"platform_core", "domain", "addon_api"}),
    "addon_kit": frozenset({"addon_api"}),
    "addons": frozenset({"addon_api"}),
}

#: Loaded by path, never imported by name (DP-008 D2). No package may name it.
NEVER_IMPORTED = "addons"

SKIPPED_DIRECTORY_NAMES = frozenset({"node_modules", "__pycache__", "evidence", ".venv"})

Violation = tuple[Path, int, str, str]
"""(path, line, imported package, reason)."""


def imported_local_packages(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield the top-level local package of every absolute import, with its line.

    Relative imports are skipped: ``from .thing import x`` cannot leave its own
    package, so it can never cross a boundary this guard cares about.
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


def owning_package(path: Path) -> str | None:
    """Which rule set applies to this file, or ``None`` if it has none."""
    try:
        relative = path.relative_to(EXPERIMENT_ROOT)
    except ValueError:
        return None
    head = relative.parts[0]
    return head if head in ALLOWED_IMPORTS else None


def python_files() -> Iterator[Path]:
    if not EXPERIMENT_ROOT.is_dir():
        return
    stack = [EXPERIMENT_ROOT]
    while stack:
        for entry in sorted(stack.pop().iterdir()):
            if entry.is_dir():
                if entry.name not in SKIPPED_DIRECTORY_NAMES:
                    stack.append(entry)
            elif entry.suffix == ".py":
                yield entry


def collect_violations() -> list[Violation]:
    violations: list[Violation] = []
    for path in python_files():
        package = owning_package(path)
        if package is None:
            continue
        allowed = ALLOWED_IMPORTS[package] | {package}
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as error:
            pytest.fail(f"{path.relative_to(REPO_ROOT)}: cannot parse: {error}")
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


def format_violations(violations: list[Violation]) -> str:
    lines = ["The add-on layer's dependency direction is fixed by DP-008 D1.", ""]
    for path, line, imported, reason in violations:
        lines.append(f"  {path.relative_to(REPO_ROOT)}:{line}: imports {imported!r} — {reason}")
    return "\n".join(lines)


def test_the_add_on_layer_points_one_way() -> None:
    violations = collect_violations()
    assert not violations, format_violations(violations)


def test_the_guard_reads_the_packages_it_claims_to_read() -> None:
    """A guard over an empty file set passes and proves nothing.

    ``addon_api`` is the package whose emptiness would be least visible — it is
    supposed to import nothing local, so a rule that never ran would look
    identical to a rule that passed.
    """
    reviewed = {owning_package(path) for path in python_files()} - {None}
    assert "addon_api" in reviewed, "addon_api was not scanned"
    assert "platform_core" in reviewed, "platform_core was not scanned"


def test_a_violating_import_is_actually_caught() -> None:
    """The positive control. An absence assertion without one is vacuous."""
    module = ast.parse("from platform_core.jobs import registry\nimport addon_api\n")
    found = {name for name, _ in imported_local_packages(module)}
    assert found == {"platform_core", "addon_api"}

    # ...and the rule that uses it rejects the first for an add-on.
    allowed = ALLOWED_IMPORTS["addons"] | {"addons"}
    assert "platform_core" not in allowed
    assert "addon_api" in allowed


def test_relative_and_third_party_imports_are_not_reviewed() -> None:
    module = ast.parse(
        "from . import sibling\nfrom .deep.part import thing\nimport json\nimport pytest\n"
    )
    assert list(imported_local_packages(module)) == []


def test_no_package_may_import_add_ons_by_name() -> None:
    """D2's rule, checked as a rule rather than only as a scan result."""
    for package, allowed in ALLOWED_IMPORTS.items():
        if package == NEVER_IMPORTED:
            continue
        assert NEVER_IMPORTED not in allowed, package
