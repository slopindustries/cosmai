"""The three read endpoints, and the two representations SEC-004 separates.

CONTRACT-JOB@0.1 says ``error_detail`` is never in an API response by default.
SEC-004 adds the half that is easy to lose: it *is* reachable, through an explicit
protected-debug representation available only on the loopback binding SEC-002
constrains, and **even there the redaction boundary holds**. Protected is about
who can ask, not about what is masked.

Three decisions shape this module.

**Redaction happens on the way out, again.** Every value written into
``job_attempt.error_detail`` was already redacted by ``ProtectedDetail`` on the way
in. Redacting once more here is not belt-and-braces for its own sake: this is the
boundary a response crosses, and a row written by anything other than
``ProtectedDetail`` — a migration, a fixture, a future writer — would otherwise
leave through it unmasked. ``redact`` is idempotent, so the second pass costs
nothing and removes the assumption.

**A connection per request.** The API holds no pool and no long-lived session. At
P0-A scale the cost is one connect per read, and what it buys is that no request
can observe another request's transaction state — which is the kind of thing that
would quietly invalidate an observation the `SEC` scenarios rest on.

**Nothing here writes.** Not a limitation to be lifted casually: an operator write
path is a state transition, and CONTRACT-JOB@0.1's transition table is what
decides which ones exist. ``JobStore.request_retry`` is the only one, and exposing
it belongs with the `OPS` scenarios that specify how an operator reaches it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.errors import PlatformError
from platform_core.jobs.store import JobStore
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


def job_view(row: Mapping[str, Any]) -> dict[str, Any]:
    """The job representation. There is one: the job row holds no debug detail.

    The opaque payload is included, and is the reason this passes through
    ``redact``. P0-A never interprets a payload, so a value under a sensitive key
    is exactly the thing that would otherwise be echoed back verbatim.
    """
    masked: dict[str, Any] = redact(dict(row))
    return masked


def attempt_view(row: Mapping[str, Any], protected: bool) -> dict[str, Any]:
    """One attempt, in the default or the protected-debug representation.

    ``error_detail_present`` is in both. Its absence would leave an operator
    looking at the default representation unable to tell "there is no detail" from
    "there is detail you are not being shown", and the second is the case where
    asking for the protected representation is worth doing. A boolean carries no
    payload-derived value.
    """
    fields = dict(row)
    detail = fields.pop(PROTECTED_FIELD, None)
    view: dict[str, Any] = redact(fields)
    view["error_detail_present"] = detail is not None
    if protected:
        view[PROTECTED_FIELD] = redact(detail)
    return view


def create_app(
    config: PlatformConfig,
    logger: StructuredLogger,
    metrics: MetricsRegistry | None = None,
) -> FastAPI:
    """Build the operator API over ``config``.

    The interactive documentation and schema endpoints are switched off. They are
    harmless on a loopback binding, but the smallest surface is the one whose
    contents can be listed from the scenario that reads it, and no scenario reads
    them.
    """
    registry = MetricsRegistry() if metrics is None else metrics
    app = FastAPI(
        title="CosmaSignal P0-A operator API",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    def store_for(handle: Any) -> JobStore:
        return JobStore(handle, config, logger=logger, metrics=registry)

    def job_or_404(job_id: UUID) -> dict[str, Any]:
        with connected(config, autocommit=True) as handle:
            row = store_for(handle).read_job(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no job with id {job_id}")
        return row

    @app.get("/health")
    def health() -> JSONResponse:
        """Whether the platform can do the one thing every other endpoint needs.

        A health check that only reported that the process was up would answer a
        question the caller already knows the answer to, so this opens a
        connection. Failure is reported as the platform's own classified error,
        which is the same shape a worker would report.
        """
        try:
            with connected(config, autocommit=True) as handle:
                handle.execute("select 1")
        except PlatformError as failure:
            logger.error(
                "api.health_failed",
                error_class=failure.error_class.value,
                error_summary=failure.summary,
            )
            return JSONResponse(
                status_code=503,
                content=jsonable_encoder(failure.operator_view()),
            )
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "status": HEALTHY,
                    "database": "reachable",
                    "log_level": config.log_level,
                }
            )
        )

    @app.get("/jobs/{job_id}")
    def read_job(job_id: UUID) -> JSONResponse:
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

        ``Literal`` rather than a free string, so an unrecognised value is a 422
        instead of being read as "not protected". A typo that silently downgraded
        the request would be the harmless direction here, but the same shape used
        for anything else would not be, and one rule is easier to keep.
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

    return app
