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

``STATUS_VALUES`` below is a copy of the template's own vocabulary rather than
something parsed out of it at import time, so that a template formatting
change fails one named test (``test_status_values_match_the_template``)
instead of silently changing what every other test in this file accepts.

``docs/agent-workflow/reviews/README.md`` says an attack report lives in this
repository — beside the experiment it attacks, or under
``docs/agent-workflow/reviews/`` when there is none. A link is therefore
always possible for a real report, so ``Attack report:`` must contain a
markdown link whose target is a repository path that exists: prose alone
("reviewed manually, no defects found") is exactly the unverifiable claim
this project keeps catching, and accepting it would make the non-emptiness
check decorative. A target that reads as a URL, a ``mailto:`` link, or a
same-document ``#anchor`` is rejected for the same reason — none of those can
name a file in this repository. The link target is resolved relative to
``docs/agent-workflow/task-packets/`` (where ``task-packets/README.md`` says
every packet is created), and a ``#fragment`` on an otherwise-valid path is
stripped before that check, so a heading anchor on a real file still
resolves.

The real directory scan below proves nothing by itself: it can only fail when
some packet under ``docs/agent-workflow/task-packets/`` is both ``ACCEPTED``
and defective, and today that directory may hold no ``ACCEPTED`` packet at
all. What gives this guard teeth is ``packet_problems`` being exercised
directly against malformed packet bodies built inline, below, which do not
depend on anything existing on disk.

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


def _field_value(text: str, field: str) -> str | None:
    r"""Return the trailing text of a ``- {field}: ...`` line, or ``None`` if absent.

    The gaps around the field name use ``[ \t]*`` rather than ``\s*`` on purpose:
    ``\s`` matches a newline, so an empty field (``- Attack report:`` with
    nothing after it) would let the pattern run on and capture the *next*
    line's content as this field's value instead of an empty string.
    """
    pattern = re.compile(rf"^-[ \t]*{re.escape(field)}:[ \t]*(.*)$", re.MULTILINE)
    match = pattern.search(text)
    return None if match is None else match.group(1).strip()


def _unquoted(value: str) -> str:
    """Strip one wrapping pair of backticks, the convention every Status/Result value uses."""
    if len(value) >= 2 and value[0] == "`" and value[-1] == "`":
        return value[1:-1].strip()
    return value


def _linked_report_target(report: str) -> str | None:
    """Return a markdown link's target found in ``report``, or ``None`` if it has none."""
    match = _MARKDOWN_LINK.search(report)
    return None if match is None else match.group(1).strip()


def _is_repository_path(target: str) -> bool:
    """True unless ``target`` is a URL, a mail link, or a same-document ``#anchor``.

    None of those name a file this guard can check for existence, and the task
    that specified this guard asked to keep the check narrow: only something
    that reads as a path into this repository is resolved on disk.
    """
    return not _URL_SCHEME.match(target) and not target.startswith(("mailto:", "#"))


def packet_problems(text: str, name: str) -> list[str]:
    """Return every defect ``text`` has as a task packet; ``[]`` means it is clean.

    ``name`` labels the packet in the returned messages only. A link inside
    ``Attack report:`` is resolved against :data:`TASK_PACKETS_DIR`, not
    against ``name``, so the malformed-packet cases below can exercise this
    function without a corresponding file on disk.
    """
    raw_status = _field_value(text, "Status")
    if raw_status is None:
        return [f"{name}: no `Status:` line"]
    status = _unquoted(raw_status)
    if status not in STATUS_VALUES:
        return [f"{name}: Status {status!r} is not one of {sorted(STATUS_VALUES)}"]
    if status != ACCEPTED_STATUS:
        return []

    problems: list[str] = []

    raw_report = _field_value(text, "Attack report")
    if not raw_report:
        problems.append(f"{name}: Status is {ACCEPTED_STATUS} but Attack report: is empty")
    else:
        target = _linked_report_target(raw_report)
        if target is None:
            problems.append(
                f"{name}: Status is {ACCEPTED_STATUS} but Attack report: has no markdown link"
            )
        elif not _is_repository_path(target):
            problems.append(
                f"{name}: Attack report links to {target!r}, which is not a repository path"
            )
        else:
            path_part = target.split("#", 1)[0].strip()
            resolved = (TASK_PACKETS_DIR / path_part).resolve()
            if not resolved.exists():
                problems.append(
                    f"{name}: Attack report links to {target!r}, but {resolved} does not exist"
                )

    raw_result = _field_value(text, "Result")
    result = None if raw_result is None else _unquoted(raw_result)
    if result != "PASS":
        problems.append(
            f"{name}: Status is {ACCEPTED_STATUS} but Result is {result!r}, not `PASS`"
        )

    return problems


def packet_paths() -> list[Path]:
    """Every task packet under :data:`TASK_PACKETS_DIR`, excluding its own index."""
    if not TASK_PACKETS_DIR.is_dir():
        return []
    return sorted(
        path
        for path in TASK_PACKETS_DIR.iterdir()
        if path.is_file() and path.name not in NON_PACKET_FILES
    )


def test_every_accepted_task_packet_carries_its_closing_evidence() -> None:
    """The real scan over whatever packets currently exist.

    This passes vacuously whenever no packet under
    ``docs/agent-workflow/task-packets/`` is both ``ACCEPTED`` and defective
    — including, today, the case of no ``ACCEPTED`` packet existing at all.
    The parametrized tests below are what actually prove ``packet_problems``
    rejects a bad one.
    """
    problems: list[str] = []
    for path in packet_paths():
        text = path.read_text(encoding="utf-8")
        problems.extend(packet_problems(text, str(path.relative_to(REPO_ROOT))))
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
        "- Attack report: [operating model](../README.md)\n"
        "- Result: `FAIL`\n",
        "Result",
        id="accepted-with-failing-result",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [operating model](../README.md)\n",
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
        "- Attack report: [operating model](../README.md)\n"
        "- Result: `PASS`\n",
        id="accepted-report-links-to-an-existing-file",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [operating model](../README.md#required-flow)\n"
        "- Result: `PASS`\n",
        id="accepted-report-link-fragment-is-stripped-before-checking-existence",
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
