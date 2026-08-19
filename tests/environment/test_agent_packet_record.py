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

A second, independent review of that repair (``REVIEW-TASK-001-R2.md``) found
three more. **R2-F1:** the field pattern anchored ``-`` at column 0, so a
real ``## Review`` field written indented — still a valid list item — or
with a ``*``/``+`` bullet was invisible, and the duplicate rule F3 built
only sees what the pattern matches. That round's fix widened the pattern to
match those two forms; it was an instance-level fix, and the paragraph below
explains what replaced it. **R2-F4:** resolving a link target could raise
instead of returning an answer — an over-long target raises ``OSError`` (not
at ``Path.resolve()`` itself on every platform; measured here, at the
``is_dir()``/``exists()`` calls that follow it) and an embedded NUL raises
``ValueError`` at ``resolve()``. Both are now caught around every
filesystem-touching call on the resolved path, and reported as a defect
rather than aborting ``scan_task_packets`` before a later packet is read —
the same failure shape F13 named for an undecodable file. **R2-F10:** an
``Attack report:`` value carrying two markdown links resolved only the
first, via ``.search()`` — so a harmless placeholder link could sit beside a
second, unrelated one nobody checked. Left open through this round and the
next; the fix is below, with F3's duplicate rule as the reason.

A third review (``REVIEW-TASK-001-R3.md``) measured a pattern across the
first two, not a defect: *"every round has repaired what the previous report
demonstrated and left what it characterised."* **R3-F1 — the class R2-F1's
fix was an instance of:** a blockquote (``> - Field: ...``), no bullet at
all, an ordered-list marker (``1.``), a table row (``| Field | value |``), a
non-breaking space or a BOM before the bullet, and a Unicode ``•`` bullet
were all still invisible to R2-F1's widened-but-still-a-list-item pattern —
each one a real field could plausibly be written as, each one a decoy could
use to stay the only visible match. ``_field_values`` no longer parses a
list item; it counts a line as stating a field whenever, once every BOM is
stripped and every non-breaking space is normalised, the line reads to a
human as declaring that field. The rule in full, including why fenced
content is still not excluded, is on ``_field_values`` itself. **R2-F10** is
fixed in this same round, by the reasoning F3 already established: more
than one markdown link in an ``Attack report:`` value is rejected rather
than resolving only the first, the same way more than one matching field
line is rejected rather than picking one. **R3-F7:** the sibling defect to
R2-F4, in the function F13 was originally about —
``scan_task_packets``'s ``read_text`` caught only ``UnicodeDecodeError``,
leaving a permission-denied file (``PermissionError``, an ``OSError``) able
to abort the scan the same way an undecodable one used to; ``iterdir()`` and
``is_file()`` were exposed to the same class unguarded. All three now are.
**R3-F9:** two of the three messages ``_report_target_problem`` can return
interpolated the resolved path raw, where the third already went through
``_short``; all three now do.

``STATUS_VALUES`` below is a copy of the template's own vocabulary rather than
something parsed out of it at import time, so that a template formatting
change fails one named test (``test_status_values_match_the_template``)
instead of silently changing what every other test in this file accepts.

``docs/agent-workflow/reviews/README.md`` says an attack report lives in this
repository — beside the experiment it attacks, or under
``docs/agent-workflow/reviews/`` when there is none. A link is therefore
always possible for a real report, so ``Attack report:`` must contain exactly
one markdown link (R2-F10), whose target, once resolved against
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
directly against malformed packet bodies built inline, below. Every inline
case whose link resolves depends on one of exactly two real files —
:data:`DISCLOSED_ON_DISK_DEPENDENCIES` names them, and
``test_every_inline_case_that_resolves_depends_on_a_disclosed_file`` checks
it — rather than inventing an undisclosed dependency, which is what happened
twice: first when several cases resolved against
``docs/agent-workflow/README.md`` instead of something this module already
needed (REVIEW-TASK-001.md **F12**), and again when the directory-rejection
case resolved against ``docs/agent-workflow/reviews/`` instead
(REVIEW-TASK-001-R2.md **R2-F5**, which also found this paragraph, a commit
message, and a hand count each stating a different number of such cases —
the reason the count is a checked fact now and not a sentence here).

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

import os
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

