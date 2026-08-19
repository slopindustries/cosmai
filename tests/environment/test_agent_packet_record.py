"""Guard: an ACCEPTED task packet must carry the evidence that closed it.

``docs/agent-workflow/ORCHESTRATOR.md`` lists, among prohibited actions,
"accepting implementation solely because the worker reports success", and
``docs/agent-workflow/README.md`` says "Only the orchestrator closes a packet
after reading the worker evidence and attacker report." Both sentences are
prose until something can fail when they are violated. This is the checkable
half: a packet whose ``Status`` is ``ACCEPTED`` must show ``Attack report:``
as a resolvable link into this repository, and ``Result: PASS`` — the two
fields ``docs/agent-workflow/TASK-PACKET-TEMPLATE.md`` puts under ``## Review``
for exactly this purpose. Every packet, regardless of status, must at least name
a ``Status:`` the template recognises; an unrecognised status is a packet the
orchestrator flow has no rule for.

``docs/agent-workflow/reviews/REVIEW-TASK-001.md`` found two ways the checks
above did not mean what this docstring said. **F2:** "a repository path" was
tested as only "not a URL, not ``mailto:``, not a bare anchor", so an absolute
path (``/etc/hosts``), a ``..`` escape out of the tree, and a link to a
directory all passed. Fixed by resolving the target and requiring the
*resolved* path to be both inside ``REPO_ROOT`` and a file: ``Path.resolve()``
returns an absolute input unchanged and collapses every ``..`` segment, so
containment has to be checked after resolution — a string search for the
substring ``..`` cannot do it, because a legitimate link needs ``..`` too
(reports live in ``../reviews/`` and deeper). **F3:** every field lookup took
the first matching line anywhere in the document, with no regard for how many
there were or where, so an earlier decoy ``- Status:``, ``- Result:``, or
``- Attack report:`` line silently overrode the real one under ``## Review``.
Fixed by rejecting any field that has more than one matching line, wherever
they fall, instead of picking a first-match or last-match winner: a
last-match rule would close this exact bypass while opening the same one from
the other direction — a decoy appended *after* the real line — so refusing to
choose is the version that is not just as breakable from the opposite side.

``STATUS_VALUES`` below is a copy of the template's own vocabulary rather than
something parsed out of it at import time, so that a template formatting
change fails one named test (``test_status_values_match_the_template``)
instead of silently changing what every other test in this file accepts.

``docs/agent-workflow/reviews/README.md`` says an attack report lives in this
repository — beside the experiment it attacks, or under
``docs/agent-workflow/reviews/`` when there is none. A link is therefore
always possible for a real report, so ``Attack report:`` must contain a
markdown link whose target, once resolved against
``docs/agent-workflow/task-packets/`` (where ``task-packets/README.md`` says
every packet is created) and stripped of any ``#fragment``, names an existing
file inside this repository. A target that reads as a URL or a ``mailto:``
link is rejected without resolving it at all; a bare same-document ``#anchor``
is rejected the same way. Everything else is resolved and must then be
contained in the repository, existing, and a file — not a directory, and not
anything a ``..`` segment or an absolute target reaches outside the tree.

The real directory scan below proves nothing by itself: it can only fail when
some packet under ``docs/agent-workflow/task-packets/`` is both ``ACCEPTED``
and defective, and today that directory may hold no ``ACCEPTED`` packet at
all. What gives this guard teeth is ``packet_problems`` being exercised
directly against malformed packet bodies built inline, below. Two of those
inline cases resolve a link against ``TASK_PACKET_TEMPLATE`` rather than
inventing a new dependency: that file is already load-bearing for this module
(``test_status_values_match_the_template`` reads it too), so it going missing
breaks this file in an obvious, already-tested way instead of turning two
unrelated cases red for a reason that has nothing to do with the validator —
which is what happened, per REVIEW-TASK-001.md **F12**, when they depended on
``docs/agent-workflow/README.md`` instead.

``scan_task_packets`` — the function both the real scan and its own tests
below call — does not recurse into a subdirectory of the directory it is
given, and does not let one file it cannot decode abort the rest of the scan.
``task-packets/README.md`` describes one packet file per task, directly in
the directory; a subdirectory is not a place this guard knows how to look for
more packets, so it is reported as a defect in its own right rather than
silently skipped or silently walked into (REVIEW-TASK-001.md **F13**).

This does **not** check that a packet exists at all for a given piece of
work, that a report's content is any good, or that whoever wrote it was
independent of the worker. Those are conventions this repository has no way
to verify mechanically; they are only as good as the roles in
``docs/agent-workflow/`` reading each other's output honestly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_WORKFLOW_DIR = REPO_ROOT / "docs" / "agent-workflow"
TASK_PACKETS_DIR = AGENT_WORKFLOW_DIR / "task-packets"
TASK_PACKET_TEMPLATE = AGENT_WORKFLOW_DIR / "TASK-PACKET-TEMPLATE.md"

#: task-packets/README.md is the directory's index, not a packet to validate.
NON_PACKET_FILES = frozenset({"README.md"})

#: The vocabulary TASK-PACKET-TEMPLATE.md's own ``Status:`` line documents,
#: copied rather than parsed at import time; see the module docstring and
#: test_status_values_match_the_template, which is what catches the copy
#: going stale.
STATUS_VALUES = frozenset(
    {
        "DRAFT",
        "READY",
        "IN_PROGRESS",
        "WORKER_DONE",
        "REVIEWING",
        "ACCEPTED",
        "REWORK",
        "BLOCKED",
    }
)

#: The one status this guard holds to a bar higher than "is a recognised value".
ACCEPTED_STATUS = "ACCEPTED"

_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def _field_values(text: str, field: str) -> list[str]:
    r"""Return the trailing text of every ``- {field}: ...`` line, in document order.

    Returning every match rather than just the first is what lets
    ``packet_problems`` refuse to pick a winner among several instead of
    picking the wrong one — see the module docstring's account of F3.

    The gaps around the field name use ``[ \t]*`` rather than ``\s*`` on
    purpose: ``\s`` matches a newline, so an empty field (``- Attack report:``
    with nothing after it) would let the pattern run on and capture the
    *next* line's content as this field's value instead of an empty string.
    """
    pattern = re.compile(rf"^-[ \t]*{re.escape(field)}:[ \t]*(.*)$", re.MULTILINE)
    return [match.group(1).strip() for match in pattern.finditer(text)]


def _unquoted(value: str) -> str:
    """Strip one wrapping pair of backticks, the convention every Status/Result value uses.

    Anything else — unbalanced, or with trailing text after the closing
    backtick — is returned unchanged rather than partially cleaned, so it
    fails the exact-equality check downstream instead of risking a partial
    strip that happens to match. ``status-with-trailing-text-after-the-
    closing-backtick-is-rejected`` and its unbalanced-backtick sibling below
    are the proof that this does not quietly accept either shape.
    """
    if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
        return value[1:-1].strip()
    return value


def _linked_report_target(report: str) -> str | None:
    """Return a markdown link's target found in ``report``, or ``None`` if it has none."""
    match = _MARKDOWN_LINK.search(report)
    return None if match is None else match.group(1).strip()


