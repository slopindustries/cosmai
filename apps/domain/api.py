"""The operator's domain surface: sources, raw browsing, snapshots, results, credentials.

Copy-adapted from ``experiments/integrated-p0/addon_host/api.py`` (M2 batch 2d), with one
structural difference this module's own placement forces, and one scope narrowing this
batch made deliberately.

**Placement.** P0 put this module in ``addon_host``, one layer above ``domain``, because
``addon_host`` is the only P0 package allowed to import ``domain``, ``platform_core``, *and*
``addon_api`` together — the layer that translates between the add-on contract and Raw
persistence. Nothing here needs ``addon_api`` at all: every route below reads or writes
``domain`` tables directly, through ``platform_core``'s connection and job store, and
none of them dispatch to an add-on's own code. So this module lives at ``domain.api``
instead — ``domain`` importing ``platform_core`` is the direction
``tests/environment/test_addon_layer_direction.py`` already permits, and no new layer had
to be invented to hold it. **This placement is provisional and named as such in
``docs/p1/M2-RECORD.md``**: M3 builds ``addon_host`` and must decide whether to import
``extend_with_domain`` from here and wrap it with the addon-dispatched routes, or move this
module's routes into ``addon_host.api`` outright and retire this one. Either is a small
change; nothing downstream should assume this file's location survives M3.

**Scope narrowing.** P0's surface had seven writes: register (not an endpoint, per its own
docstring), collect, import, seal, normalize, and (added by this batch) a credential write.
``POST /sources/{id}/collect`` and ``POST /sources/{id}/import`` are **not** reproduced here.
Both would create a job whose handler names ``addon:<addon_id>`` — a dispatch convention
that lives in ``addon_host.registration`` (P0) and has no P1 equivalent yet: nothing in this
tree registers a handler for that prefix, so such a job would sit ``PENDING`` forever with no
worker able to claim it in a way that does anything. Creating a job nothing can ever process
is not a smaller version of the feature; it is a route that looks like it works and does not.
``docs/p1/M2-RECORD.md`` names this split and the M3 batch that closes it.
``POST /snapshots/{id}/normalize`` **is** reproduced, per this batch's brief, even though it
shares the same eventual-dispatch dependency — the job it creates is equally unprocessable
until M3 registers ``addon:*`` handlers. That inconsistency is deliberate scope from the
batch brief rather than an oversight on this module's part, and is recorded rather than
smoothed over in ``docs/p1/M2-RECORD.md``.

**Every write still takes an identifier, never a location.** ``p0-security.md``: operator
input selects a registered ``source_id``; it must not turn an arbitrary URL into an
outbound request. No route below accepts a host, a path, a URL, or a header name. The one
route that accepts something resembling a secret — the credential write — accepts a
*value* deliberately (DP-034 D1) and never returns, logs, or stores it anywhere but the
secret store ``platform_core.secrets.write_credential`` already validates the location of.

**A connection per request**, for the reason ``platform_core.api.app`` gives: nothing is
cached across requests, so a database that went away and came back needs no restart.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Body, FastAPI, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from domain.store import DomainStore
from platform_core.config import PlatformConfig
from platform_core.db.connection import connect
from platform_core.errors import ConfigurationInvalidError
from platform_core.jobs.store import JobStore
from platform_core.obs.logging import StructuredLogger
from platform_core.obs.redaction import redact_mapping
from platform_core.secrets import CREDENTIAL_REF_PATTERN, write_credential

__all__ = ["extend_with_domain"]

#: What a normalize job carries, and the whole of it. Mirrors what M3's capability layer
#: will read rather than importing it — a payload key is a contract between this surface
#: and that layer and both spell it out, the same reasoning P0's own module gave.
SOURCE_ID_FIELD = "source_id"
SNAPSHOT_ID_FIELD = "snapshot_id"

#: The addon-dispatch handler prefix CONTRACT-JOB@0.1's job-handler naming convention
#: fixes and ``addon_host.registration.HANDLER_PREFIX`` will define for real in M3.
#: Mirrored here, not imported — ``addon_host`` does not exist in this tree yet. **M3 must
#: keep this string in sync with its own** (or supersede this module outright; see this
#: module's docstring); a mismatch would mean a job this route creates is never claimed by
#: the handler M3 registers.
HANDLER_PREFIX = "addon:"

#: A normalize job's attempt budget. Three, matching every other P0 job: a transient
#: failure is the case the budget exists for.
MAX_ATTEMPTS = 3

#: FastAPI's "an absent body is an empty object" marker, as a module-level singleton
#: because calling ``Body(...)`` in a default argument evaluates once at import and reads
#: as though it evaluated per call (ruff B008).
_OPTIONAL_BODY: Any = Body(default_factory=dict)

#: The credential write's body marker, for the same reason — required rather than
#: optional (``Body(...)``), so a request with no body at all reaches the 422 that names
#: the missing fields instead of a 400 that only says something was wrong.
_REQUIRED_BODY: Any = Body(...)

#: How many raw items one page of the data browser returns when the request does not say,
#: and the most it will return when it does. `platform_core.api.app`'s job-listing bound,
#: for the same reason: an unbounded read over a table that only grows is a cost nobody
#: chose.
DEFAULT_PAGE = 50
MAX_PAGE = 200

#: A credential's ``purpose`` must look like an identifier segment before it becomes part
#: of a ref: non-empty, starting with a letter, and free of anything that is not itself a
#: letter, digit, underscore, or hyphen. Refusing a purpose this loosely-shaped one catches
#: an obviously wrong request (an empty string, a stray URL) at the boundary instead of
#: silently folding every character `CREDENTIAL_REF_PATTERN` forbids into an underscore.
_PURPOSE_SHAPE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")

#: Everything a `CREDENTIAL_REF_PATTERN` ref may not contain, once `source_id`/`purpose`
#: are uppercased. Collapsed to one underscore per run, so `"naver-blog"` becomes
#: `NAVER_BLOG` rather than `NAVER__BLOG`.
_NOT_REF_CHARS = re.compile(r"[^A-Z0-9]+")


def credential_ref_for(source_id: str, purpose: str) -> str:
    """Derive the `COSMA_SRC_<SOURCE_ID>_<PURPOSE>` ref a credential write uses.

    `secret-setup.md`'s naming convention, applied to operator-supplied text rather than
    to a value already known to be identifier-shaped: `source_id` is a free-text primary
    key (`apps/platform_core/db/migrations/0002_domain.sql`'s `source` table states no
    format CHECK on it beyond non-empty), so a hyphen or a space is ordinary input and not
    a caller error. Both segments are uppercased and every run of non-`[A-Z0-9]` characters
    becomes one underscore, then the result is checked against
    `platform_core.secrets.CREDENTIAL_REF_PATTERN` — the same pattern `resolve_credential`
    and the `source_credential_ref_is_a_key_name` CHECK already hold every ref to, so a ref
    this function builds can never be one the rest of the platform would refuse.
    """
    id_part = _NOT_REF_CHARS.sub("_", source_id.upper()).strip("_")
    purpose_part = _NOT_REF_CHARS.sub("_", purpose.upper()).strip("_")
    return f"COSMA_SRC_{id_part}_{purpose_part}"


def extend_with_domain(
    config: PlatformConfig, logger: StructuredLogger
) -> Callable[[FastAPI], None]:
    """Return the `extend` callable `platform_core.api.app.create_app` takes."""

    def extend(app: FastAPI) -> None:
        _register(app, config, logger)

    return extend


def _register(app: FastAPI, config: PlatformConfig, logger: StructuredLogger) -> None:
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

    def snapshot_or_404(snapshot_id: UUID) -> dict[str, Any]:
        with connect(config, autocommit=True) as handle:
            row = DomainStore(handle).read_snapshot(snapshot_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"no snapshot with id {snapshot_id}")
        return row

    # ---------------------------------------------------------------- sources

    @app.get("/sources")
    def list_sources() -> JSONResponse:
        """Every registered source. The dashboard's entry point into the domain."""
        with connect(config, autocommit=True) as handle:
            rows = DomainStore(handle).list_sources()
        return JSONResponse({"sources": [source_view(row) for row in rows]})

    @app.get("/sources/{source_id}")
    def read_source(source_id: str) -> JSONResponse:
        return JSONResponse(source_view(source_or_404(source_id)))

    @app.get("/sources/{source_id}/raw")
    def read_raw(source_id: str) -> JSONResponse:
        """How much this source has collected, and when it last did. Counts, not payloads."""
        source_or_404(source_id)
        with connect(config, autocommit=True) as handle:
            summary = DomainStore(handle).raw_summary(source_id)
        return JSONResponse(summary)

    @app.get("/sources/{source_id}/raw/items")
    def read_raw_items(
        source_id: str,
        offset: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=MAX_PAGE)] = DEFAULT_PAGE,
    ) -> JSONResponse:
        """A page of this source's raw items, for the data-browser screen (DP-033 D1/D2).

        `payload` comes back as plain text — decoded UTF-8, with anything that cannot
        decode replaced rather than rejected, since JSON has no way to carry a byte a
        payload's own encoding does not agree with. DP-033 D2's own text is explicit
        about what this is *not*: no body-level redaction exists anywhere in this
        platform, so this is a page of unreviewed external text, rendered as text and
        nothing else — never as interpreted markup. That rendering rule is the
        dashboard's (M5) to hold; this route's only obligation is to hand back text
        and no rendering instruction of any kind.
        """
        source_or_404(source_id)
        with connect(config, autocommit=True) as handle:
            rows = DomainStore(handle).list_items(source_id, offset, limit)
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "source_id": source_id,
                    "offset": offset,
                    "limit": limit,
                    "returned": len(rows),
                    "items": [raw_item_view(row) for row in rows],
                }
            )
        )

    # ---------------------------------------------------------------- schedule

    @app.get("/sources/{source_id}/schedule")
    def read_schedule(source_id: str) -> JSONResponse:
        """This source's recurring-collection schedule, or an unset one (DP-033 D5).

        No schedule row is not an error: most sources never get one. `enabled`
        reads `false` and every timestamp reads `null` on an unset schedule, the
        same shape a `PUT` that then disables it would leave — a caller does not
        have to special-case "never configured" against "configured, disabled".
        """
        source_or_404(source_id)
        with connect(config, autocommit=True) as handle:
            row = DomainStore(handle).read_schedule(source_id)
        return JSONResponse(schedule_view(source_id, row))

    @app.put("/sources/{source_id}/schedule")
    def write_schedule(source_id: str, body: dict[str, Any] = _REQUIRED_BODY) -> JSONResponse:
        """Create or replace this source's schedule; upserts, per the plan's own
        `GET|PUT /sources/{id}/schedule` shape (DP-033 D5; `apps/scheduler`
        polls what this writes).

        Restricted to a `collector` source: D5's own text is "collection runs on
        a schedule; normalization stays operator-triggered, with an optional
        schedule" — the optional normalization hook is explicitly *not* built by
        this batch (M6's brief: "정규화는 수동 유지+선택 스케줄 훅만"), so a
        schedule on a normalizer or an importer would be a row `apps/scheduler`
        can create a `collect`-shaped job against but that can never mean
        anything — the same "a route that looks like it works and does not"
        reasoning this module's own docstring gives for `/collect`/`/import`.
        """
        source = require_kind(source_or_404(source_id), "collector")
        interval = body.get("interval_seconds")
        enabled = body.get("enabled")
        if not isinstance(interval, int) or isinstance(interval, bool) or interval <= 0:
            raise HTTPException(
                status_code=422, detail="interval_seconds must be a positive integer"
            )
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=422, detail="enabled must be a boolean")
        with connect(config, autocommit=True) as handle:
            row = DomainStore(handle).upsert_schedule(source["source_id"], interval, enabled)
        return JSONResponse(schedule_view(source_id, row))

    # --------------------------------------------------------------- credentials

    @app.post("/sources/{source_id}/credentials", status_code=204)
    def write_source_credential(
        source_id: str, body: dict[str, Any] = _REQUIRED_BODY
    ) -> Response:
        """Write one credential value for this source (DP-034 D1/D2).

        Write-only, by construction rather than by convention: the value is read out of
        the request body once, passed straight to `write_credential`, and this function
        holds no other reference to it — it is never logged, never included in the
        response, and never read back by any other route. The response is empty on
        success (`204`), and an unresolvable secret store (unset, missing, inside the
        repository, wrong permissions — everything `secret_store_path()` already
        checks for a *read*) answers `422` with `CONFIGURATION_INVALID`, never a
        silent fallback to creating a store somewhere else.
        Wrapped in one `try`/`except ConfigurationInvalidError` from the source lookup
        onward: both `source_or_404`'s connection and `write_credential`'s store resolve
        the same `COSMA_SECRET_SOURCE`-named file (the runtime database password and the
        credential store are, in this deployment, the same kind of resolution), so a
        store that has become entirely unresolvable must surface as one clean
        `CONFIGURATION_INVALID` response regardless of which of the two calls hit it
        first, rather than a client-visible difference between "no such source" and an
        unhandled failure depending on exactly where the store stopped resolving.
        """
        purpose = body.get("purpose")
        value = body.get("value")
        if not isinstance(purpose, str) or not _PURPOSE_SHAPE.match(purpose):
            raise HTTPException(
                status_code=422,
                detail=(
                    "purpose must be a non-empty identifier (letters, digits, '_', '-', "
                    "starting with a letter)"
                ),
            )
        if not isinstance(value, str) or not value:
            raise HTTPException(status_code=422, detail="value must be a non-empty string")
        ref = credential_ref_for(source_id, purpose)
        if not CREDENTIAL_REF_PATTERN.match(ref):
            # Unreachable given `_PURPOSE_SHAPE` and `credential_ref_for`'s own
            # transliteration, short of `source_id` and `purpose` both being made
            # entirely of characters `_NOT_REF_CHARS` strips to nothing (a `purpose`
            # of `"---"` cannot pass `_PURPOSE_SHAPE`, but `source_id` carries no
            # equivalent guard) — refused explicitly rather than writing a
            # malformed-looking ref no CHECK on this row would ever hold.
            raise HTTPException(
                status_code=422,
                detail=f"source_id {source_id!r} yields no usable ref segment",
            )
        try:
            source_or_404(source_id)
            write_credential(ref, value)
        except ConfigurationInvalidError as failure:
            return JSONResponse(
                status_code=422, content=jsonable_encoder(failure.operator_view())
            )
        # `credential_ref` is exempt from the redaction walk (DP-018 D1;
        # `platform_core.obs.redaction.EXEMPT_KEYS`) — a ref is a name, safe to log.
        # `value` never reaches this call at all.
        logger.info("api.credential_written", source_id=source_id, credential_ref=ref)
        return Response(status_code=204)

    # -------------------------------------------------------------- snapshots

    @app.post("/sources/{source_id}/snapshots", status_code=201)
    def seal_snapshot(source_id: str) -> JSONResponse:
        """Materialize and seal every `raw_item` of this source (DP-019 D5)."""
        require_kind(source_or_404(source_id), "collector", "importer")
        with connect(config, autocommit=True) as handle:
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
        with connect(config, autocommit=True) as handle:
            store = DomainStore(handle)
            rows = store.list_snapshots(source_id)
            viewed = [snapshot_view(row, store.snapshot_tampering(row["id"])) for row in rows]
        return JSONResponse({"snapshots": viewed})

    @app.get("/snapshots/{snapshot_id}")
    def read_snapshot(snapshot_id: UUID) -> JSONResponse:
        row = snapshot_or_404(snapshot_id)
        with connect(config, autocommit=True) as handle:
            problems = DomainStore(handle).snapshot_tampering(snapshot_id)
        return JSONResponse(snapshot_view(row, problems))

    @app.post("/snapshots/{snapshot_id}/normalize", status_code=201)
    def start_normalization(
        snapshot_id: UUID, body: dict[str, Any] = _OPTIONAL_BODY
    ) -> JSONResponse:
        """Enqueue one normalize job over this sealed snapshot.

        **What "enqueue" means today.** This creates a `job` row with handler
        `f"{HANDLER_PREFIX}{addon_id}"`. Nothing in this tree yet registers a handler
        for that prefix — `addon_host` is M3 — so the created job is real (it is
        listed, read, and retried through the ordinary job surface) but stays
        `PENDING` until M3 lands a worker that can claim it. This route is reproduced
        now per the batch brief; `docs/p1/M2-RECORD.md` names the gap explicitly
        rather than letting a `201` read as "and it ran."
        """
        snapshot_or_404(snapshot_id)
        source_id = body.get(SOURCE_ID_FIELD)
        if not isinstance(source_id, str) or not source_id:
            raise HTTPException(
                status_code=422,
                detail=f"a normalize request must name a registered {SOURCE_ID_FIELD!r}",
            )
        source = require_kind(source_or_404(source_id), "normalizer")
        with connect(config, autocommit=True) as handle:
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
        """Every normalized result over this snapshot, all versions unless one is named."""
        snapshot_or_404(snapshot_id)
        with connect(config, autocommit=True) as handle:
            rows = DomainStore(handle).read_results(snapshot_id, addon_version)
        return JSONResponse({"results": [result_view(row) for row in rows]})


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #


def source_view(row: dict[str, Any]) -> dict[str, Any]:
    """One source as an operator sees it: named fields, never the stored blob.

    Assembled field by field rather than by redacting the whole row — P0's own module
    docstring records why: a stored blob shipped whole is a blob whose *future* fields
    nobody decided to publish. ``config`` still goes through the redactor as a second
    boundary, and ``credential_ref`` is shown directly: it is a key **name** (DP-018
    D1), and since M2 batch 2c it is also exempt from the redactor's containment match
    (``platform_core.obs.redaction.EXEMPT_KEYS``) should this view ever stop hand-picking
    fields.
    """
    profile = row["outbound_profile"] or {}
    inputs = row["input_profile"] or {}
    return {
        "source_id": row["source_id"],
        "addon_id": row["addon_id"],
        "addon_version": row["addon_version"],
        "kind": row["kind"],
        "config": dict(redact_mapping(row["config"] or {})),
        "config_schema_version": row["config_schema_version"],
        "credential_ref": row["credential_ref"],
        "outbound_profile": None if not profile else profile_view(profile),
        "input_profile": None if not inputs else input_profile_view(inputs),
        "data_class": row["data_class"],
        "enabled": row["enabled"],
        "created_at": _instant(row["created_at"]),
        "updated_at": _instant(row["updated_at"]),
    }