#: The only real files the inline cases below are allowed to depend on, besides
#: TASK_PACKETS_DIR itself. Both are already load-bearing for this module —
#: TASK_PACKET_TEMPLATE is read directly by test_status_values_match_the_template,
#: and AGENTS.md is this repository's chosen permanence anchor (see CLEAN_CASES).
#: How many cases use which is checked by
#: test_every_inline_case_that_resolves_depends_on_a_disclosed_file, not counted
#: in prose here — REVIEW-TASK-001-R2.md R2-F5 found three different counts of
#: that number in this file's own history (a docstring, a commit message, and
#: the true count), which is what a hand-maintained count does eventually.
DISCLOSED_ON_DISK_DEPENDENCIES = frozenset(
    {TASK_PACKET_TEMPLATE.resolve(), (REPO_ROOT / "AGENTS.md").resolve()}
)

_MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


def _field_values(text: str, field: str) -> list[str]:
    r"""Return the trailing text of every line that states ``{field}:``, in document order.

    Returning every match rather than just the first is what lets
    ``packet_problems`` refuse to pick a winner among several instead of
    picking the wrong one — see the module docstring's account of F3.

    REVIEW-TASK-001-R2.md R2-F1 widened this from "a ``-`` bullet at column
    0" to "any indentation, with ``-``/``*``/``+``" — an instance-level fix.
    REVIEW-TASK-001-R3.md R3-F1 measured what that left open: a blockquote
    (``> - Field: ...``), no bullet at all, an ordered-list marker (``1.``),
    a table row (``| Field | value |``), a non-breaking space or a BOM
    before the bullet, and a Unicode ``•`` bullet were all still invisible —
    each one a real ``## Review`` field could plausibly be written as, and
    each one a decoy could use to stay the pattern's only visible match.

    So this stops parsing "a list item" and counts instead: a line counts if,
    once normalised, it reads as stating the field to a human. Normalising
    means stripping every BOM and treating every non-breaking space as an
    ordinary one, across the whole text, before matching begins. A counted
    line then allows, from its start: any amount of whitespace; a leading
    blockquote run of any length (``>``, ``>>``, ``> >``); more whitespace;
    at most one marker — a ``-``/``*``/``+``/``•`` bullet, a table row's
    leading ``|``, or an ordinal like ``1.``/``1)`` — or no marker at all;
    more whitespace; the field name; more whitespace; and a separator that
    is ``:`` or ``|`` (a table cell has no colon). What follows is the
    captured value.

    Fenced code blocks are deliberately *not* excluded, even though this
    means a packet that quotes its own field syntax verbatim inside a fence
    trips the duplicate rule too. Skipping fenced content would let the
    real, binding field disappear from the count entirely — hidden inside a
    fence, not merely written in a form the pattern misses — while an
    unfenced decoy stood alone and unchallenged. A false rejection of an
    unusual but honest packet is the safe direction to be wrong in, and that
    trade only grows as the pattern widens; it is accepted for the same
    reason each time.

    The gaps around the field name use ``[ \t]*`` rather than ``\s*`` on
    purpose: ``\s`` matches a newline, so an empty field (``- Attack report:``
    with nothing after it) would let the pattern run on and capture the
    *next* line's content as this field's value instead of an empty string.
    """
    # Explicit \u escapes, not literal characters: a BOM and a non-breaking
    # space are visually indistinguishable from "nothing" and "a regular
    # space" in a source file, which is exactly the property that makes them
    # worth normalising in a packet in the first place. Escapes keep this line
    # honest about what it does.
    normalized = text.replace("\ufeff", "").replace("\u00a0", " ")
    pattern = re.compile(
        rf"^[ \t]*(?:>[ \t]*)*[ \t]*(?:[-*+\u2022|]|\d+[.)])?[ \t]*"
        rf"{re.escape(field)}[ \t]*(?::|\|)[ \t]*(.*)$",
        re.MULTILINE,
    )
    return [match.group(1).strip() for match in pattern.finditer(normalized)]


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


def _linked_report_targets(report: str) -> list[str]:
    """Return every markdown link target found in ``report``, in document order.

    REVIEW-TASK-001-R2.md R2-F10, left open through two rounds: the previous
    version took only the first link via ``.search()``, so
    ``[placeholder](../TASK-PACKET-TEMPLATE.md) ... [here](https://example.com/none)``
    resolved the harmless placeholder and never looked at the second link at
    all. Returning every target, and rejecting more than one in
    ``packet_problems``, matches the duplicate rule's own reasoning: refusing
    to pick a winner among several is what closes a bypass that picking
    either the first or the last one open again.
    """
    return [match.group(1).strip() for match in _MARKDOWN_LINK.finditer(report)]