def _report_target_problem(target: str) -> str | None:
    """Why ``target`` cannot stand as an ``Attack report:`` link, or ``None`` if it can.

    REVIEW-TASK-001.md F2: the previous check tested only that ``target`` was
    not a URL, a ``mailto:`` link, or a bare ``#anchor`` — so an absolute
    path, a ``..`` escape, and a link to a directory all passed as "a
    repository path". ``Path.resolve()`` returns an absolute input unchanged
    and collapses every ``..`` segment, so checking containment on the
    *resolved* path is what catches both kinds of escape; a string check for
    the substring ``..`` cannot, because a legitimate link needs it too.
    """
    if _URL_SCHEME.match(target) or target.startswith(("mailto:", "#")):
        return "which is not a repository path"
    path_part = target.split("#", 1)[0].strip()
    resolved = (TASK_PACKETS_DIR / path_part).resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        return "which is not a repository path"
    if resolved.is_dir():
        return f"but {resolved} is a directory, not a file"
    if not resolved.exists():
        return f"but {resolved} does not exist"
    return None


def packet_problems(text: str, name: str) -> list[str]:
    """Return every defect ``text`` has as a task packet; ``[]`` means it is clean.

    ``name`` labels the packet in the returned messages only. A link inside
    ``Attack report:`` is resolved against :data:`TASK_PACKETS_DIR`, not
    against ``name``, so the malformed-packet cases below can exercise this
    function without a corresponding file on disk.

    A field with more than one matching line is rejected outright, before its
    content is examined at all — see the module docstring's account of F3.
    """
    statuses = _field_values(text, "Status")
    if not statuses:
        return [f"{name}: no `Status:` line"]
    if len(statuses) > 1:
        return [f"{name}: {len(statuses)} `Status:` lines found; exactly one is required"]
    status = _unquoted(statuses[0])
    if status not in STATUS_VALUES:
        return [f"{name}: Status {status!r} is not one of {sorted(STATUS_VALUES)}"]
    if status != ACCEPTED_STATUS:
        return []

    problems: list[str] = []

    reports = _field_values(text, "Attack report")
    if len(reports) > 1:
        problems.append(
            f"{name}: {len(reports)} `Attack report:` lines found; exactly one is required"
        )
    elif not reports or not reports[0]:
        problems.append(f"{name}: Status is {ACCEPTED_STATUS} but Attack report: is empty")
    else:
        target = _linked_report_target(reports[0])
        if target is None:
            problems.append(
                f"{name}: Status is {ACCEPTED_STATUS} but Attack report: has no markdown link"
            )
        else:
            reason = _report_target_problem(target)
            if reason is not None:
                problems.append(f"{name}: Attack report links to {target!r}, {reason}")

    results = _field_values(text, "Result")
    if len(results) > 1:
        problems.append(
            f"{name}: {len(results)} `Result:` lines found; exactly one is required"
        )
    else:
        result = _unquoted(results[0]) if results else None
        if result != "PASS":
            problems.append(
                f"{name}: Status is {ACCEPTED_STATUS} but Result is {result!r}, not `PASS`"
            )

    return problems


