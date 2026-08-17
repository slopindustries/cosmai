"""SEC-004's dashboard half: the screen an operator reads, searched for every marker.

`test_api.py` executes SEC-004 steps 1 to 3 as far as the API. Action step 3 also
names *"the dashboard job-detail screen"* and step 4 asks for a screenshot of it,
and until this module existed both were recorded as unmet: a field that is returned
by an endpoint but never rendered does not satisfy the charter's diagnosis criterion,
and neither does a field that is rendered somewhere nobody checked.

**What is executed here, and what is not.** The screen is rendered by the same
components the browser mounts, under Node, from HTTP responses this module's probe
obtained from a real API process — see `dashboard/src/detail-text.tsx`. What comes
back is the visible text of that screen, and every assertion below searches it. That
is the reading half of step 3, executed on every run. It is **not** the screenshot of
step 4: a screenshot needs a browser driver, DP-006 D6 puts the dependency floor
below one, and a value hidden by CSS or parked in an attribute would pass this
module and fail a human's eyes. The reproduction procedure for the screenshot is in
`dashboard/README.md`, and SEC-004's `Result` section states which half was executed
how rather than letting the two read as one.

**Three jobs, because one cannot carry all the controls.**

===========  ===========================================  ==========================
Job          How it reaches its state                     What it is here for
===========  ===========================================  ==========================
`failed`     SEC-004's Action verbatim: a marked payload   the payload markers, and
             and `handler = "fail_permanent"`, run by a    the detection control
             real worker process
`detail`     completed through `complete_permanent` with   whether `error_detail` is
             markers **inside** `error_detail`             on the default screen
`done`       `succeed`, then a retry is requested          the refusal OPS-002 needs
                                                          shown as the API gave it
===========  ===========================================  ==========================

The middle one exists because `fail_permanent` builds its own detail — `{"attempt_no":
n}` — so job `failed` alone could only show that *some* detail is reachable, never
that a value inside it was withheld. Putting a distinctive marker inside
`error_detail` and finding it on the protected screen and **not** on the default one
turns "the default screen withholds detail" from an absence into an observation.
"""

from __future__ import annotations

import fcntl
import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from shutil import which
from typing import Any

import httpx
import pytest
from platform_core.api.app import DEFAULT, PROTECTED, PROTECTED_FIELD
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import ErrorClass, PlatformPermanentError
from platform_core.jobs.state import AttemptOutcome, JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from platform_core.obs.redaction import REDACTED_KEYS, REDACTION_MARKER

from tests.conftest import (
    EXPERIMENT_ROOT,
    LEASE_SECONDS,
    WORKER,
    cloned_database,
    keep_databases,
    run_worker,
    running_api,
)

DASHBOARD = EXPERIMENT_ROOT / "dashboard"

#: What `npm run text:build` produces. Running it is this module's own setup.
TEXT_BUNDLE = DASHBOARD / "dist-text" / "assets" / "detail-text.js"

#: Held while the bundle is built, so two `pytest-xdist` workers that both want it
#: cannot write the same output directory at once. The same mechanism `conftest.py`
#: uses for the migrated template database, for the same reason.
BUILD_LOCK = DASHBOARD / ".text-build.lock"

BUILD_TIMEOUT_SECONDS = 300.0

RENDER_TIMEOUT_SECONDS = 60.0

REQUEST_TIMEOUT_SECONDS = 10.0

MAX_ATTEMPTS = 3

#: One distinctive payload value per redacted key, so a leak says which key leaked.
#: Deliberately different strings from `test_api.py`'s: a marker found on the screen
#: has then come through this module's own job and not through a shared constant.
SCREEN_MARKERS: dict[str, str] = {
    key: f"screen-must-not-leak-{key}-42" for key in sorted(REDACTED_KEYS)
}

PAYLOAD_ORDINARY_KEY = "note"

#: The detection control for the payload. It contains no reserved term, so nothing
#: in the platform has a reason to touch it, and its absence would mean the search
#: itself is broken rather than that the boundary held.
PAYLOAD_ORDINARY_MARKER = "screen-must-survive-42"