def _short(text: str, limit: int = 80) -> str:
    """Truncate ``text`` for an error message; an attacker controls its length, not its use."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...({len(text)} chars)"


def _report_target_problem(target: str) -> str | None:
    """Why ``target`` cannot stand as an ``Attack report:`` link, or ``None`` if it can.

    REVIEW-TASK-001.md F2: the previous check tested only that ``target`` was
    not a URL, a ``mailto:`` link, or a bare ``#anchor`` — so an absolute
    path, a ``..`` escape, and a link to a directory all passed as "a
    repository path". ``Path.resolve()`` returns an absolute input unchanged
    and collapses every ``..`` segment, so checking containment on the
    *resolved* path is what catches both kinds of escape; a string check for
    the substring ``..`` cannot, because a legitimate link needs it too.

    Every filesystem-touching call below is inside one ``try`` (REVIEW-TASK-001-R2.md
    R2-F4), not just ``Path.resolve()``: a target long enough to blow a
    filesystem's name-length limit does not fail at ``resolve()`` on every
    platform — measured here, it raises ``OSError`` only once something
    actually calls ``stat`` on it, which ``is_dir()`` and ``exists()`` both
    do. Guarding ``resolve()`` alone leaves those two calls exposed to the
    exact defect this is fixing. An embedded NUL byte does fail at
    ``resolve()`` itself. Either raised exception, unhandled, would abort
    ``scan_task_packets`` the way F13's undecodable file used to: not a
    silent pass, but a scan that stops short and blames the wrong packet.

    All three returned reasons truncate what they interpolate
    (REVIEW-TASK-001-R3.md R3-F9): the exception branch already did, but the
    other two interpolated ``resolved`` — itself as unbounded as ``target``,
    since it is built from it — raw.
    """
    if _URL_SCHEME.match(target) or target.startswith(("mailto:", "#")):
        return "which is not a repository path"
    path_part = target.split("#", 1)[0].strip()
    try:
        resolved = (TASK_PACKETS_DIR / path_part).resolve()
        if not resolved.is_relative_to(REPO_ROOT):
            return "which is not a repository path"
        is_directory = resolved.is_dir()
        already_exists = resolved.exists()
    except (OSError, ValueError) as error:
        # str(error) embeds the OS message's own copy of the offending path, which
        # is exactly as unbounded as ``target`` — truncate it too, not only ``target``.
        return f"whose target does not resolve to a path at all ({_short(str(error))})"
    if is_directory:
        return f"but {_short(str(resolved))} is a directory, not a file"
    if not already_exists:
        return f"but {_short(str(resolved))} does not exist"
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
        targets = _linked_report_targets(reports[0])
        if not targets:
            problems.append(
                f"{name}: Status is {ACCEPTED_STATUS} but Attack report: has no markdown link"
            )
        elif len(targets) > 1:
            problems.append(
                f"{name}: Attack report: {len(targets)} markdown links found; "
                "exactly one is required"
            )
        else:
            reason = _report_target_problem(targets[0])
            if reason is not None:
                problems.append(
                    f"{name}: Attack report links to {_short(targets[0])!r}, {reason}"
                )

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

    Every filesystem-touching call is guarded the same way
    (REVIEW-TASK-001-R3.md R3-F7): the sibling defect to R2-F4, in the
    function F13 was originally about. ``read_text`` used to catch only
    ``UnicodeDecodeError``; an unreadable file raises ``PermissionError`` (an
    ``OSError``), and ``iterdir()`` and ``is_file()`` can raise the same way
    on a directory this process cannot fully stat. Any of them, unguarded,
    would abort the whole scan before a later, genuinely defective packet is
    ever read — F13's own failure shape, reached through a different call.

    Parameterized on ``directory`` rather than closing over
    :data:`TASK_PACKETS_DIR` so the tests below can reproduce all three
    failure modes against a throwaway ``tmp_path`` tree instead of the real
    one.
    """
    if not directory.is_dir():
        return []
    try:
        entries = sorted(directory.iterdir())
    except OSError as error:
        return [f"{directory}: cannot list this directory ({_short(str(error))})"]
    problems: list[str] = []
    for path in entries:
        if path.name in NON_PACKET_FILES:
            continue
        label = path.relative_to(directory)
        try:
            is_file = path.is_file()
        except OSError as error:
            problems.append(
                f"{label}: cannot check what kind of entry this is ({_short(str(error))})"
            )
            continue
        if not is_file:
            problems.append(f"{label}: task-packets holds one file per packet, not a directory")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            problems.append(f"{label}: not valid UTF-8 ({error})")
            continue
        except OSError as error:
            problems.append(f"{label}: cannot read this file ({_short(str(error))})")
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