def scan_task_packets(directory: Path) -> list[str]:
    """Scan ``directory`` the way :data:`TASK_PACKETS_DIR` is scanned for real.

    Does not recurse: ``task-packets/README.md`` describes one file per
    packet, directly in the directory, so a subdirectory is not a place to
    look for more packets — it is reported as a problem in its own right,
    the same way a file that is not valid UTF-8 is reported and skipped
    rather than left to raise and abort the scan before later packets are
    read (REVIEW-TASK-001.md F13).

    Parameterized on ``directory`` rather than closing over
    :data:`TASK_PACKETS_DIR` so the tests below can reproduce both failure
    modes against a throwaway ``tmp_path`` tree instead of the real one.
    """
    if not directory.is_dir():
        return []
    problems: list[str] = []
    for path in sorted(directory.iterdir()):
        if path.name in NON_PACKET_FILES:
            continue
        label = path.relative_to(directory)
        if not path.is_file():
            problems.append(f"{label}: task-packets holds one file per packet, not a directory")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            problems.append(f"{label}: not valid UTF-8 ({error})")
            continue
        problems.extend(packet_problems(text, str(label)))
    return problems


def test_every_accepted_task_packet_carries_its_closing_evidence() -> None:
    """The real scan over whatever packets currently exist.

    This passes vacuously whenever no packet under
    ``docs/agent-workflow/task-packets/`` is both ``ACCEPTED`` and defective
    — including, today, the case of no ``ACCEPTED`` packet existing at all.
    The parametrized tests below are what actually prove ``packet_problems``
    rejects a bad one.
    """
    problems = scan_task_packets(TASK_PACKETS_DIR)
    assert not problems, "\n".join(problems)