MARKED_PAYLOAD: dict[str, Any] = {
    **SCREEN_MARKERS,
    PAYLOAD_ORDINARY_KEY: PAYLOAD_ORDINARY_MARKER,
}

#: The same idea one level in: markers placed inside `error_detail`.
DETAIL_MARKERS: dict[str, str] = {
    key: f"detail-must-not-leak-{key}-42" for key in sorted(REDACTED_KEYS)
}

DETAIL_ORDINARY_KEY = "diagnosis"

#: The value that must be on the protected screen and absent from the default one.
DETAIL_ORDINARY_MARKER = "detail-must-not-render-42"

MARKED_DETAIL: dict[str, Any] = {
    **DETAIL_MARKERS,
    DETAIL_ORDINARY_KEY: DETAIL_ORDINARY_MARKER,
}

#: What the screen says when detail exists and this representation withholds it.
WITHHELD = "present, withheld"

#: The explicit action SEC-004 requires the screen to offer rather than imply.
EXPLICIT_ASK = "?debug=protected"


def toolchain_absent() -> str | None:
    """Why the screen cannot be rendered here, or ``None`` if it can.

    A skip rather than a failure, and the message names the command that fixes it.
    The dashboard's dependencies are not part of the Python environment, so a
    checkout that has never run `npm install` would otherwise fail a `SEC` test for
    a reason that has nothing to do with redaction.
    """
    for tool in ("npm", "node"):
        if which(tool) is None:
            return f"{tool} is needed to render the dashboard screen and is not on PATH"
    if not (DASHBOARD / "node_modules").is_dir():
        return (
            "the dashboard's dependencies are not installed; run `npm install` in "
            f"{DASHBOARD.relative_to(EXPERIMENT_ROOT.parent.parent)}"
        )
    return None


def _build_inputs() -> list[Path]:
    watched = [
        DASHBOARD / "package.json",
        DASHBOARD / "tsconfig.json",
        DASHBOARD / "vite.config.ts",
        *sorted((DASHBOARD / "src").iterdir()),
    ]
    return [path for path in watched if path.is_file()]


def _bundle_is_current() -> bool:
    if not TEXT_BUNDLE.is_file():
        return False
    built = TEXT_BUNDLE.stat().st_mtime
    return all(path.stat().st_mtime <= built for path in _build_inputs())


def build_text_renderer() -> None:
    """Build the Node entry that renders the screen, unless it is already current.

    Rebuilt from mtimes rather than unconditionally, because the build is the same
    inputs to the same output and a run that changed nothing should not pay for it.
    """
    with BUILD_LOCK.open("w", encoding="utf-8") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            if _bundle_is_current():
                return
            finished = subprocess.run(
                ["npm", "run", "--silent", "text:build"],
                cwd=DASHBOARD,
                capture_output=True,
                text=True,
                timeout=BUILD_TIMEOUT_SECONDS,
                check=False,
            )
            assert finished.returncode == 0, (
                f"the dashboard renderer did not build\n{finished.stdout}\n{finished.stderr}"
            )
            assert TEXT_BUNDLE.is_file(), f"the build produced no {TEXT_BUNDLE}"
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def rendered_screen(
    job: dict[str, Any],
    attempts: dict[str, Any],
    retry: dict[str, Any] | None = None,
) -> str:
    """The visible text of the job-detail screen for these API responses.

    The three arguments are API responses, unedited. Nothing is fetched inside the
    renderer, so what is searched below is a function of what the API actually said.
    """
    finished = subprocess.run(
        ["node", str(TEXT_BUNDLE)],
        input=json.dumps({"job": job, "attempts": attempts, "retry": retry}),
        cwd=DASHBOARD,
        capture_output=True,
        text=True,
        timeout=RENDER_TIMEOUT_SECONDS,
        check=False,
    )
    assert finished.returncode == 0, f"the screen did not render\n{finished.stderr}"
    return finished.stdout