def test_short_truncates_long_text_and_leaves_short_text_alone() -> None:
    """The mechanism R3-F9 asked applied to two more call sites; this is the unit test
    those two call sites never had — they were only ever exercised as part of a
    longer message, which would not catch _short itself regressing.
    """
    assert _short("short") == "short"
    at_the_limit = "x" * 80
    assert _short(at_the_limit) == at_the_limit
    just_over_the_limit = "x" * 81
    assert _short(just_over_the_limit) == "x" * 80 + "...(81 chars)"
    # The "(N chars)" suffix can make a barely-over-limit input longer once
    # truncated, not shorter — _short bounds the worst case, not every case.
    # A genuinely long input is what the bound actually needs to hold for.
    much_longer = "x" * 5000
    truncated = _short(much_longer)
    assert len(truncated) < len(much_longer)
    assert truncated == "x" * 80 + "...(5000 chars)"


def test_a_long_missing_target_message_is_truncated() -> None:
    """R3-F9: ``resolved`` was interpolated raw in the "does not exist" and "is a
    directory" branches, which ``_short`` never reached. Only the first is tested
    directly here — constructing a genuinely long *existing* directory without
    creating one on disk under the real ``task-packets/`` is not possible without
    either a fixture this file is not allowed to leave behind or changing how
    ``_report_target_problem`` resolves paths, which was not asked for. Both
    branches call the identical ``_short(str(resolved))``, checked in isolation
    above, so this is not a proof of the second branch — it is the honest edge
    of what this file can check without either of those.
    """
    target = "/".join(["nonexistent-segment"] * 20)
    text = (
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        f"- Attack report: [r]({target})\n"
        "- Result: `PASS`\n"
    )
    problems = packet_problems(text, "packet")
    assert len(problems) == 1, problems
    assert "does not exist" in problems[0], problems
    assert len(problems[0]) < 300, problems  # the raw, untruncated message exceeds 500


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


