"""The operator's domain surface: sources, collection, snapshots, normalization, results.

`platform_core.api.app` navigates three kinds of thing — platform health, jobs, attempts —
and its own docstring is explicit that a fourth would refute OQ-005 H1 and has to be
**named** rather than added quietly. This module is that naming, and the four objects are:

| Object | Why it is not a job |
|---|---|
| source | A registered configuration. It exists before any job and outlives every one. |
| raw | What a collection produced. A job that succeeded says nothing about how much. |
| snapshot | A sealed input, verifiable long after the job that sealed it finished. |
| result | Versioned output. Two normalizer versions over one snapshot are two sets. |

`[추론]` So OQ-005 H1 — "platform health, jobs, and attempts are sufficient for every
required operator scenario" — is **refuted for P0-B**, and this file is the evidence rather
than a workaround. An operator restricted to jobs can see that a collection ran and not what
it collected, can see that a normalization succeeded and not what it produced, and cannot
seal a snapshot at all. That belongs in the record, and it is recorded here rather than
absorbed silently into the platform's own surface.

**Why the routes are here and not there.** DP-008 D1: `platform_core` may import nothing
local, enforced by `tests/environment/test_addon_layer_direction.py`. The platform's
`create_app` gained one source-neutral seam — `extend`, a callable handed the app — and this
is what fills it. The same split `RegistryFor` and `addon_host.worker` make for the worker.

**Every write takes an identifier, never a location.** `p0-security.md`: "operator input
selects a registered `source_id`; it must not turn an arbitrary URL into an outbound
request." No route below accepts a host, a path, a URL, a header name, or a credential.
A request body that carries one is ignored rather than merged — there is no code path from
an HTTP request to an `outbound_profile`, and registration is deliberately not an endpoint.

**A connection per request**, for the reason `platform_core.api.app` gives: nothing is
cached across requests, so a database that went away and came back needs no restart.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from domain.store import DomainStore
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from platform_core.config import PlatformConfig
from platform_core.db.connection import connected
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.redaction import redact_mapping

from addon_host.registration import HANDLER_PREFIX

__all__ = ["extend_with_domain"]

#: What a collect job carries, and the whole of it. Mirrors
#: `addon_host.capabilities.SOURCE_ID_FIELD` rather than importing it, because a payload key
#: is a contract between this surface and that layer and both spell it out.
SOURCE_ID_FIELD = "source_id"
SNAPSHOT_ID_FIELD = "snapshot_id"

#: FastAPI's "an absent body is an empty object" marker, as a module-level singleton
#: because calling `Body(...)` in a default argument evaluates once at import and reads as
#: though it evaluated per call (ruff B008). The default matters: a normalize request with
#: no body must reach the 422 that names the missing `source_id`, not a 400 that says only
#: that something was wrong.
_OPTIONAL_BODY: Any = Body(default_factory=dict)

#: A collect job's attempt budget. Three, like every other P0 job: a transient network
#: failure is the case the budget exists for, and this is the source of most of them.
MAX_ATTEMPTS = 3


def extend_with_domain(
    config: PlatformConfig, logger: StructuredLogger
) -> Callable[[FastAPI], None]:
    """Return the `extend` callable `platform_core.api.create_app` takes."""

    def extend(app: FastAPI) -> None:
        _register(app, config, logger)

    return extend


def _register(app: FastAPI, config: PlatformConfig, logger: StructuredLogger) -> None:
    def source_or_404(source_id: str) -> dict[str, Any]:
        with connected(config, autocommit=True) as handle:
            row = DomainStore(handle).read_source(source_id)
        if row is None:
            # 404 and never an empty success, for the reason OPS-001 gives about jobs: an
            # operator has to be able to tell a wrong identifier from a source with no
            # history, and an empty 200 says both.
            raise HTTPException(status_code=404, detail=f"no source named {source_id!r}")
        return row

    def require_kind(source: dict[str, Any], kind: str) -> dict[str, Any]:
        """Refuse with the kind it *is*, because "wrong kind" is not actionable."""
        if source["kind"] != kind:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"source {source['source_id']!r} is a {source['kind']} and this action "
                    f"needs a {kind}"
                ),
            )
        if not source["enabled"]:
            raise HTTPException(
                status_code=409, detail=f"source {source['source_id']!r} is disabled"
            )
        return source

    def snapshot_or_404(snapshot_id: UUID) -> dict[str, Any]:
        with connected(config, autocommit=True) as handle:
            row = DomainStore(handle).read_snapshot(snapshot_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no snapshot with id {snapshot_id}")
        return row

    # ---------------------------------------------------------------- sources

    @app.get("/sources")
    def list_sources() -> JSONResponse:
        """Every registered source. The dashboard's entry point into the domain."""
        with connected(config, autocommit=True) as handle:
            rows = DomainStore(handle).list_sources()
        return JSONResponse({"sources": [source_view(row) for row in rows]})

    @app.get("/sources/{source_id}")
    def read_source(source_id: str) -> JSONResponse:
        return JSONResponse(source_view(source_or_404(source_id)))

    @app.get("/sources/{source_id}/raw")
    def read_raw(source_id: str) -> JSONResponse:
        """How much this source has collected, and when it last did.

        Counts rather than payloads. A page of Raw bodies is a page of unreviewed external
        text on an operator screen, and nothing in P0-B needs one to answer "did the
        collection do anything".
        """
        source_or_404(source_id)
        with connected(config, autocommit=True) as handle:
            store = DomainStore(handle)
            summary = store.raw_summary(source_id)
        return JSONResponse(summary)

    @app.post("/sources/{source_id}/collect", status_code=201)
    def start_collection(source_id: str) -> JSONResponse:
        """Enqueue one collect job for this source.

        Takes no body. Everything about the request the collector will make is read from
        the row this identifier names, which is `p0-security.md`'s rule stated as a
        signature rather than as a validation step: there is no parameter here that could
        become a URL.
        """
        source = require_kind(source_or_404(source_id), "collector")
        with connected(config, autocommit=True) as handle:
            job_id = JobStore(handle, config, logger=logger).create_job(
                f"{HANDLER_PREFIX}{source['addon_id']}",
                {SOURCE_ID_FIELD: source_id},
                max_attempts=MAX_ATTEMPTS,
            )
        return JSONResponse({"job_id": str(job_id), "source_id": source_id}, status_code=201)

    # -------------------------------------------------------------- snapshots

    @app.post("/sources/{source_id}/snapshots", status_code=201)
    def seal_snapshot(source_id: str) -> JSONResponse:
        """Materialize and seal every `raw_item` of this source (DP-019 D5).

        Synchronous rather than a job, because it is one statement over rows that are
        already local — there is no network, no add-on, and nothing to retry. `[결정]` If a
        snapshot ever becomes expensive enough to need a lease, it becomes a job and this
        endpoint returns its id instead; the shape of that change is why the response
        already names an identifier rather than a body.
        """
        require_kind(source_or_404(source_id), "collector")
        with connected(config, autocommit=True) as handle:
            store = DomainStore(handle)
            with handle.transaction():
                snapshot_id = store.seal_snapshot_from_raw(source_id)
            row = store.read_snapshot(snapshot_id)
        assert row is not None
        return JSONResponse(
            {"snapshot_id": str(snapshot_id), **snapshot_view(row, ())}, status_code=201
        )

    @app.get("/snapshots")
    def list_snapshots(source_id: str | None = None) -> JSONResponse:
        with connected(config, autocommit=True) as handle:
            store = DomainStore(handle)
            rows = store.list_snapshots(source_id)
            viewed = [
                snapshot_view(row, store.snapshot_tampering(row["id"])) for row in rows
            ]
        return JSONResponse({"snapshots": viewed})

    @app.get("/snapshots/{snapshot_id}")
    def read_snapshot(snapshot_id: UUID) -> JSONResponse:
        row = snapshot_or_404(snapshot_id)
        with connected(config, autocommit=True) as handle:
            problems = DomainStore(handle).snapshot_tampering(snapshot_id)
        return JSONResponse(snapshot_view(row, problems))

    @app.post("/snapshots/{snapshot_id}/normalize", status_code=201)
    def start_normalization(
        snapshot_id: UUID, body: dict[str, Any] = _OPTIONAL_BODY
    ) -> JSONResponse:
        """Enqueue one normalize job over this sealed snapshot.

        Two identifiers and nothing else: which sealed input, and which registered
        normalizer. `project-state.md` §4 and DP-019 D6 keep this an explicit operator act —
        collection never starts it — and that is why it is a separate endpoint rather than
        something `POST /collect` does when it finishes.
        """
        snapshot_or_404(snapshot_id)
        source_id = body.get(SOURCE_ID_FIELD)
        if not isinstance(source_id, str) or not source_id:
            raise HTTPException(
                status_code=422,
                detail=f"a normalize request must name a registered {SOURCE_ID_FIELD!r}",
            )
        source = require_kind(source_or_404(source_id), "normalizer")
        with connected(config, autocommit=True) as handle:
            job_id = JobStore(handle, config, logger=logger).create_job(
                f"{HANDLER_PREFIX}{source['addon_id']}",
                {SOURCE_ID_FIELD: source_id, SNAPSHOT_ID_FIELD: str(snapshot_id)},
                max_attempts=MAX_ATTEMPTS,
            )
        return JSONResponse(
            {"job_id": str(job_id), "snapshot_id": str(snapshot_id)}, status_code=201
        )

    @app.get("/snapshots/{snapshot_id}/results")
    def read_results(snapshot_id: UUID, addon_version: str | None = None) -> JSONResponse:
        """Every normalized result over this snapshot, all versions unless one is named.

        Unfiltered by default because coexistence is the point (DP-019 D3): a reader
        comparing two normalizer versions asks for both and narrows afterwards.
        """
        snapshot_or_404(snapshot_id)
        with connected(config, autocommit=True) as handle:
            rows = DomainStore(handle).read_results(snapshot_id, addon_version)
        return JSONResponse({"results": [result_view(row) for row in rows]})


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #


def source_view(row: dict[str, Any]) -> dict[str, Any]:
    """One source as an operator sees it: named fields, never the stored blob.

    `[측정]` The first version of this passed the whole `outbound_profile` through
    `redact_mapping`, and the redactor masked it — `credentials` is a key name that looks
    exactly like a secret, which is the redactor being right. The lesson generalises and is
    why the profile is now assembled field by field: a stored blob shipped whole is a blob
    whose *future* fields nobody decided to publish, and the choice between "the redactor
    ate a field an operator needs" and "a field nobody reviewed left the boundary" is a
    choice not to have to make.

    So `config` and the profile are built explicitly. The credential parts carry **key
    names** and never values — DP-018 D1, held by `_read_credentials` and by the
    `source_credential_ref_is_a_key_name` CHECK — and an operator needs to see those names
    to know which keys to put in the store, so they are shown deliberately rather than
    surviving by accident. `config` still goes through the redactor: `validate_config`
    refuses a `secret` field there, and this is the second boundary in case a row arrived
    by some path that did not.
    """
    profile = row["outbound_profile"] or {}
    return {
        "source_id": row["source_id"],
        "addon_id": row["addon_id"],
        "addon_version": row["addon_version"],
        "kind": row["kind"],
        "config": dict(redact_mapping(row["config"] or {})),
        "config_schema_version": row["config_schema_version"],
        "credential_ref": row["credential_ref"],
        "outbound_profile": None if not profile else profile_view(profile),
        "data_class": row["data_class"],
        "enabled": row["enabled"],
        "created_at": _instant(row["created_at"]),
        "updated_at": _instant(row["updated_at"]),
    }


