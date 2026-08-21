"""collector.tubedepth.rest: fixture-based logic tests, conformance, and host-loading.

Three layers, each proving something the others cannot (`docs/conventions/addon-authoring.md`,
"하네스가 표현하지 못하는 것" / "⚠️ 하네스를 통과하는 것은 통합의 증거가 아니다"):

- ``TestHandlerLogic`` calls ``handler.run`` directly against a hand-built
  ``CollectContext`` whose ``fetch`` is a small Python stub returning scripted
  ``FetchResponse``s per call. This is the only way to exercise three different
  dereference outcomes (200/404/409/410) in one collector run: ``addon_kit``'s
  harness fixtures serve one status code for the whole run.
- ``TestGoldenPathThroughTheHarness`` runs the real add-on through
  ``addon_kit.harness``/``addon_kit.conformance`` against committed fixtures — the
  add-on's own manifest, config validation, and entry point, exercised the way an
  author runs them before a host exists.
- ``TestHostLoading`` runs the real add-on through ``addon_host.loading`` — the
  version gate and the credential-hygiene scan a real host applies before this
  add-on's module is ever imported.

Neither layer exercises ``domain.outbound``/``domain.transport`` (the real
outbound guard, credential attachment, or atomicity) — that evidence is the
batch report's live-verification section, not a pytest fixture; see this
add-on's README.md, "Live verification, and two platform-level findings".
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from addon_api.context import CollectContext, FetchResponse, Limits
from addon_api.errors import AddonConfigInvalid, AddonOutputInvalid, AddonPermanent, AddonTransient
from addon_api.results import CollectOutcome, RawItem
from addon_host.loading import load_addon
from addon_kit.conformance import format_conformance_report, run_conformance
from addon_kit.harness import default_limits, load_fixtures, run_addon

ADDON_DIR = Path(__file__).resolve().parents[1] / "addons" / "collector.tubedepth.rest"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "collector.tubedepth.rest"

FAKE_CREDENTIAL = "should-never-appear-anywhere-in-output"  # noqa: S105 - test sentinel, not a real secret


def _load_handler() -> ModuleType:
    """Import ``handler.py`` by path, the way ``addon_host``/``addon_kit`` both do —
    an add-on's directory name (dots included) is not an importable package path."""
    path = ADDON_DIR / "handler.py"
    spec = importlib.util.spec_from_file_location("collector_tubedepth_rest_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HANDLER = _load_handler()


class _ScriptedFetch:
    """A ``Fetch`` stub that answers each call from a queue keyed by ``endpoint_ref``.

    Deliberately not the harness's ``_Recorder``: that one status code applies to a
    whole run, and this add-on's dereference branch needs a different status per
    call within the *same* run.
    """

    def __init__(self, scripts: Mapping[str, Sequence[FetchResponse]]) -> None:
        self._queues = {key: list(value) for key, value in scripts.items()}
        self.calls: list[tuple[str, Mapping[str, str] | None]] = []

    def __call__(
        self,
        endpoint_ref: str,
        params: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> FetchResponse:
        self.calls.append((endpoint_ref, params))
        queue = self._queues.get(endpoint_ref)
        assert queue, f"no scripted response left for {endpoint_ref!r} (call {params!r})"
        return queue.pop(0)


class _Recorder:
    """Buffers what the add-on did, the way ``addon_host.capabilities`` would,
    without a database or a transaction — enough to assert on."""

    def __init__(self) -> None:
        self.raw_items: list[RawItem] = []
        self.cursors: dict[str, Any] = {}
        self.accepted: list[tuple[int, str]] = []
        self.logs: list[tuple[str, Mapping[str, Any]]] = []

    def emit_raw(self, items: Sequence[RawItem]) -> None:
        self.raw_items.extend(items)

    def advance_cursor(self, stream: str, value: Any) -> None:
        self.cursors[stream] = value

    def accept_status(self, response: FetchResponse, reason: str) -> None:
        assert reason and reason.strip(), "accept_status needs a real reason (contract 1.2)"
        self.accepted.append((response.status, reason))

    def log(self, event: str, fields: Mapping[str, Any]) -> None:
        self.logs.append((event, dict(fields)))


def _response(
    endpoint_ref: str, status: int, body: Mapping[str, Any], envelope_ref: str
) -> FetchResponse:
    return FetchResponse(
        endpoint_ref=endpoint_ref,
        status=status,
        headers={"content-type": "application/json"},
        body=json.dumps(body).encode("utf-8"),
        envelope_ref=envelope_ref,
        retrieved_at="2026-08-21T00:00:00Z",
    )


def _context(
    fetch: _ScriptedFetch,
    recorder: _Recorder,
    config: Mapping[str, Any],
    cursor: Any = None,
) -> CollectContext:
    return CollectContext(
        source_id="test-tubedepth",
        config=config,
        cursor=cursor,
        limits=Limits(
            connect_timeout_s=5.0,
            read_timeout_s=30.0,
            max_response_bytes=8 * 1024 * 1024,
            max_redirects=3,
            max_pages=20,
            max_records=5000,
        ),
        fetch=fetch,
        accept_status=recorder.accept_status,
        emit_raw=recorder.emit_raw,
        advance_cursor=recorder.advance_cursor,
        log=recorder.log,
    )


def _list_page(artifacts: Sequence[Mapping[str, Any]], cursor: str | None) -> Mapping[str, Any]:
    return {"artifacts": list(artifacts), "cursor": cursor}


def _notes(
    *, aged_out: int = 0, retracted: int = 0, unattributed: int = 0,
    skipped_by_kind: int = 0, pages: int,
) -> dict[str, int]:
    return {
        "aged_out": aged_out,
        "retracted": retracted,
        "unattributed": unattributed,
        "skipped_by_kind": skipped_by_kind,
        "pages": pages,
    }


def _artifact(kind: str, target: str, digest: str, fetched_at: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "target": target,
        "schema_version": "1",
        "digest": digest,
        "byte_count": 10,
        "fetched_at": fetched_at,
        "fresh_until": fetched_at,
    }


def _payload_body(kind: str, target: str, digest: str, fetched_at: str) -> dict[str, Any]:
    return {
        "digest": digest,
        "kind": kind,
        "target": target,
        "observations": 1,
        "first_fetched_at": fetched_at,
        "fetched_at": fetched_at,
        "schema_version": "1",
        "current_schema_version": "1",
        "payload_fields": [],
        "current_fields": [],
        "payload": {"note": "test payload", "credential": None},
    }


class TestHandlerLogic:
    """Direct calls, one scripted status per dereference — see the module docstring."""

    def test_a_single_page_emits_one_item_per_kept_artifact(self) -> None:
        artifacts = [_artifact("video.metadata", "abc", "digest-1", "2026-08-19T00:00:00Z")]
        page = _list_page(artifacts, None)
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [_response("artifacts_list", 200, page, "env-list")],
                "artifact_payload": [
                    _response(
                        "artifact_payload",
                        200,
                        _payload_body("video.metadata", "abc", "digest-1", "2026-08-19T00:00:00Z"),
                        "env-payload-1",
                    )
                ],
            }
        )
        recorder = _Recorder()
        outcome = HANDLER.run(_context(fetch, recorder, {}))

        assert outcome == CollectOutcome(
            items_emitted=1, more_available=False, notes=_notes(pages=1)
        )
        assert len(recorder.raw_items) == 1
        item = recorder.raw_items[0]
        assert item.item_key == "video.metadata|abc|2026-08-19T00:00:00Z"
        assert item.envelope_ref == "env-payload-1"
        assert item.content_type == "application/json"
        assert recorder.cursors == {"artifacts": {"since": "2026-08-19T00:00:00Z"}}

    def test_the_watermark_is_the_newest_fetched_at_across_every_page(self) -> None:
        """Newest-first pages: the cursor written is page 1's first row, not the last
        row processed."""
        page1 = [
            _artifact("video.metadata", "newest", "d1", "2026-08-20T00:00:00Z"),
            _artifact("video.metadata", "middle", "d2", "2026-08-19T00:00:00Z"),
        ]
        page2 = [_artifact("video.metadata", "oldest", "d3", "2026-08-18T00:00:00Z")]
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [
                    _response("artifacts_list", 200, _list_page(page1, "opaque-cursor"), "env-1"),
                    _response("artifacts_list", 200, _list_page(page2, None), "env-2"),
                ],
                "artifact_payload": [
                    _response(
                        "artifact_payload", 200,
                        _payload_body("video.metadata", "newest", "d1", "2026-08-20T00:00:00Z"),
                        "env-p1",
                    ),
                    _response(
                        "artifact_payload", 200,
                        _payload_body("video.metadata", "middle", "d2", "2026-08-19T00:00:00Z"),
                        "env-p2",
                    ),
                    _response(
                        "artifact_payload", 200,
                        _payload_body("video.metadata", "oldest", "d3", "2026-08-18T00:00:00Z"),
                        "env-p3",
                    ),
                ],
            }
        )
        recorder = _Recorder()
        outcome = HANDLER.run(_context(fetch, recorder, {}))

        assert outcome.items_emitted == 3
        assert recorder.cursors == {"artifacts": {"since": "2026-08-20T00:00:00Z"}}
        # Both pages were requested with the run's own second-page keyset cursor,
        # never the add-on's own watermark cursor (they are different things).
        list_calls = [call for call in fetch.calls if call[0] == "artifacts_list"]
        assert list_calls[0] == ("artifacts_list", {"limit": "50"})
        assert list_calls[1] == ("artifacts_list", {"limit": "50", "cursor": "opaque-cursor"})

    def test_a_stored_watermark_becomes_the_since_parameter(self) -> None:
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [
                    _response("artifacts_list", 200, _list_page([], None), "env-1")
                ],
                "artifact_payload": [],
            }
        )
        recorder = _Recorder()
        HANDLER.run(_context(fetch, recorder, {}, cursor={"since": "2026-08-19T00:00:00Z"}))

        assert fetch.calls[0] == (
            "artifacts_list", {"limit": "50", "since": "2026-08-19T00:00:00Z"}
        )
        # Nothing was seen this run, so the cursor is left exactly as it was.
        assert recorder.cursors == {}

    def test_a_malformed_stored_cursor_is_refused(self) -> None:
        fetch = _ScriptedFetch({"artifacts_list": [], "artifact_payload": []})
        recorder = _Recorder()
        with pytest.raises(AddonOutputInvalid):
            HANDLER.run(_context(fetch, recorder, {}, cursor={"wrong_key": "x"}))

    def test_kinds_not_on_the_allowlist_are_skipped_and_never_dereferenced(self) -> None:
        artifacts = [
            _artifact("video.metadata", "keep", "d1", "2026-08-19T00:00:00Z"),
            _artifact("video.comments", "drop", "d2", "2026-08-19T00:00:00Z"),
        ]
        page = _list_page(artifacts, None)
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [_response("artifacts_list", 200, page, "env-1")],
                "artifact_payload": [
                    _response(
                        "artifact_payload", 200,
                        _payload_body("video.metadata", "keep", "d1", "2026-08-19T00:00:00Z"),
                        "env-p1",
                    )
                ],
            }
        )
        recorder = _Recorder()
        outcome = HANDLER.run(_context(fetch, recorder, {"kinds": "video.metadata"}))

        assert outcome.items_emitted == 1
        assert outcome.notes["skipped_by_kind"] == 1
        kept_key = "video.metadata|keep|2026-08-19T00:00:00Z"
        assert [item.item_key for item in recorder.raw_items] == [kept_key]
        # The dropped kind's digest was never dereferenced: only one artifact_payload
        # call was scripted and it was consumed exactly once.
        assert [call for call in fetch.calls if call[0] == "artifact_payload"] == [
            ("artifact_payload", {"digest": "d1"})
        ]

    @pytest.mark.parametrize(
        ("status", "counter_name", "reason_fragment"),
        [
            (404, "aged_out", "retention"),
            (410, "retracted", "retracted"),
            (409, "unattributed", "schema version"),
        ],
    )
    def test_dereference_status_is_data_not_failure(
        self, status: int, counter_name: str, reason_fragment: str
    ) -> None:
        artifacts = [_artifact("video.metadata", "x", "digest-1", "2026-08-19T00:00:00Z")]
        page = _list_page(artifacts, None)
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [_response("artifacts_list", 200, page, "env-1")],
                "artifact_payload": [
                    FetchResponse(
                        endpoint_ref="artifact_payload",
                        status=status,
                        headers={"content-type": "application/json"},
                        body=json.dumps({"error": {"code": "x", "message": "x"}}).encode(),
                        envelope_ref="env-p1",
                        retrieved_at="2026-08-21T00:00:00Z",
                    )
                ],
            }
        )
        recorder = _Recorder()
        outcome = HANDLER.run(_context(fetch, recorder, {}))

        assert outcome.items_emitted == 0
        assert recorder.raw_items == []
        assert outcome.notes[counter_name] == 1
        assert len(recorder.accepted) == 1
        accepted_status, reason = recorder.accepted[0]
        assert accepted_status == status
        assert reason_fragment in reason
        # The run still succeeded and still advanced its watermark: a skip is not a
        # failure (contract 1.2's own distinction between refusing and deciding).
        assert recorder.cursors == {"artifacts": {"since": "2026-08-19T00:00:00Z"}}

    def test_401_on_the_list_route_is_a_configuration_failure(self) -> None:
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [
                    _response(
                        "artifacts_list", 401,
                        {"error": {"code": "unauthenticated", "message": "x"}}, "env-1",
                    )
                ],
                "artifact_payload": [],
            }
        )
        with pytest.raises(AddonConfigInvalid):
            HANDLER.run(_context(fetch, _Recorder(), {}))

    def test_429_on_the_list_route_is_transient(self) -> None:
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [
                    _response(
                        "artifacts_list", 429,
                        {"error": {"code": "rate_limited", "message": "x"}}, "env-1",
                    )
                ],
                "artifact_payload": [],
            }
        )
        with pytest.raises(AddonTransient):
            HANDLER.run(_context(fetch, _Recorder(), {}))

    def test_422_on_the_list_route_is_permanent_a_defect_in_this_addon(self) -> None:
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [
                    _response(
                        "artifacts_list", 422,
                        {"error": {"code": "invalid_request", "message": "x"}}, "env-1",
                    )
                ],
                "artifact_payload": [],
            }
        )
        with pytest.raises(AddonPermanent):
            HANDLER.run(_context(fetch, _Recorder(), {}))

    @pytest.mark.parametrize("bad_limit", [0, 501, -1])
    def test_an_out_of_range_page_limit_is_refused_before_any_request(self, bad_limit: int) -> None:
        fetch = _ScriptedFetch({"artifacts_list": [], "artifact_payload": []})
        with pytest.raises(AddonConfigInvalid):
            HANDLER.run(_context(fetch, _Recorder(), {"page_limit": bad_limit}))
        assert fetch.calls == []

    def test_the_credential_never_appears_in_a_raw_item_or_a_log_line(self) -> None:
        """This add-on never receives a credential (DP-008 D4) — this is a sentinel
        check that nothing it *does* handle leaks the one string a real deployment
        would never let it see either."""
        artifacts = [_artifact("video.metadata", "x", "digest-1", "2026-08-19T00:00:00Z")]
        page = _list_page(artifacts, None)
        fetch = _ScriptedFetch(
            {
                "artifacts_list": [_response("artifacts_list", 200, page, "env-1")],
                "artifact_payload": [
                    _response(
                        "artifact_payload", 200,
                        _payload_body("video.metadata", "x", "digest-1", "2026-08-19T00:00:00Z"),
                        "env-p1",
                    )
                ],
            }
        )
        recorder = _Recorder()
        HANDLER.run(_context(fetch, recorder, {"kinds": FAKE_CREDENTIAL}))

        for item in recorder.raw_items:
            assert FAKE_CREDENTIAL not in item.item_key
            assert FAKE_CREDENTIAL.encode() not in item.payload
            assert FAKE_CREDENTIAL not in json.dumps(item.notes)
        for _, fields in recorder.logs:
            assert FAKE_CREDENTIAL not in json.dumps(fields)


