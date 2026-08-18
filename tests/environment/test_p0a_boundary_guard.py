"""Guard: no domain-shaped identifier may appear inside ``platform_core``.

``docs/project-state.md`` ("P0-A boundary") and ``docs/p0-execution-plan.md`` (A2)
restrict P0-A to source- and normalization-independent platform behavior. A
boundary that lives only in prose is discovered after the code exists, so this
scans for the vocabulary that would mean the domain has leaked in: file and
directory names, Python identifiers, and SQL object names.

**Rescoped for P0-B on 2026-08-18.** Until the P0-A Completion Gate this scanned the
whole of ``experiments/integrated-p0``, because during P0-A no part of that tree was
allowed to hold domain vocabulary. P0-B is allowed to, so that claim is now about a
past revision (``f83fe3c``) rather than about the working tree, and a whole-tree scan
would fail on P0-B's first legitimate file.

What survives the rescope is the narrower claim, and it is the more useful one:
``platform_core`` **stays** source-neutral. DP-008 D1 promises exactly that — the
add-on layer depends on ``platform_core`` and never the reverse — so the guard keeps
proving a live invariant instead of being retired. The P0-A gate's evidence continues
to hold for the same reason.

``domain/``, ``addon_api/``, ``addon_host/``, ``addons/``, and the dashboard are
outside the scan root deliberately: domain vocabulary is what they are for. The
direction they must not cross is enforced by
``tests/environment/test_addon_layer_direction.py`` instead, which is a different
question — not *which words* appear, but *which package imports which*.

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
#: The rescope described in the module docstring. Narrowing this is a decision;
#: widening it back would fail on P0-B code that is allowed to be domain-shaped.
SCAN_ROOT = EXPERIMENT_ROOT / "platform_core"

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
# Each alternative is a statement opener that ordinary English does not produce.
# A bare `from` or `join` was the first attempt and it misfired immediately: any
# docstring containing "separates this case from ..." became a SQL statement, and
# every noun in the surrounding prose was then reviewed as an identifier.
_LOOKS_LIKE_SQL = re.compile(
    r"(?:^|\n)\s*(?:with\s+\w+\s+as|select\s|insert\s+into\s|update\s+\w+\s+set\s|"
    r"delete\s+from\s|create\s+(?:table|index|unique)\s|alter\s+table\s|drop\s+table\s|"
    r"truncate\s)",
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


def walk_scanned_tree() -> Iterator[Path]:
    """Yield every file under the scan root, skipping generated directories."""
    if not SCAN_ROOT.is_dir():
        return
    stack = [SCAN_ROOT]
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
    relative = path.relative_to(SCAN_ROOT)
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
        "platform_core must stay source-neutral; see docs/project-state.md "
        "'P0-A boundary' and DP-008 D1. Domain vocabulary belongs in domain/, "
        "addon_api/, addon_host/, or addons/, which this guard does not scan.",
        "",
    ]
    for path, line, identifier, segment in findings:
        location = path.relative_to(REPO_ROOT)
        where = f"{location}:{line}" if line else f"{location} (path name)"
        lines.append(f"  {where}: {identifier!r} contains forbidden segment {segment!r}")
    return "\n".join(lines)


def collect_violations() -> list[Finding]:
    findings: list[Finding] = []
    for path in walk_scanned_tree():
        findings.extend(scan_path_name(path))
        if path.suffix == ".py":
            findings.extend(scan_python(path))
        elif path.suffix == ".sql":
            findings.extend(scan_sql(path))
    return findings


def test_no_domain_identifiers_in_platform_core() -> None:
    findings = collect_violations()
    assert not findings, format_findings(findings)


def test_the_scan_root_is_platform_core_and_actually_contains_files() -> None:
    """A guard pointed at a missing directory passes silently and proves nothing.

    ``walk_scanned_tree`` returns immediately when the root is absent, so the
    assertion above would hold vacuously if the rescope had named the directory
    wrongly. This is the positive control for the rescope itself.
    """
    assert SCAN_ROOT.name == "platform_core"
    assert SCAN_ROOT.is_dir(), SCAN_ROOT
    scanned = list(walk_scanned_tree())
    assert any(path.suffix == ".py" for path in scanned), "no Python file was scanned"
    assert any(path.suffix == ".sql" for path in scanned), "no SQL file was scanned"


def test_the_addon_layer_is_deliberately_outside_the_scan_root() -> None:
    """DP-008's packages are allowed the vocabulary this guard forbids.

    Their boundary is a direction, not a word list, and
    ``test_addon_layer_direction.py`` is what enforces it. If a future change
    widens the scan root back to the experiment tree, this fails first and names
    the reason instead of producing a wall of legitimate findings.
    """
    scanned = {path.resolve() for path in walk_scanned_tree()}
    for domain_package in ("domain", "addon_api", "addon_host", "addons", "dashboard"):
        root = (EXPERIMENT_ROOT / domain_package).resolve()
        assert not any(root in path.parents for path in scanned), domain_package


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
        'QUERY = "\\nselect id from observation where 1"\n'
        'NOTE = "this handler is not a collector and holds no raw payload"\n'
    )
    found = [text for text, _ in embedded_sql(module)]
    assert len(found) == 1, found
    assert "observation" in found[0]


def test_prose_that_merely_contains_a_sql_word_is_not_scanned_as_sql() -> None:
    """A docstring is not a query, however many keywords English lends it.

    The first version of the detector matched a bare ``from`` and turned every
    docstring using the word into a statement whose every noun was then reviewed
    as an identifier. Prose is exactly what the guard promises not to read.
    """
    module = ast.parse(
        '''
def handler() -> None:
    """Apply the effect, then stop.

    This separates the case from the one before it, and the observation that
    follows is what distinguishes them: the effect was already there.
    """
'''
    )
    assert list(embedded_sql(module)) == []


def test_real_statements_are_still_recognised() -> None:
    for statement in (
        "\nselect id from job",
        "\n  insert into platform_effect (effect_key) values (%s)",
        "\nwith candidate as materialized (select 1)",
        "\nupdate job set state = 'FAILED'",
        "\ncreate unique index one_open on job_attempt (job_id)",
    ):
        module = ast.parse(f"Q = {statement!r}")
        assert list(embedded_sql(module)), statement


def test_secret_store_names_stay_available_to_the_p0a_guard() -> None:
    """docs/conventions/secret-setup.md places this guard inside P0-A scope."""
    assert violated_segment("COSMA_SECRET_SOURCE") is None
    assert violated_segment("secret_source") is None
    # The allowance is exact, not a licence for the segment generally.
    assert violated_segment("secret_source_path") == "source"
