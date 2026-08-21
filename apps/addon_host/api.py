"""The host's addition to the domain surface: `POST /sources/{id}/collect` and `/import`.

M2-RECORD's `domain/api.py` docstring named the decision this module makes and asked M3
to make it: **reuse**, not relocate. P0 put the whole domain surface in
`addon_host/api.py` because that was the one P0 package allowed to import `domain`,
`platform_core`, and `addon_api` together; M2 found that nothing in the domain routes
actually needs `addon_api` — no route dispatches to an add-on's own code — and placed
them at `domain.api` instead, a direction `tests/environment/test_addon_layer_direction.py`
already permits. Nothing about that finding changed in this batch, and moving 400+ lines of
working, tested routes to satisfy a placement convention that was itself provisional would
be churn for its own sake. So this module **reuses** `domain.api.extend_with_domain` for
everything M2 already built, and adds only the two routes M2 deferred pending the add-on
dispatch this batch supplies: `collect` and `import`. `docs/p1/M2-RECORD.md`'s `(d)` section
is the deferral record this satisfies; `apps/domain/api.py`'s own module docstring is updated
alongside this file to record that the decision was made, so a reader following either
document finds the other.

**Why these two and not the rest.** Every other domain route (`GET /sources`, the raw
browser, the credential write, `POST .../snapshots`, `POST .../normalize`, `GET
.../results`) reads or writes `domain` tables directly and dispatches to no add-on code —
`domain.api` already builds all of them correctly, M3 or not. `collect` and `import` are
different: both create a job whose `handler` is `f"{HANDLER_PREFIX}{addon_id}"`, and that
dispatch convention lives in `addon_host.registration` — nothing before this batch
registered a handler for that prefix, so M2 declined to build a route that would insert a
job nothing could ever claim. `addon_host.registration` exists now, so the two routes are
real.

**Every write still takes an identifier, never a location** (`p0-security.md`), exactly as
`domain.api`'s own docstring states — these two routes take no body at all, which is the
same rule expressed as a signature: there is no parameter here that could become a URL.

**A connection per request**, for the reason `domain.api` and `platform_core.api.app` both
give: nothing is cached across requests, so a database that went away and came back needs
no restart.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from addon_host.registration import HANDLER_PREFIX
from domain.api import extend_with_domain as extend_with_domain_routes
from domain.store import DomainStore
from platform_core.config import PlatformConfig
from platform_core.db.connection import connect
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger

__all__ = ["extend_with_domain"]

#: What a collect or import job carries, and the whole of it. Mirrors
#: `addon_host.capabilities.SOURCE_ID_FIELD` and `domain.api.SOURCE_ID_FIELD` rather than
#: importing either — a payload key is a contract between this surface and the capability
#: layer, and all three spell it out.
SOURCE_ID_FIELD = "source_id"

#: A collect or import job's attempt budget. Three, matching every other job this platform
#: creates: a transient network failure is the case the budget exists for.
MAX_ATTEMPTS = 3


def extend_with_domain(
    config: PlatformConfig, logger: StructuredLogger
) -> Callable[[FastAPI], None]:
    """Return the `extend` callable `platform_core.api.app.create_app` takes.

    Composes `domain.api.extend_with_domain` (every route M2 built) with the two routes
    the add-on dispatch layer makes possible. `domain`'s own `extend` runs first, so a
    request for one of its routes is served identically to `python -m platform_core.api`
    with `domain`'s surface alone — this module only ever adds routes, never replaces one.
    """
    domain_extend = extend_with_domain_routes(config, logger)

    def extend(app: FastAPI) -> None:
        domain_extend(app)
        _register_addon_routes(app, config, logger)

    return extend


def _register_addon_routes(app: FastAPI, config: PlatformConfig, logger: StructuredLogger) -> None:
    def source_or_404(source_id: str) -> dict[str, Any]:
        with connect(config, autocommit=True) as handle:
            row = DomainStore(handle).read_source(source_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no source named {source_id!r}")
        return row

    def require_kind(source: dict[str, Any], *kinds: str) -> dict[str, Any]:
        """Refuse with the kind it *is*, because "wrong kind" is not actionable."""
        if source["kind"] not in kinds:
            wanted = " or a ".join(kinds)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"source {source['source_id']!r} is a {source['kind']} and this action "
                    f"needs a {wanted}"
                ),
            )
        if not source["enabled"]:
            raise HTTPException(
                status_code=409, detail=f"source {source['source_id']!r} is disabled"
            )
        return source

    @app.post("/sources/{source_id}/collect", status_code=201)
    def start_collection(source_id: str) -> JSONResponse:
        """Enqueue one collect job for this source.

        Takes no body. Everything about the request the collector will make is read from
        the row this identifier names, which is `p0-security.md`'s rule stated as a
        signature rather than as a validation step: there is no parameter here that could
        become a URL.
        """
        source = require_kind(source_or_404(source_id), "collector")
        with connect(config, autocommit=True) as handle:
            job_id = JobStore(handle, config, logger=logger).create_job(
                f"{HANDLER_PREFIX}{source['addon_id']}",
                {SOURCE_ID_FIELD: source_id},
                max_attempts=MAX_ATTEMPTS,
            )
        return JSONResponse({"job_id": str(job_id), "source_id": source_id}, status_code=201)

    @app.post("/sources/{source_id}/import", status_code=201)
    def start_import(source_id: str) -> JSONResponse:
        """Enqueue one import job for this source.

        The dataset half of `/collect`, and the same shape for the same reason: no body,
        and nothing here that could become a path. DP-024 puts the root and the member list
        on the operator-approved `input_profile`, so this identifier selects a grant rather
        than naming a file — `domain.inputs.resolve_input` is what turns the add-on's input
        name into an approved path, and it never sees one from here.
        """
        source = require_kind(source_or_404(source_id), "importer")
        with connect(config, autocommit=True) as handle:
            job_id = JobStore(handle, config, logger=logger).create_job(
                f"{HANDLER_PREFIX}{source['addon_id']}",
                {SOURCE_ID_FIELD: source_id},
                max_attempts=MAX_ATTEMPTS,
            )
        return JSONResponse({"job_id": str(job_id), "source_id": source_id}, status_code=201)