#: Where SEC-004's Verification says the screens belong.
EVIDENCE_SCREEN = (
    EXPERIMENT_ROOT / "evidence" / "2026-08-17-5b26d47" / "sec-004-detail-screen.txt"
)

EVIDENCE_HEADER = """SEC-004 — the job-detail screens as an operator reads them
==============================================================================

Rendered by dashboard/src/detail-text.tsx: the same component tree the browser
mounts, from API responses this module's probe obtained from a real API process.
This is the reading half of SEC-004 step 3. It is NOT step 4's screenshot — a
value hidden by CSS or parked in a DOM attribute would pass a text search and
fail a person's eyes, and dashboard/README.md records the capture procedure.

Every value under a redacted key arrives already masked: the API masks on the
way out, so no screen ever holds one. The marker under the ordinary key survives,
which is the detection control — a screen that rendered nothing would satisfy the
eight absences for the wrong reason.

Regenerated by `-k sec_004`. The assertions in test_dashboard.py are the
authority; this file is what they were asserted over.

Data class: public. Synthetic throughout.
"""


def masked_entry(key: str) -> str:
    """The exact text the screen must show where a value was removed."""
    return f'"{key}": "{REDACTION_MARKER}"'


@dataclass(frozen=True)
class ScreenProbe:
    """Every screen this module asserts over, rendered once."""

    job: dict[str, Any]
    attempt: dict[str, Any]
    refusal: dict[str, Any]
    correlation_id: str
    default_screen: str
    protected_screen: str
    detail_default_screen: str
    detail_protected_screen: str
    refused_screen: str

    @property
    def both_screens(self) -> dict[str, str]:
        """Both representations of the marked-payload job, named for failure text."""
        return {
            "default job-detail screen": self.default_screen,
            "protected job-detail screen": self.protected_screen,
        }

    @property
    def every_screen(self) -> dict[str, str]:
        return {
            **self.both_screens,
            "default screen of the marked-detail job": self.detail_default_screen,
            "protected screen of the marked-detail job": self.detail_protected_screen,
            "refused-retry screen": self.refused_screen,
        }


def _store(handle: Any, config: PlatformConfig) -> JobStore:
    quiet = StructuredLogger(stream=StringIO(), level="DEBUG")
    return JobStore(handle, config, logger=quiet, metrics=MetricsRegistry())


