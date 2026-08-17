"""Guard: no domain-shaped identifier may appear inside ``experiments/integrated-p0``.

``docs/project-state.md`` ("P0-A boundary") and ``docs/p0-execution-plan.md`` (A2)
restrict P0-A to source- and normalization-independent platform behavior. A
boundary that lives only in prose is discovered after the code exists, so this
scans the experiment tree for the vocabulary that would mean the domain has been
started early: file and directory names, Python identifiers, and SQL object names.

Prose is deliberately not scanned. A comment or docstring that says "this is not a
collector" is exactly the kind of boundary statement the documents ask for, so the
guard parses ``.py`` files with ``ast`` and strips SQL comments before matching, and
compares whole snake_case / camelCase / kebab-case segments rather than substrings —
``resource`` must not read as ``source``, nor ``drawer`` as ``raw``.

It lives in ``tests/environment/`` because ``tests/README.md`` reserves that
directory for executable checks on the repository itself — the development
environment, its launchers, and its guards — none of which are promotion
candidates. It verifies no P0 behavior.

``normaliz*`` is the one entry that collides with ordinary programming English.
The prohibition targets the domain sense — `Normalized Schema 0.x`, the normalizer
provider protocol, a normalization run — and the guard cannot tell that apart from
"normalize this key to lowercase". Permitting the generic sense would let
``normalized_result`` through later, so the ban stays blunt and P0-A code uses a
different verb for the generic operation: ``casefold``, ``canonical``, or ``fold``.
The cost is one renamed helper; the alternative is a guard that stops guarding.

Known coverage limit: TypeScript and TSX identifiers are checked by path name
only, because parsing them would mean carrying a second language toolchain into
a Python test. The P0-A dashboard is three screens over a source-neutral API
(DP-006 D6), so the exposure is small and is recorded in the gate rather than
solved here.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_ROOT = REPO_ROOT / "experiments" / "integrated-p0"

# Vocabulary that belongs to P0-B. Matched as a whole identifier segment.
FORBIDDEN_SEGMENTS = frozenset(
    {
        "source",
        "collector",
        "importer",
        "raw",
        "observation",
        "ingest",
        "snapshot",
        "manifest",
        "provider",
        "lineage",
    }
)

# Matched as a segment prefix, to catch normalize/normalized/normalizer/normalization.
FORBIDDEN_SEGMENT_PREFIXES = ("normaliz",)

# The secret-store location guard is explicitly P0-A scope in
# docs/conventions/secret-setup.md ("Stage boundary"), and it can only be written
# against the name the launcher already exports. Exact identifier matches only.
ALLOWED_IDENTIFIERS = frozenset({"COSMA_SECRET_SOURCE", "secret_source"})

SKIPPED_DIRECTORY_NAMES = frozenset({"node_modules", "__pycache__", "evidence"})

_SEGMENT_BOUNDARY = re.compile(r"[_\-\s]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SQL_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_SQL_LINE_COMMENT = re.compile(r"--[^\n]*")
_SQL_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*")

# DP-006 D5 puts hand-written SQL in Python string literals, so a domain-shaped
# table name could reach the database without ever appearing as a Python
# identifier or in a .sql file. String constants are therefore scanned too — but
# only those that read as SQL, so that an error message explaining the boundary
# ("this handler is not a collector") is still ordinary prose the guard ignores.
_LOOKS_LIKE_SQL = re.compile(
    r"\b(select|insert\s+into|update|delete\s+from|create\s+table|alter\s+table|"
    r"drop\s+table|from|join)\b",
    re.IGNORECASE,
)

Finding = tuple[Path, int, str, str]
"""(path, line number, offending identifier, violated segment)."""


def segments_of(identifier: str) -> list[str]:
    """Split an identifier into lowercase snake_case / camelCase / kebab-case parts."""
    return [part.lower() for part in _SEGMENT_BOUNDARY.split(identifier) if part]


def violated_segment(identifier: str) -> str | None:
    """Return the first forbidden segment in ``identifier``, or ``None``."""
    if identifier in ALLOWED_IDENTIFIERS:
        return None
    for segment in segments_of(identifier):
        if segment in FORBIDDEN_SEGMENTS:
            return segment
        for prefix in FORBIDDEN_SEGMENT_PREFIXES:
            if segment.startswith(prefix):
                return f"{prefix}*"
    return None


def walk_experiment_tree() -> Iterator[Path]:
    """Yield every file under the experiment root, skipping generated directories."""
    if not EXPERIMENT_ROOT.is_dir():
        return
    stack = [EXPERIMENT_ROOT]
    while stack:
        for entry in sorted(stack.pop().iterdir()):
            if entry.is_dir():
                if entry.name not in SKIPPED_DIRECTORY_NAMES:
                    stack.append(entry)
            else:
                yield entry


def python_identifiers(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield every declared, bound, referenced, or imported name with its line."""
    for node in ast.walk(tree):
        match node:
            case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
                yield node.name, node.lineno
            case ast.Name():
                yield node.id, node.lineno
            case ast.Attribute():
                yield node.attr, node.lineno
            case ast.arg():
                yield node.arg, node.lineno
            case ast.keyword() if node.arg is not None:
                yield node.arg, node.lineno
            case ast.alias():
                yield node.name, node.lineno
                if node.asname is not None:
                    yield node.asname, node.lineno
            case ast.ImportFrom() if node.module is not None:
                yield node.module, node.lineno
            case ast.Global() | ast.Nonlocal():
                for name in node.names:
                    yield name, node.lineno
            case ast.ExceptHandler() if node.name is not None:
                yield node.name, node.lineno
            case _:
                continue