def profile_view(profile: dict[str, Any]) -> dict[str, Any]:
    """The approved outbound policy, field by named field. Every credential is a **key
    name**, never a value (DP-018)."""
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


def input_profile_view(profile: dict[str, Any]) -> dict[str, Any]:
    """The approved input grant, field by named field. DP-024. Neither field is
    redacted: both are the operator's own writing, and no credential lives here."""
    inputs = profile.get("inputs") or {}
    return {
        "root": str(profile.get("root", "")),
        "inputs": {str(name): str(member) for name, member in inputs.items()},
    }


def snapshot_view(row: dict[str, Any], problems: tuple[str, ...]) -> dict[str, Any]:
    """One snapshot, with whether it still matches what was sealed.

    ``verifies`` is computed rather than stored, so a dashboard cannot show a tampered
    input as ready to run.
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
    """One normalized record, with the two version axes and the lineage key. ``body``
    is external text a normalizer produced, so it goes through the redactor."""
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


def schedule_view(source_id: str, row: dict[str, Any] | None) -> dict[str, Any]:
    """One source's schedule, or the unset shape when it has none (DP-033 D5).

    `GET`'s own docstring is why `row is None` is not a 404: it is the ordinary
    resting state of "never configured", answered with the same field shape a
    configured-then-disabled schedule would have.
    """
    if row is None:
        return {
            "source_id": source_id,
            "interval_seconds": None,
            "enabled": False,
            "next_run_at": None,
            "last_run_at": None,
        }
    return {
        "source_id": row["source_id"],
        "interval_seconds": row["interval_seconds"],
        "enabled": row["enabled"],
        "next_run_at": _instant(row["next_run_at"]),
        "last_run_at": _instant(row["last_run_at"]),
    }


def raw_item_view(row: dict[str, Any]) -> dict[str, Any]:
    """One raw item, for the data browser (DP-033 D1/D2). Plain text, no redaction.

    DP-033 D2 is explicit that no body-level redaction mechanism exists anywhere in
    this platform, and does not add one — the payload is a page of unreviewed
    external text by design, exposed on the loopback-only operator surface under a
    plain-text-rendering obligation the *dashboard* (M5) holds. This view's own
    obligation is narrower: hand back text and nothing that could be read as a
    rendering instruction, which is why ``payload`` is a plain ``str`` field and
    carries no content-type-driven interpretation of its own.
    """
    payload = bytes(row["payload"])
    return {
        "item_key": row["item_key"],
        "seq": int(row["seq"]),
        "emitted_at": _instant(row["emitted_at"]),
        "content_type": row["content_type"],
        "payload": payload.decode("utf-8", errors="replace"),
    }


def _instant(value: Any) -> str | None:
    return None if value is None else value.isoformat()