class TestGoldenPathThroughTheHarness:
    """Fixture-based, through ``addon_kit.harness`` — the golden path only, since the
    harness serves one status per run (see the module docstring)."""

    def test_two_pages_yield_three_items_and_the_newest_watermark(self) -> None:
        fixtures = load_fixtures(FIXTURES_DIR)
        result = run_addon(ADDON_DIR, fixtures=fixtures, config={})

        assert not result.failed, result.failure
        assert result.outcome == CollectOutcome(
            items_emitted=3, more_available=False, notes=_notes(pages=2)
        )
        assert len(result.raw_items) == 3
        assert result.cursors == {"artifacts": {"since": "2026-08-19T00:29:38.328557Z"}}
        assert not result.emitted_count_disagrees()

    def test_a_kinds_allowlist_narrows_what_is_emitted(self) -> None:
        fixtures = load_fixtures(FIXTURES_DIR)
        result = run_addon(ADDON_DIR, fixtures=fixtures, config={"kinds": "channel.about"})

        assert not result.failed, result.failure
        assert [item.item_key for item in result.raw_items] == [
            "channel.about|UCHnyfMqiRRG1u-2MsSQLbXA|2026-08-17T09:00:00.000000Z"
        ]


class TestConformance:
    def test_the_add_on_is_conformant(self) -> None:
        fixtures = load_fixtures(FIXTURES_DIR)
        report = run_conformance(ADDON_DIR, fixtures=fixtures, config={})

        assert report.passed, format_conformance_report(report)
        assert report.addon_id == "collector.tubedepth.rest"


class TestHostLoading:
    """The real host's load path: the version gate and the credential-hygiene scan,
    both run before this add-on's module is ever imported for real."""

    def test_the_add_on_loads_through_the_real_host(self) -> None:
        loaded = load_addon(ADDON_DIR / "addon.toml")

        assert loaded.manifest.addon_id == "collector.tubedepth.rest"
        assert loaded.manifest.kind == "collector"
        assert loaded.manifest.declares.needs_credential is True
        assert set(loaded.manifest.declares.endpoints) == {"artifacts_list", "artifact_payload"}
        assert loaded.manifest.declares.streams == ("artifacts",)
        assert callable(loaded.entry)

    def test_default_limits_are_readable_by_the_harness_too(self) -> None:
        # Sanity: the harness's own default limits construct without error, so a
        # future add-on change that reads context.limits has something to read in
        # every test path this module uses.
        assert default_limits().max_pages > 0