@pytest.fixture(scope="module")
def screen_probe(
    platform_database: PlatformConfig,
    migrated_template: str,
    request: pytest.FixtureRequest,
) -> Iterator[ScreenProbe]:
    """SEC-004's Action, carried through to the screen, with every result frozen.

    Module-scoped for the reason `test_api.py`'s `redaction_probe` is: two worker
    runs, one API process, and five renders serve every assertion below, and at
    function scope the same setup would be replayed once per assertion.
    """
    absent = toolchain_absent()
    if absent is not None:
        pytest.skip(absent)
    build_text_renderer()

    with cloned_database(
        platform_database, migrated_template, "test", keep_databases(request)
    ) as database:
        # 1 and 2 — the marked payload, failed permanently by a real worker.
        with connected(database, autocommit=True) as handle:
            failed_id = _store(handle, database).create_job(
                "fail_permanent", MARKED_PAYLOAD, max_attempts=MAX_ATTEMPTS
            )
        first = run_worker(database, "--once")
        assert first.returncode == 0, first.stderr

        # The job whose retry must be refused, so the refusal is a real 409 body.
        with connected(database, autocommit=True) as handle:
            done_id = _store(handle, database).create_job("succeed", {}, max_attempts=MAX_ATTEMPTS)
        second = run_worker(database, "--once")
        assert second.returncode == 0, second.stderr

        # The job whose protected detail carries markers. Written through the same
        # completion path a handler's failure takes, so the detail is stored the way
        # the platform stores one.
        with connected(database, autocommit=True) as handle:
            store = _store(handle, database)
            detail_id = store.create_job("succeed", {}, max_attempts=MAX_ATTEMPTS)
            claimed = store.claim_next(WORKER, LEASE_SECONDS)
            assert claimed is not None
            assert claimed.job_id == detail_id
            completion = store.complete_permanent(
                detail_id,
                claimed.attempt_id,
                WORKER,
                PlatformPermanentError(
                    "the screen probe refused this attempt",
                    {**MARKED_DETAIL, "attempt_no": claimed.attempt_no},
                ),
            )
            assert completion.accepted

        # 3 — read every representation the screens need, over HTTP.
        with (
            running_api(database) as api,
            httpx.Client(base_url=api.base_url, timeout=REQUEST_TIMEOUT_SECONDS) as client,
        ):
            protected = {"debug": PROTECTED}
            job = client.get(f"/jobs/{failed_id}")
            attempts = client.get(f"/jobs/{failed_id}/attempts")
            protected_attempts = client.get(f"/jobs/{failed_id}/attempts", params=protected)
            detail_job = client.get(f"/jobs/{detail_id}")
            detail_attempts = client.get(f"/jobs/{detail_id}/attempts")
            detail_protected = client.get(f"/jobs/{detail_id}/attempts", params=protected)
            done_job = client.get(f"/jobs/{done_id}")
            done_attempts = client.get(f"/jobs/{done_id}/attempts")
            refusal = client.post(f"/jobs/{done_id}/retry")

        reads = (
            job,
            attempts,
            protected_attempts,
            detail_job,
            detail_attempts,
            detail_protected,
            done_job,
            done_attempts,
        )
        for response in reads:
            assert response.status_code == 200, response.text
        assert refusal.status_code == 409, refusal.text

        attempt_page: dict[str, Any] = attempts.json()
        assert len(attempt_page["attempts"]) == 1, attempt_page

        yield ScreenProbe(
            job=job.json(),
            attempt=attempt_page["attempts"][0],
            refusal=refusal.json(),
            correlation_id=str(job.json()["correlation_id"]),
            default_screen=rendered_screen(job.json(), attempt_page),
            protected_screen=rendered_screen(job.json(), protected_attempts.json()),
            detail_default_screen=rendered_screen(detail_job.json(), detail_attempts.json()),
            detail_protected_screen=rendered_screen(detail_job.json(), detail_protected.json()),
            refused_screen=rendered_screen(done_job.json(), done_attempts.json(), refusal.json()),
        )


# --------------------------------------------------------------------------- #
# The precondition, and the screen's identity
# --------------------------------------------------------------------------- #


def test_sec_004_the_screen_is_the_one_sec_004_names(screen_probe: ScreenProbe) -> None:
    """The failure was reached, and the screen is showing that job.

    Without this, every absence below could be the absence of a job.
    """
    assert screen_probe.job["state"] == JobState.FAILED
    assert screen_probe.job["terminal_reason"] == ErrorClass.PLATFORM_PERMANENT
    assert screen_probe.attempt["outcome"] == AttemptOutcome.PERMANENT_FAILURE
    assert screen_probe.attempt["error_detail_present"] is True
    screen = screen_probe.default_screen
    assert str(screen_probe.job["id"]) in screen, "the screen names the job it is showing"
    assert screen_probe.job["handler"] in screen
    assert str(screen_probe.attempt["error_summary"]) in screen


# --------------------------------------------------------------------------- #
# SEC-004 step 5 — search the screen for every marker
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("key", sorted(SCREEN_MARKERS))
def test_sec_004_no_payload_marker_under_a_redacted_key_reaches_any_screen(
    screen_probe: ScreenProbe, key: str
) -> None:
    marker = SCREEN_MARKERS[key]
    for name, screen in screen_probe.every_screen.items():
        assert marker not in screen, f"{key} leaked onto the {name}"