def test_the_task_packets_directory_exists_and_is_where_the_scan_looks() -> None:
    """A scan pointed at a renamed or deleted directory passes and proves nothing."""
    assert TASK_PACKETS_DIR == REPO_ROOT / "docs" / "agent-workflow" / "task-packets"
    assert TASK_PACKETS_DIR.is_dir(), TASK_PACKETS_DIR


def test_status_values_match_the_template() -> None:
    """STATUS_VALUES is a copy; this is what stops it silently going stale."""
    text = TASK_PACKET_TEMPLATE.read_text(encoding="utf-8")
    match = re.search(r"^-\s*Status:\s*`([^`]+)`", text, re.MULTILINE)
    assert match is not None, f"{TASK_PACKET_TEMPLATE}: no backticked Status: line found"
    documented = frozenset(part.strip() for part in match.group(1).split("|"))
    assert documented == STATUS_VALUES


def test_scanning_reports_a_non_utf8_file_and_keeps_going(tmp_path: Path) -> None:
    """F13's reproduction: a bad file must not abort the scan before later packets.

    ``path.read_text(encoding="utf-8")`` used to be unguarded, so one binary
    file raised ``UnicodeDecodeError`` and stopped the ``for`` loop — a
    defective packet that sorts after it was never read at all. ``TASK-999``
    is named to sort after ``TASK-000`` so this reproduces that ordering.
    """
    (tmp_path / "TASK-000-not-utf8.md").write_bytes(b"x \xff\xfe\n")
    (tmp_path / "TASK-999-defective.md").write_text(
        "- Status: `ACCEPTED`\n\n## Review\n\n- Attack report:\n- Result: `PASS`\n",
        encoding="utf-8",
    )
    problems = scan_task_packets(tmp_path)
    assert any("not valid UTF-8" in problem for problem in problems), problems
    assert any("Attack report" in problem for problem in problems), problems


def test_scanning_reports_a_subdirectory_instead_of_silently_skipping_it(
    tmp_path: Path,
) -> None:
    """F13: the previous scan filtered out non-files with no report at all.

    A packet filed in a subdirectory was invisible to the scan — neither
    read nor named as a problem. This makes the subdirectory itself the
    finding, rather than silently recursing into it or silently ignoring it.
    """
    (tmp_path / "nested").mkdir()
    problems = scan_task_packets(tmp_path)
    assert len(problems) == 1, problems
    assert "directory" in problems[0], problems


def test_scanning_still_excludes_the_directory_index(tmp_path: Path) -> None:
    """The README exclusion survives the F13 rewrite, not just the pre-rewrite version."""
    (tmp_path / "README.md").write_text("# Active Task Packets\n", encoding="utf-8")
    assert scan_task_packets(tmp_path) == []


