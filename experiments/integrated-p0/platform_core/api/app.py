"""The operator surface, and the two representations SEC-004 separates.

CONTRACT-JOB@0.1 says ``error_detail`` is never in an API response by default.
SEC-004 adds the half that is easy to lose: it *is* reachable, through an explicit
protected-debug representation available only on the loopback binding SEC-002
constrains, and **even there the redaction boundary holds**. Protected is about
who can ask, not about what is masked.

**The navigation model is three kinds of thing: platform health, jobs, and
attempts.** OQ-005 H1 claims those three are sufficient for every required
operator scenario, and its falsification condition is a scenario that needs a
fourth. Nothing below adds one. ``/metrics`` and ``/events`` are not a fourth kind
of thing: metrics are a reading of this process's counters, and events are the
structured log filtered by an identifier a job already carries. Neither is
navigable, neither has an identity, and neither can be reached except by asking
for it directly. A genuinely new object — a batch, a queue, a run — would be H1
refuted and would have to be named as such rather than added quietly.

Six decisions shape this module.

**Redaction happens on the way out, again.** Every value written into
``job_attempt.error_detail`` was already redacted by ``ProtectedDetail`` on the way
in, and every event was redacted by ``StructuredLogger`` before it reached the log.
Redacting once more here is not belt-and-braces for its own sake: this is the
boundary a response crosses, and a row or a line written by anything other than
those two — a migration, a fixture, a future writer, a hand-edited log — would
otherwise leave through it unmasked. ``redact`` is idempotent, so the second pass
costs nothing and removes the assumption.

**A connection per request.** The API holds no pool and no long-lived session. At
P0-A scale the cost is one connect per read, and what it buys is twofold: no
request can observe another request's transaction state, and nothing is cached
across requests — which is what lets ``/health`` report a database that stopped
being reachable, and then report it healthy again when it returns, without the
process being restarted.

**``/health`` reports the platform, not the process.** OPS-004's intent names the
failure mode directly: an endpoint that answers ``ok`` while nothing works
"converts an outage into a report of normal operation". So this one reaches the
database and reads the platform schema, and it also reports the queue depth,
because OPS-004 step 5 requires a queue with no worker not to read as identical to
an empty one.

**One write endpoint, and it is the one transition the contract gives an
operator.** ``POST /jobs/{id}/retry`` is ``FAILED → PENDING`` and nothing else.
Every other state is refused with the state it was in and the state a retry needs,
because OPS-002 is explicit that "this job is `SUCCEEDED`; a retry starts from
`FAILED`" is actionable and "bad request" is not. Reads write nothing: a ``GET``
that changed state would be its own defect.

**The event query takes an identifier, never a location.** ``/events`` filters the
log file named by ``COSMA_LOG_FILE``, resolved once at startup. A request supplies
a correlation identifier and a bound, so no query can be turned into a read of an
arbitrary path.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Annotated, Any, Final, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import ErrorClass, PlatformError
from platform_core.jobs.state import JobState
from platform_core.jobs.store import JobStore
from platform_core.obs.correlation import CORRELATION_FIELD
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.metrics import MetricsRegistry
from platform_core.obs.redaction import redact

#: The column the default representation must not carry.
PROTECTED_FIELD: Final = "error_detail"

#: The query value that asks for the protected-debug representation. Spelled out
#: rather than a boolean flag so that a log line saying which representation was
#: served reads the same as the request that asked for it.
PROTECTED: Final = "protected"

DEFAULT: Final = "default"

#: Reported by ``/health`` instead of the whole configuration. A health endpoint
#: that echoed settings would be the environment dump ``secret-setup.md``
#: prohibits, arriving by a different route.
HEALTHY: Final = "ok"

UNHEALTHY: Final = "unhealthy"

REACHABLE: Final = "reachable"

UNREACHABLE: Final = "unreachable"

#: The only state a safe retry may start from (CONTRACT-JOB@0.1, "Safe retry
#: starts from `FAILED` only").
RETRY_REQUIRES: Final = JobState.FAILED

#: How many jobs one page returns when the request does not say, and the most it
#: will return when it does. A bound rather than a preference: an unbounded list
#: over a table that only grows is a read whose cost nobody chose.
DEFAULT_PAGE: Final = 50

MAX_PAGE: Final = 200

#: How many correlated events one query returns at most, for the same reason.
DEFAULT_EVENT_LIMIT: Final = 500

MAX_EVENT_LIMIT: Final = 5000

#: What ``/events`` answers when no log file was configured. Not an error in the
#: platform: it is a question this deployment cannot answer, and saying which
#: setting would make it answerable is the whole content of the reply.
NO_LOG_CONFIGURED: Final = (
    "no structured log file is configured, so events cannot be served; "
    "set COSMA_LOG_FILE to a .jsonl path both the worker and the API can reach"
)


def job_view(row: Mapping[str, Any]) -> dict[str, Any]:
    """The job representation. There is one: the job row holds no debug detail.

    The opaque payload is included, and is the reason this passes through
    ``redact``. P0-A never interprets a payload, so a value under a sensitive key
    is exactly the thing that would otherwise be echoed back verbatim.

    Two derived fields are added because OPS-001 question 5 — "is anything left to
    try?" — has to be answerable without the reader knowing the contract's
    arithmetic. They are derived from the row and carry no payload-derived value.
    """
    masked: dict[str, Any] = redact(dict(row))
    spent = int(row["attempt_count"])
    budget = int(row["max_attempts"])
    masked["attempts_remaining"] = max(budget - spent, 0)
    masked["attempt_budget_spent"] = spent >= budget
    return masked


def attempt_view(row: Mapping[str, Any], protected: bool) -> dict[str, Any]:
    """One attempt, in the default or the protected-debug representation.

    ``error_detail_present`` is in both. Its absence would leave an operator
    looking at the default representation unable to tell "there is no detail" from
    "there is detail you are not being shown", and the second is the case where
    asking for the protected representation is worth doing. A boolean carries no
    payload-derived value.

    ``error_class_retryable`` is here because OPS-001 requires two facts that are
    easy to collapse into one: in the retry-exhaustion case the error *class* is
    retryable while the *job* is not, because its budget is spent. The class's half
    of that belongs to the attempt and the job's half to ``job_view``, and an
    operator who has to remember which classes are retryable has been told neither.
    """
    fields = dict(row)
    detail = fields.pop(PROTECTED_FIELD, None)
    view: dict[str, Any] = redact(fields)
    view["error_detail_present"] = detail is not None
    view["error_class_retryable"] = _class_is_retryable(fields.get("error_class"))
    if protected:
        view[PROTECTED_FIELD] = redact(detail)
    return view


def event_view(record: Mapping[str, Any]) -> dict[str, Any]:
    """One structured event as an API response may carry it.

    The same two rules as ``attempt_view``, for the same reason. SEC-004's boundary
    is about the API, not about one endpoint of it, so serving the log must not
    become a second route to what the attempt representation withholds — even
    though the platform never writes ``error_detail`` into a log line, and
    therefore even though the pop below is expected to find nothing.
    """
    fields = dict(record)
    detail = fields.pop(PROTECTED_FIELD, None)
    view: dict[str, Any] = redact(fields)
    if detail is not None:
        view["error_detail_present"] = True
    return view


def _class_is_retryable(error_class: object) -> bool | None:
    """Whether the contract permits retrying this class. ``None`` if there is none.

    An unrecognised value also reads as ``None``: the column is ``text`` with no
    CHECK, so a class this build does not know about is possible, and answering
    "not retryable" for it would be a claim the platform cannot support.
    """
    if not isinstance(error_class, str):
        return None
    try:
        known = ErrorClass(error_class)
    except ValueError:
        return None
    return known.retryable


def correlated_events(path: Path, correlation_id: str, limit: int) -> list[dict[str, Any]]:
    """Every event in the log carrying ``correlation_id``, oldest first, bounded.

    The file is read a line at a time and only matching lines are kept, so the
    memory cost is the answer rather than the log. A line that is not JSON, or is
    JSON that is not an object, is skipped: a process that died mid-write leaves a
    partial line, and the operator's problem is the events that are there.
    """
    found: list[dict[str, Any]] = []
    for record in _records(path):
        if record.get(CORRELATION_FIELD) != correlation_id:
            continue
        found.append(event_view(record))
        if len(found) >= limit:
            break
    return found


def _records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                yield parsed


def create_app(
    config: PlatformConfig,
    logger: StructuredLogger,
    metrics: MetricsRegistry | None = None,
    extend: Callable[[FastAPI], None] | None = None,
) -> FastAPI:
    """Build the operator API over ``config``.

    The interactive documentation and schema endpoints are switched off. They are
    harmless on a loopback binding, but the smallest surface is the one whose
    contents can be listed from the scenario that reads it, and no scenario reads
    them.
    """
    registry = MetricsRegistry() if metrics is None else metrics
    app = FastAPI(
        title="Cosmai P0-A operator API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def store_for(handle: Any) -> JobStore:
        return JobStore(handle, config, logger=logger, metrics=registry)

    def job_or_404(job_id: UUID) -> dict[str, Any]:
        with connected(config, autocommit=True) as handle:
            row = store_for(handle).read_job(job_id)
        return _found(job_id, row)

    def _absent(job_id: UUID) -> HTTPException:
        """A missing job is 404, never an empty success.

        OPS-001 asks for this by name: an operator has to be able to tell a wrong
        identifier from a job with no history, and an empty 200 says both.
        """
        return HTTPException(status_code=404, detail=f"no job with id {job_id}")

    def _found(job_id: UUID, row: dict[str, Any] | None) -> dict[str, Any]:
        if row is None:
            raise _absent(job_id)
        return row

    # ----------------------------------------------------------------- health

    @app.get("/health")
    def health() -> JSONResponse:
        """Whether the *platform* can do the one thing every other endpoint needs.

        OPS-004. A check that only reported that this process was up would answer a
        question the caller already knows the answer to, so this opens a connection
        and reads the platform schema. Failure is reported as the platform's own
        classified error, which is the same shape a worker would report, and it
        names the database — "the database is unreachable" is actionable and
        "internal error" is not.

        Nothing here is cached, so recovery needs no restart: the next request
        opens the next connection. The queue depth is included because OPS-004
        step 5 requires a queue nobody is working on not to read as identical to an
        empty queue — P0-A defines no worker liveness expectation, so a `PENDING`
        job with no worker is a healthy platform an operator should still see.
        """
        try:
            with connected(config, autocommit=True) as handle:
                queued = store_for(handle).count_by_state()
        except PlatformError as failure:
            logger.error(
                "api.health_failed",
                database=config.db_name,
                error_class=failure.error_class.value,
                error_summary=failure.summary,
            )
            return JSONResponse(
                status_code=503,
                content=jsonable_encoder(
                    {
                        "status": UNHEALTHY,
                        "database": UNREACHABLE,
                        "database_name": config.db_name,
                        **failure.operator_view(),
                    }
                ),
            )
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "status": HEALTHY,
                    "database": REACHABLE,
                    "database_name": config.db_name,
                    "log_level": config.log_level,
                    "jobs_by_state": queued,
                }
            )
        )

    # ---------------------------------------------------------------- metrics

    @app.get("/metrics")
    def read_metrics() -> JSONResponse:
        """This process's counters and durations, as CONTRACT-JOB@0.1 lists them.

        OPS-004. ``scope`` and ``pid`` are in the response because the reading is
        per process and in memory: a worker's counters live and die with that
        worker, and an operator handed a number with no owner would read this as a
        fleet-wide view. That gap is the scenario's recorded limitation, and saying
        whose counters these are is the least that keeps it visible.

        Every label in the reading is a job state from ``jobs.state``. SEC-004
        requires that no metric label carry a payload-derived value, and
        ``MetricsRegistry`` refuses any other label, so there is nothing to filter
        here.
        """
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "scope": "this API process only",
                    "pid": os.getpid(),
                    "metrics": registry.read().as_dict(),
                }
            )
        )

    # ------------------------------------------------------------------- jobs

    @app.get("/jobs")
    def list_jobs(
        state: JobState | None = None,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = DEFAULT_PAGE,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> JSONResponse:
        """A page of jobs, newest first. The path OPS-001 takes to find a failure.

        ``state`` is typed as ``JobState``, so an unknown state is a 422 rather than
        a filter that silently matched nothing — the difference between "there are
        no failures" and "you asked for a state that does not exist" is the whole
        value of the answer.
        """
        with connected(config, autocommit=True) as handle:
            store = store_for(handle)
            rows = store.list_jobs(state=state, limit=limit, offset=offset)
            matched = store.count_jobs(state=state)
        logger.info(
            "api.jobs_listed",
            state=None if state is None else state.value,
            limit=limit,
            offset=offset,
            returned=len(rows),
            matched=matched,
        )
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "state": None if state is None else state.value,
                    "limit": limit,
                    "offset": offset,
                    "returned": len(rows),
                    "matched": matched,
                    "jobs": [job_view(row) for row in rows],
                }
            )
        )

    @app.get("/jobs/{job_id}")
    def read_job(job_id: UUID) -> JSONResponse:
        """One job: what ran, with which input, when it was created, and where it ended.

        OPS-001 questions 1, 2, 3 and 5. Question 4's summary and question 6's
        withholding flag belong to the attempt, and question 3's per-attempt
        timings do too, so ``/attempts`` completes the set.
        """
        row = job_or_404(job_id)
        logger.info(
            "api.job_read",
            job_id=str(job_id),
            correlation_id=str(row["correlation_id"]),
            representation=DEFAULT,
        )
        return JSONResponse(content=jsonable_encoder(job_view(row)))

    @app.get("/jobs/{job_id}/attempts")
    def read_attempts(job_id: UUID, debug: Literal["protected"] | None = None) -> JSONResponse:
        """Every attempt of one job. ``?debug=protected`` adds ``error_detail``.

        OPS-001 questions 3, 4 and 6. ``Literal`` rather than a free string, so an
        unrecognised value is a 422 instead of being read as "not protected". A typo
        that silently downgraded the request would be the harmless direction here,
        but the same shape used for anything else would not be, and one rule is
        easier to keep.
        """
        row = job_or_404(job_id)
        protected = debug == PROTECTED
        with connected(config, autocommit=True) as handle:
            attempts = store_for(handle).read_attempts(job_id)
        representation = PROTECTED if protected else DEFAULT
        logger.info(
            "api.attempts_read",
            job_id=str(job_id),
            correlation_id=str(row["correlation_id"]),
            representation=representation,
            attempt_count=len(attempts),
        )
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "job_id": str(job_id),
                    "correlation_id": str(row["correlation_id"]),
                    "representation": representation,
                    "attempts": [attempt_view(attempt, protected) for attempt in attempts],
                }
            )
        )

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: UUID) -> JSONResponse:
        """The operator's safe retry: ``FAILED → PENDING``, and nothing else.

        OPS-002. The refusal is the substance of the endpoint rather than its edge
        case. It carries the state the job was in and the state a retry requires,
        because an operator told only that the request was bad learns nothing about
        what to do instead — and both are logged, because a refusal that logs
        nothing leaves nobody able to explain afterwards why the button did nothing.

        One connection for the whole request, so the state that is reported is read
        from the same session that attempted the write. The statement itself is
        still what decides: it carries ``state = 'FAILED'``, so a job that changed
        between the read and the update is refused by the database rather than by
        the check above it. In that narrow case the reported state is the one that
        was read, which is the closest true thing this process saw.

        A retry on an identity that does not exist is logged too, with no state
        rather than a wrong one. It is the same operator action as the other two
        refusals, and leaving it out of the log would leave the one case where the
        operator was looking at a stale list unexplainable afterwards.
        """
        with connected(config, autocommit=True) as handle:
            store = store_for(handle)
            row = store.read_job(job_id)
            if row is None:
                logger.warning(
                    "api.retry_refused",
                    job_id=str(job_id),
                    current_state=None,
                    required_state=RETRY_REQUIRES.value,
                    reason=f"no job with id {job_id}",
                )
                raise _absent(job_id)
            previous = JobState(row["state"])
            correlation_id = str(row["correlation_id"])
            accepted = store.request_retry(job_id)
            refreshed = store.read_job(job_id) if accepted else None

        if not accepted:
            reason = (
                f"this job is {previous.value}; "
                f"a safe retry starts from {RETRY_REQUIRES.value}"
            )
            logger.warning(
                "api.retry_refused",
                job_id=str(job_id),
                correlation_id=correlation_id,
                current_state=previous.value,
                required_state=RETRY_REQUIRES.value,
                reason=reason,
            )
            return JSONResponse(
                status_code=409,
                content=jsonable_encoder(
                    {
                        "job_id": str(job_id),
                        "correlation_id": correlation_id,
                        "accepted": False,
                        "current_state": previous.value,
                        "required_state": RETRY_REQUIRES.value,
                        "reason": reason,
                    }
                ),
            )

        assert refreshed is not None, "an accepted retry leaves the job it updated"
        # ``from_state``/``to_state`` rather than the refusal's ``current_state``,
        # matching ``job.transition``: on this path the state the operator saw is
        # already stale by the time the line is written, and calling it "current"
        # would make the accepted and refused events read as the same shape when
        # they are not.
        logger.info(
            "api.retry_accepted",
            job_id=str(job_id),
            correlation_id=correlation_id,
            from_state=previous.value,
            to_state=str(refreshed["state"]),
        )
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "job_id": str(job_id),
                    "correlation_id": correlation_id,
                    "accepted": True,
                    "previous_state": previous.value,
                    "current_state": str(refreshed["state"]),
                    "job": job_view(refreshed),
                }
            )
        )

    # ----------------------------------------------------------------- events

    @app.get("/events")
    def read_events(
        correlation_id: str,
        limit: Annotated[int, Query(ge=1, le=MAX_EVENT_LIMIT)] = DEFAULT_EVENT_LIMIT,
    ) -> JSONResponse:
        """Every structured event carrying one correlation identifier.

        OPS-003. One handle, and only one: the query takes no process identity, no
        time range and no attempt number, because the claim under test is that a
        single identifier reconstructs a history that crosses a process boundary.

        The identifier is the only thing the request supplies. The file it is
        searched in is ``COSMA_LOG_FILE``, resolved at startup, so this cannot
        become a way to read an arbitrary path — the same rule the data-handling
        convention states for outbound requests, applied to a local read.
        """
        if config.log_file is None:
            logger.warning("api.events_unavailable", reason=NO_LOG_CONFIGURED)
            return JSONResponse(
                status_code=503,
                content=jsonable_encoder({"status": "unavailable", "reason": NO_LOG_CONFIGURED}),
            )
        try:
            events = correlated_events(config.log_file, correlation_id, limit)
        except OSError as unreadable:
            # The path was validated at startup and the file is created by the
            # first event, so "not there yet" is the ordinary case: no process has
            # logged anything. It is an empty history, not a failure.
            logger.warning(
                "api.events_unreadable",
                correlation_id=correlation_id,
                error_summary=str(unreadable),
            )
            events = []
        logger.info("api.events_read", correlation_id=correlation_id, returned=len(events))
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "correlation_id": correlation_id,
                    "limit": limit,
                    "returned": len(events),
                    "events": events,
                }
            )
        )

    if extend is not None:
        # The seam, and the whole of what this module knows about anything beyond the
        # platform. DP-008 D1 forbids `platform_core` from importing the add-on layer at
        # all, so a domain surface cannot be defined here — and OQ-005 H1's rule that a
        # fourth kind of navigable object must be *named* rather than added quietly is
        # honoured by that surface living in `addon_host.api`, where it is named.
        #
        # It runs last, so a domain route cannot shadow a platform one: FastAPI matches in
        # registration order, and every path above is already bound.
        extend(app)
    return app