def test_sec_004_the_ordinary_payload_marker_is_on_the_screen(screen_probe: ScreenProbe) -> None:
    """The detection control. Without it the test above proves nothing.

    A value under an ordinary key is rendered in full, so the search that found
    nothing above is a search that works.
    """
    assert PAYLOAD_ORDINARY_MARKER in screen_probe.default_screen
    assert masked_entry(PAYLOAD_ORDINARY_KEY) not in screen_probe.default_screen


@pytest.mark.parametrize("key", sorted(SCREEN_MARKERS))
def test_sec_004_the_screen_shows_the_marker_where_the_value_was_removed(
    screen_probe: ScreenProbe, key: str
) -> None:
    """The key name survives on screen, with the redaction marker in its value.

    Asserted as the rendered pair rather than as two separate presences: `key` and
    the marker both appearing somewhere on a screen this size would be a much weaker
    claim than the marker appearing *as that key's value*.
    """
    assert masked_entry(key) in screen_probe.default_screen


def test_sec_004_the_correlation_identifier_is_on_the_screen_and_is_not_masked(
    screen_probe: ScreenProbe,
) -> None:
    """A redacted correlation identifier would make diagnosis impossible."""
    for name, screen in screen_probe.both_screens.items():
        assert screen_probe.correlation_id in screen, f"missing from the {name}"


# --------------------------------------------------------------------------- #
# `error_detail` is not on the default screen, and the control that proves it
# --------------------------------------------------------------------------- #


def test_sec_004_protected_detail_is_absent_from_the_default_screen(
    screen_probe: ScreenProbe,
) -> None:
    """The value inside `error_detail` is nowhere on the default representation.

    `DETAIL_ORDINARY_MARKER` sits under an ordinary key inside `error_detail`, so
    nothing masks it — the only reason it can be missing here is that the default
    screen does not render protected detail at all.
    """
    screen = screen_probe.detail_default_screen
    assert DETAIL_ORDINARY_MARKER not in screen
    assert PROTECTED_FIELD not in screen, "not even the field name is on the default screen"
    assert WITHHELD in screen, "the screen still says detail exists and is being withheld"


def test_sec_004_protected_detail_is_on_the_protected_screen(screen_probe: ScreenProbe) -> None:
    """The control for the test above, and SEC-004's "reachable" clause on a screen."""
    assert DETAIL_ORDINARY_MARKER in screen_probe.detail_protected_screen
    assert WITHHELD not in screen_probe.detail_protected_screen


@pytest.mark.parametrize("key", sorted(DETAIL_MARKERS))
def test_sec_004_the_protected_screen_still_masks_reserved_keys(
    screen_probe: ScreenProbe, key: str
) -> None:
    """Protected is about who may ask, not about what is masked."""
    screen = screen_probe.detail_protected_screen
    assert DETAIL_MARKERS[key] not in screen
    assert masked_entry(key) in screen


def test_sec_004_the_default_screen_offers_the_explicit_way_to_ask(
    screen_probe: ScreenProbe,
) -> None:
    """Question 6 of OPS-001 is answerable, and the next step is on the screen.

    An operator who can see that detail is withheld but not how to ask for it has
    been told half of something.
    """
    assert EXPLICIT_ASK in screen_probe.detail_default_screen
    assert EXPLICIT_ASK in screen_probe.default_screen


def test_sec_004_the_protected_screen_says_which_representation_it_is(
    screen_probe: ScreenProbe,
) -> None:
    assert DEFAULT in screen_probe.default_screen
    assert PROTECTED in screen_probe.protected_screen


# --------------------------------------------------------------------------- #
# OPS-001's six questions, on the screen rather than in a response body
# --------------------------------------------------------------------------- #