def test_scanning_reports_an_unreadable_file_and_keeps_going(tmp_path: Path) -> None:
    """R3-F7: the same class R2-F4 fixed in ``_report_target_problem``, in the
    sibling function F13 was originally about. ``read_text`` caught only
    ``UnicodeDecodeError``; a permission-denied file raises ``PermissionError``
    (an ``OSError``), which was unguarded and would abort the scan the same way.
    """
    unreadable = tmp_path / "TASK-000-unreadable.md"
    unreadable.write_text("- Status: `ACCEPTED`\n", encoding="utf-8")
    unreadable.chmod(0o000)
    try:
        if os.access(unreadable, os.R_OK):
            pytest.skip("this process can read a mode-000 file it owns (running as root?)")
        (tmp_path / "TASK-999-defective.md").write_text(
            "- Status: `ACCEPTED`\n\n## Review\n\n- Attack report:\n- Result: `PASS`\n",
            encoding="utf-8",
        )
        problems = scan_task_packets(tmp_path)
    finally:
        unreadable.chmod(0o644)  # so tmp_path's own teardown can remove it
    assert any("cannot read" in problem for problem in problems), problems
    assert any("Attack report" in problem for problem in problems), problems


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
        # "." resolves to TASK_PACKETS_DIR itself — a directory the module already
        # depends on structurally, rather than an undisclosed one. The original
        # version of this case used `../reviews` and REVIEW-TASK-001-R2.md R2-F5
        # named that: it fails with "does not exist" instead of "is a directory,
        # not a file" in a tree without that directory, naming the wrong defect.
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [the packet directory itself](.)\n"
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
    # --- R2-F1: indentation and bullet character (REVIEW-TASK-001-R2.md) ---
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "  - Result: `FAIL`\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="an-indented-decoy-result-line-is-no-longer-invisible",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "* Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Attack report: none, reviewed by eye\n"
        "- Result: `PASS`\n",
        "2 `Attack report:` lines",
        id="a-star-bullet-decoy-attack-report-line-is-no-longer-invisible",
    ),
    pytest.param(
        # A packet that quotes its own field syntax inside a fenced example is a
        # false positive this guard accepts on purpose — see _field_values's
        # docstring for why skipping fenced content would be worse.
        "- Status: `ACCEPTED`\n\n"
        "## Worker handoff\n\n"
        "Example of the field this packet must carry:\n\n"
        "```\n"
        "- Result: `FAIL`\n"
        "```\n\n"
        "## Review\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="a-quoted-example-inside-a-fenced-block-still-counts-as-a-duplicate",
    ),
    # --- R2-F4: a pathological link target must not abort the scan (REVIEW-TASK-001-R2.md) ---
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        f"- Attack report: [r]({'x' * 5000})\n"
        "- Result: `PASS`\n",
        "does not resolve to a path",
        id="a-link-target-too-long-for-the-filesystem-is-reported-not-raised",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [r](a\x00b)\n"
        "- Result: `PASS`\n",
        "does not resolve to a path",
        id="a-link-target-with-an-embedded-null-byte-is-reported-not-raised",
    ),
    # --- R3-F1: every placement the reviewer demonstrated, not just indent and
    # bullet character (REVIEW-TASK-001-R3.md). Each decoy states `Result` a
    # second time in one of the seven forms the widened pattern must all count. ---
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "> - Result: `FAIL`\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="a-blockquoted-decoy-result-line-is-no-longer-invisible",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "Result: `FAIL`\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="a-bare-unbulleted-decoy-result-line-is-no-longer-invisible",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "1. Result: `FAIL`\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="an-ordered-list-decoy-result-line-is-no-longer-invisible",
    ),
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "| Result | FAIL |\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="a-table-row-decoy-result-line-is-no-longer-invisible",
    ),
    pytest.param(
        # The leading character on the decoy line is U+00A0 (non-breaking space),
        # not a regular space — indistinguishable by eye, which is the point.
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "\u00a0- Result: `FAIL`\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="a-non-breaking-space-indented-decoy-result-line-is-no-longer-invisible",
    ),
    pytest.param(
        # U+FEFF (BOM) immediately before the bullet.
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "\ufeff- Result: `FAIL`\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="a-bom-prefixed-decoy-result-line-is-no-longer-invisible",
    ),
    pytest.param(
        # U+2022 (bullet) as the marker, not - / * / +.
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "\u2022 Result: `FAIL`\n\n"
        "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
        "- Result: `PASS`\n",
        "2 `Result:` lines",
        id="a-unicode-bullet-decoy-result-line-is-no-longer-invisible",
    ),
    # --- R2-F10: an Attack report carrying two links is ambiguous the same way a
    # duplicated field is (REVIEW-TASK-001-R2.md, left open through R2 and R3). ---
    pytest.param(
        "- Status: `ACCEPTED`\n\n## Review\n\n"
        "- Attack report: [placeholder](../TASK-PACKET-TEMPLATE.md) "
        "— the real one is [here](https://example.com/none)\n"
        "- Result: `PASS`\n",
        "markdown links found",
        id="an-attack-report-with-two-links-is-rejected",
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


def test_every_inline_case_that_resolves_depends_on_a_disclosed_file() -> None:
    """Replaces a hand count with a check (REVIEW-TASK-001-R2.md R2-F5).

    Every link target across every case above that this guard would accept as
    a real repository path is resolved the same way ``packet_problems``
    resolves one, and the file it lands on must be in
    :data:`DISCLOSED_ON_DISK_DEPENDENCIES`. A case depending on anything else
    — the way ``accepted-report-links-to-a-directory`` used to depend on
    ``docs/agent-workflow/reviews/`` before R2-F5 — fails here by name instead
    of surfacing later as an unrelated red test in a tree missing that file.
    """
    found: set[Path] = set()
    for case in (*REJECTED_CASES, *CLEAN_CASES):
        text = case.values[0]
        assert isinstance(text, str)  # pytest.param's values are untyped; narrow for mypy
        for match in _MARKDOWN_LINK.finditer(text):
            target = match.group(1).strip()
            if _report_target_problem(target) is not None:
                continue  # rejected outright; not a dependency this case relies on
            path_part = target.split("#", 1)[0].strip()
            found.add((TASK_PACKETS_DIR / path_part).resolve())
    undisclosed = found - DISCLOSED_ON_DISK_DEPENDENCIES
    assert not undisclosed, undisclosed