def profile_view(profile: dict[str, Any]) -> dict[str, Any]:
    """The approved outbound policy, field by named field.

    Everything here is the operator's own grant read back to them: which hosts, which
    endpoints and by which method (DP-020 D1), which bounds, and which secret-store **keys**
    fill which headers (DP-018). A field this function does not name does not reach a
    response, which is the point.
    """
    endpoints = profile.get("endpoints") or {}
    return {
        "hosts": list(profile.get("hosts") or ()),
        "endpoints": {
            str(name): (
                {"path": str(entry.get("path", "")), "method": str(entry.get("method", "GET"))}
                if isinstance(entry, dict)
                else {"path": str(entry), "method": "GET"}
            )
            for name, entry in endpoints.items()
        },
        "port": profile.get("port", 443),
        "limits": dict(profile.get("limits") or {}),
        "allow_loopback": bool(profile.get("allow_loopback", False)),
        "credentials": [
            {"header": str(part.get("header", "")), "ref": str(part.get("ref", ""))}
            for part in (profile.get("credentials") or ())
        ],
    }


def snapshot_view(row: dict[str, Any], problems: tuple[str, ...]) -> dict[str, Any]:
    """One snapshot, with whether it still matches what was sealed.

    `verifies` is computed rather than stored. A dashboard that showed only "sealed" would
    make a tampered input look ready to run, and `snapshot_tampering` returns reasons rather
    than a boolean precisely because "the manifest digest differs" and "member 3 was edited"
    need different operator actions.
    """
    return {
        "snapshot_id": str(row["id"]),
        "source_id": row["source_id"],
        "item_count": row["item_count"],
        "manifest_sha256": row["manifest_sha256"],
        "selection": row["selection"],
        "sealed_at": _instant(row["sealed_at"]),
        "created_at": _instant(row["created_at"]),
        "verifies": not problems,
        "problems": list(problems),
    }


def result_view(row: dict[str, Any]) -> dict[str, Any]:
    """One normalized record, with the two version axes and the lineage key.

    `body` is external text a normalizer produced, so it goes through `redact_mapping` on
    the way out like everything else here. `[추론]` Schema 0.1 carries no credential-shaped
    field, so this masks nothing today — it is here so that a later schema field named like
    a token does not leave through this boundary unmasked.
    """
    return {
        "id": str(row["id"]),
        "snapshot_id": str(row["snapshot_id"]),
        "source_id": row["source_id"],
        "addon_id": row["addon_id"],
        "addon_version": row["addon_version"],
        "output_contract_version": row["output_contract_version"],
        "source_item_key": row["source_item_key"],
        "body": dict(redact_mapping(row["body"])),
        "body_sha256": row["body_sha256"],
        "notes": row["notes"],
        "created_at": _instant(row["created_at"]),
    }


def _instant(value: Any) -> str | None:
    return None if value is None else value.isoformat()