def test_sec_004_all_six_questions_are_answerable_from_the_rendered_screen(
    screen_probe: ScreenProbe,
) -> None:
    """The half OPS-001's result recorded as unmet: whether an operator *sees* them.

    Each entry is the question, and the values on screen that answer it. Labels are
    asserted alongside values because a timestamp with no label answers "when?" only
    for a reader who already knows which one it is.
    """
    screen = screen_probe.default_screen
    job = screen_probe.job
    attempt = screen_probe.attempt
    answers: dict[str, list[str]] = {
        "1 what ran": ["handler", str(job["handler"]), str(job["id"])],
        "2 with which input": ["payload", PAYLOAD_ORDINARY_MARKER],
        "3 when": [
            "created at",
            str(job["created_at"]),
            "started",
            str(attempt["started_at"]),
            "finished",
            str(attempt["finished_at"]),
        ],
        "4 why did it fail": [
            "terminal reason",
            str(job["terminal_reason"]),
            "error class",
            str(attempt["error_class"]),
            str(attempt["error_summary"]),
        ],
        "5 is anything left to try": [
            "attempts spent",
            f"{job['attempt_count']} of {job['max_attempts']}",
            "attempts remaining",
            "attempt budget spent",
            "class retryable",
        ],
        "6 is detail being withheld": ["protected detail", WITHHELD, EXPLICIT_ASK],
    }
    for question, expected in answers.items():
        for fragment in expected:
            assert fragment in screen, f"question {question} is unanswered: {fragment!r} missing"


def test_sec_004_the_screen_reports_the_worker_that_ran_the_attempt(
    screen_probe: ScreenProbe,
) -> None:
    """`OPS-003` reaches the log by correlation identifier; the screen names the process."""
    assert str(screen_probe.attempt["worker_id"]) in screen_probe.default_screen


# --------------------------------------------------------------------------- #
# OPS-002 — a refusal is shown as the API gave it
# --------------------------------------------------------------------------- #


def test_sec_004_a_refused_retry_shows_the_current_and_the_required_state(
    screen_probe: ScreenProbe,
) -> None:
    """"That failed" is not on this screen. The two states and the API's sentence are.

    OPS-002 is explicit that "this job is `SUCCEEDED`; a safe retry starts from
    `FAILED`" is actionable and "bad request" is not. The screen shows the `409`
    body's `current_state`, `required_state`, and `reason` unedited, so the operator
    reads the API's own explanation rather than the dashboard's paraphrase of it.
    """
    refusal = screen_probe.refusal
    screen = screen_probe.refused_screen
    assert refusal["accepted"] is False
    assert "Retry refused." in screen
    assert "current state" in screen
    assert "required state" in screen
    assert str(refusal["current_state"]) in screen
    assert str(refusal["required_state"]) in screen
    assert str(refusal["reason"]) in screen


def test_sec_004_the_refusal_screen_carries_no_marker_and_no_protected_detail(
    screen_probe: ScreenProbe,
) -> None:
    """The retry path is a third route out of the API, and the boundary is one rule."""
    screen = screen_probe.refused_screen
    for marker in (*SCREEN_MARKERS.values(), *DETAIL_MARKERS.values()):
        assert marker not in screen
    assert PROTECTED_FIELD not in screen

# ---------------------------------------------------------------------------
# Evidence capture
# ---------------------------------------------------------------------------


def test_sec_004_the_screens_are_written_to_the_evidence_directory(
    screen_probe: ScreenProbe,
) -> None:
    """Write the rendered screens where the gate reviewer can read them.

    SEC-004's Verification names an evidence location, and a screen asserted over
    but never captured leaves the reviewer taking the assertions on trust. The file
    is regenerated whenever this module runs, so it cannot drift from what was
    asserted — and the assertions above, not the file, remain the authority.
    """
    target = EVIDENCE_SCREEN
    if not target.parent.is_dir():
        pytest.skip(f"no evidence directory at {target.parent}")
    sections = [EVIDENCE_HEADER]
    for name, screen in screen_probe.every_screen.items():
        sections.append("\n" + "=" * 78 + f"\n{name}\n" + "=" * 78 + "\n\n" + screen)
    target.write_text("".join(sections), encoding="utf-8")
    written = target.read_text(encoding="utf-8")
    # The capture is only evidence if it carries what the assertions above checked.
    assert PAYLOAD_ORDINARY_MARKER in written
    for marker in SCREEN_MARKERS.values():
        assert marker not in written