REJECTED_CASES = [
    pytest.param(
        "# TASK-901 — Example without a status line\n\n## Objective\n\nDo the thing.\n",
        "Status",
        id="missing-status-line",
    ),
    pytest.param(
        "- Status: `SUBMITTED`\n",
        "SUBMITTED",
        id="status-outside-vocabulary",
    ),
    pytest.param(
        "- Status: `DRAFT | READY | IN_PROGRESS | WORKER_DONE | REVIEWING | ACCEPTED | "
        "REWORK | BLOCKED`\n",
        "Status",
        id="status-left-as-the-template-placeholder",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n- Attack report:\n- Result: `PASS`\n",
        "Attack report",
        id="accepted-with-empty-attack-report",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [operating model](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `FAIL`\n",
        "Result",
        id="accepted-with-failing-result",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [operating model](../TASK-PACKET-TEMPLATE.md)\n",
        "Result",
        id="accepted-with-no-result-line",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [missing review](../reviews/REVIEW-TASK-DOES-NOT-EXIST.md)\n"
        "- Result: `PASS`\n",
        "does not exist",
        id="accepted-report-links-to-a-missing-file",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: Reviewed manually against the acceptance criteria; "
        "no defects found.\n"
        "- Result: `PASS`\n",
        "no markdown link",
        id="accepted-report-is-plain-prose-with-no-link",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [external tracker](https://example.com/reviews/901)\n"
        "- Result: `PASS`\n",
        "not a repository path",
        id="accepted-report-links-to-a-url-is-rejected",
    ),
    # --- F2: containment, not just "not a URL/mailto/anchor" (REVIEW-TASK-001.md) ---
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [leaked](/etc/hosts)\n"
        "- Result: `PASS`\n",
        "not a repository path",
        id="accepted-report-links-to-an-absolute-path-outside-the-tree",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [leaked](../../../../../../../../../../etc/hosts)\n"
        "- Result: `PASS`\n",
        "not a repository path",
        id="accepted-report-link-escapes-the-tree-through-dot-dot",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [the repository root](../../..)\n"
        "- Result: `PASS`\n",
        "is a directory, not a file",
        id="accepted-report-links-to-the-repository-root",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [the whole directory](../reviews)\n"
        "- Result: `PASS`\n",
        "is a directory, not a file",
        id="accepted-report-links-to-a-directory",
    ),
    # --- F3: an earlier line must not silently override the real one (REVIEW-TASK-001.md) ---
    pytest.param(
        "- Status: `DRAFT`\n\n(real header below)\n\n- Status: `ACCEPTED`\n\n"
        "## Review\n\n- Attack report:\n- Result: `FAIL`\n",
        "2 `Status:` lines",
        id="an-earlier-status-line-no-longer-exempts-the-packet",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n- Result: `PASS`\n\n## Review\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n- Result: `FAIL`\n",
        "2 `Result:` lines",
        id="an-earlier-result-line-no-longer-overrides-the-real-one",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n\n"
        "## Review\n\n- Attack report: none, reviewed by eye\n- Result: `PASS`\n",
        "2 `Attack report:` lines",
        id="an-earlier-attack-report-line-no-longer-overrides-the-real-one",
    ),
    # --- _unquoted: a value cannot be partially stripped into an accidental match ---
    pytest.param(
        "- Status: `ACCEPTED` extra\n",
        "not one of",
        id="status-with-trailing-text-after-the-closing-backtick-is-rejected",
    ),
    pytest.param(
        "- Status: `ACCEPTED\n",
        "not one of",
        id="status-with-an-unbalanced-backtick-is-rejected",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS` extra\n",
        "not `PASS`",
        id="result-with-trailing-text-after-the-closing-backtick-is-rejected",
    ),
]


@pytest.mark.parametrize(("text", "expected"), REJECTED_CASES)
def test_a_malformed_packet_is_rejected_and_named(text: str, expected: str) -> None:
    """Each case carries exactly one defect, so a passing check names it precisely."""
    problems = packet_problems(text, "packet")
    assert len(problems) == 1, problems
    assert expected in problems[0], problems


CLEAN_CASES = [
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [operating model](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        id="accepted-report-links-to-an-existing-file",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [operating model](../TASK-PACKET-TEMPLATE.md#objective)\n"
        "- Result: `PASS`\n",
        id="accepted-report-link-fragment-is-stripped-before-checking-existence",
    ),
    pytest.param(
        # Three levels of `..` — as deep as the real `../../../experiments/...` reports
        # reviews/README.md describes — landing on AGENTS.md rather than anything under
        # experiments/: AGENTS.md itself says that tree is disposable, so it is the one
        # anchor in this repository less likely to move than the guard's own module-level
        # dependencies.
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [project instructions](../../../AGENTS.md)\n"
        "- Result: `PASS`\n",
        id="accepted-report-link-through-dot-dot-that-stays-inside-the-tree",
    ),
    pytest.param(
        "- Status: `DRAFT`\n",
        id="non-accepted-status-is-not-held-to-the-report-bar",
    ),
]


@pytest.mark.parametrize("text", CLEAN_CASES)
def test_a_well_formed_packet_produces_no_problems(text: str) -> None:
    """The validator must not simply reject everything it is given."""
    assert packet_problems(text, "packet") == []