def embedded_sql(tree: ast.Module) -> Iterator[tuple[str, int]]:
    """Yield string constants that read as SQL, with their line."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _LOOKS_LIKE_SQL.search(node.value)
        ):
            yield node.value, node.lineno


def scan_python(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as error:
        pytest.fail(f"{path.relative_to(REPO_ROOT)}: cannot parse for boundary review: {error}")
    findings: list[Finding] = []
    for identifier, line in python_identifiers(tree):
        # A dotted module path is several identifiers; review each part.
        for part in identifier.split("."):
            segment = violated_segment(part)
            if segment is not None:
                findings.append((path, line, part, segment))
    for statement, line in embedded_sql(tree):
        for match in _SQL_IDENTIFIER.finditer(statement):
            segment = violated_segment(match.group())
            if segment is not None:
                findings.append((path, line, match.group(), segment))
    return findings


def scan_sql(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    # Blank the comments rather than delete them so line numbers stay accurate.
    stripped = _SQL_BLOCK_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)
    stripped = _SQL_LINE_COMMENT.sub("", stripped)
    findings: list[Finding] = []
    for line_number, line in enumerate(stripped.splitlines(), start=1):
        for match in _SQL_IDENTIFIER.finditer(line):
            segment = violated_segment(match.group())
            if segment is not None:
                findings.append((path, line_number, match.group(), segment))
    return findings


def scan_path_name(path: Path) -> list[Finding]:
    relative = path.relative_to(EXPERIMENT_ROOT)
    findings: list[Finding] = []
    for part in relative.parts:
        # Compare the stem so `raw.py` is caught but `run.raw`-free suffixes are not
        # split apart into meaningless fragments.
        for candidate in (part, Path(part).stem):
            segment = violated_segment(candidate)
            if segment is not None:
                findings.append((path, 0, part, segment))
                break
    return findings


def format_findings(findings: list[Finding]) -> str:
    lines = [
        "P0-A must not create domain-shaped identifiers; "
        "see docs/project-state.md 'P0-A boundary'.",
        "",
    ]
    for path, line, identifier, segment in findings:
        location = path.relative_to(REPO_ROOT)
        where = f"{location}:{line}" if line else f"{location} (path name)"
        lines.append(f"  {where}: {identifier!r} contains forbidden segment {segment!r}")
    return "\n".join(lines)


def collect_violations() -> list[Finding]:
    findings: list[Finding] = []
    for path in walk_experiment_tree():
        findings.extend(scan_path_name(path))
        if path.suffix == ".py":
            findings.extend(scan_python(path))
        elif path.suffix == ".sql":
            findings.extend(scan_sql(path))
    return findings


def test_no_domain_identifiers_in_the_integrated_experiment() -> None:
    findings = collect_violations()
    assert not findings, format_findings(findings)


def test_matching_is_segment_exact_not_substring() -> None:
    """Words that merely contain a forbidden substring must survive."""
    for benign in ("resource", "resourceLimit", "drawer", "job-drawer", "digest", "normal_state"):
        assert violated_segment(benign) is None, benign


def test_matching_catches_each_forbidden_form() -> None:
    assert violated_segment("source_id") == "source"
    assert violated_segment("rawPayload") == "raw"
    assert violated_segment("snapshot-manifest") == "snapshot"
    assert violated_segment("normalizeRow") == "normaliz*"
    assert violated_segment("HTTPProviderBase") == "provider"


def test_sql_embedded_in_python_is_reviewed_but_prose_is_not() -> None:
    """DP-006 D5 keeps SQL in string literals, so those strings must be scanned."""
    module = ast.parse(
        'QUERY = "SELECT id FROM observation WHERE 1"\n'
        'NOTE = "this handler is not a collector and holds no raw payload"\n'
    )
    found = [text for text, _ in embedded_sql(module)]
    assert len(found) == 1, found
    assert "observation" in found[0]


def test_secret_store_names_stay_available_to_the_p0a_guard() -> None:
    """docs/conventions/secret-setup.md places this guard inside P0-A scope."""
    assert violated_segment("COSMA_SECRET_SOURCE") is None
    assert violated_segment("secret_source") is None
    # The allowance is exact, not a licence for the segment generally.
    assert violated_segment("secret_source_path") == "source"
