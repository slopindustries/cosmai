"""`normalizer.naver.blog` — the two rules DP-019 D1 permits, and DP-030 D2's fallback.

Copy-adapted from `experiments/integrated-p0/tests/test_normalizer_naver_blog.py` (M4
naver-blog worktree). `TestTheManifest`, `TestTheTwoRules`, `TestTheSchemaItProduces`,
and `TestItIsDeterministic` are unchanged — the rules and the schema did not change in
this batch. `TestWhatItRefusesToNormalize` is replaced by `TestPerRecordFallback`: P0's
normalizer skipped a record it could not fully process (`NormalizeOutcome.skipped`,
no result emitted); `docs/decisions/DP-030-p1-normalization-scope.md` D2 requires the
opposite — every item in the snapshot produces exactly one result, with the fields
that could not be derived set to `null` and a `notes.normalize_error {field, reason}`
entry, and the run's own summary aggregates how many results carried one. See
`handler.py`'s module docstring for the two distinct failure shapes this add-on
distinguishes. `TestConformance` and `TestDiscoveredFromTheRealAddonDirectory` are new,
for the same reason `test_collector_naver_blog.py`'s matching classes are new.

Every case here is a fixture of the *documented* response shape. `[가설]` That the real API
returns exactly this is what the real-data scenario tests; these are the rules, and they are
testable without a network, which is why they live apart.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from addon_api import CONTRACT_VERSION, AddonManifest, NormalizedResult, NormalizeOutcome
from addon_api.context import NormalizeContext
from addon_api.results import SnapshotItem
from addon_host.loading import load_addon, manifest_paths
from addon_host.settings import DEFAULT_ADDON_DIR
from addon_kit.conformance import format_conformance_report, run_conformance

ADDON_ROOT = Path(__file__).resolve().parents[1] / "addons" / "normalizer.naver.blog"


def load_entry() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "normalizer_naver_blog_under_test", ADDON_ROOT / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def an_item(**overrides: Any) -> SnapshotItem:
    entry: dict[str, Any] = {
        "title": "촉촉한 <b>수분크림</b> 후기",
        "link": "https://blog.naver.com/someone/123",
        "description": "발림성이 좋고 <b>수분감</b>이 오래갑니다",
        "bloggername": "어떤블로거",
        "bloggerlink": "https://blog.naver.com/someone",
        "postdate": "20260801",
    }
    entry.update(overrides)
    return SnapshotItem(
        item_key=entry["link"],
        payload=json.dumps(entry, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )


def normalize(*items: SnapshotItem, config: dict[str, Any] | None = None) -> Any:
    emitted: list[NormalizedResult] = []
    context = NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config=config if config is not None else {"language": "ko"},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: None,
    )
    outcome = load_entry()(context)
    return outcome, emitted


class TestTheManifest:
    def test_it_declares_the_normalizer_kind_and_an_output_contract(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.kind == "normalizer"
        assert manifest.output_contract_version == "0.1"
        assert manifest.supports(CONTRACT_VERSION)

    def test_it_declares_no_host_no_endpoint_and_no_credential(self) -> None:
        """DP-008 D4's asymmetry, at the manifest. A normalizer that asked for any of these
        is refused at load time, so this asserts it does not ask."""
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.declares.hosts == ()
        assert manifest.declares.endpoints == ()
        assert manifest.declares.needs_credential is False


class TestTheTwoRules:
    def test_markup_is_removed_from_the_title(self) -> None:
        """Naver wraps matched terms in `<b>`. Left in, every downstream reader has to
        strip it, and the ones that forget compare `"<b>수분크림</b>"` with `"수분크림"`."""
        _, results = normalize(an_item())
        assert results[0].body["title"] == "촉촉한 수분크림 후기"

    def test_markup_is_removed_from_the_excerpt(self) -> None:
        _, results = normalize(an_item())
        assert results[0].body["excerpt"] == "발림성이 좋고 수분감이 오래갑니다"

    def test_html_entities_are_decoded(self) -> None:
        """`&quot;` and `&amp;` appear in real titles. Decoding is part of "plain text"."""
        _, results = normalize(an_item(title="&quot;앰플&quot; &amp; 세럼"))
        assert results[0].body["title"] == '"앰플" & 세럼'

    def test_a_postdate_becomes_an_iso_date(self) -> None:
        _, results = normalize(an_item())
        assert results[0].body["published_at"] == "2026-08-01"

    def test_an_unparseable_postdate_becomes_null_rather_than_a_guess(self) -> None:
        """DP-019 D1: `published_at` is absent when the source gave no parseable date. A
        guessed date is a fact nobody can trace to the Raw it came from."""
        _, results = normalize(an_item(postdate="not-a-date"))
        assert results[0].body["published_at"] is None

    def test_a_missing_postdate_becomes_null(self) -> None:
        item = an_item()
        entry = json.loads(item.payload)
        del entry["postdate"]
        _, results = normalize(
            SnapshotItem(item.item_key, json.dumps(entry).encode("utf-8"), item.content_type)
        )
        assert results[0].body["published_at"] is None


class TestTheSchemaItProduces:
    def test_every_schema_0_1_field_is_present(self) -> None:
        _, results = normalize(an_item())
        assert set(results[0].body) == {
            "schema_version",
            "record_type",
            "external_id",
            "url",
            "title",
            "excerpt",
            "published_at",
            "author",
            "language",
        }

    def test_the_record_names_its_schema_and_type(self) -> None:
        _, results = normalize(an_item())
        assert results[0].body["schema_version"] == "0.1"
        assert results[0].body["record_type"] == "document"

    def test_the_link_is_both_the_identity_and_the_lineage_key(self) -> None:
        """The API assigns no id, and a post's URL is stable across pages and re-runs."""
        _, results = normalize(an_item())
        assert results[0].source_item_key == "https://blog.naver.com/someone/123"
        assert results[0].body["external_id"] == "https://blog.naver.com/someone/123"
        assert results[0].body["url"] == "https://blog.naver.com/someone/123"

    def test_the_language_is_configuration_and_not_detection(self) -> None:
        """DP-019 D2. A detected language is a guess in the same field as facts."""
        _, results = normalize(an_item(), config={"language": "en"})
        assert results[0].body["language"] == "en"

    def test_a_missing_blogger_name_becomes_null_rather_than_an_empty_string(self) -> None:
        """`author` is nullable in Schema 0.1 and `title` is not. "" and null are different
        claims: one says the source gave nothing, the other says it gave nothing useful."""
        item = an_item()
        entry = json.loads(item.payload)
        del entry["bloggername"]
        _, results = normalize(
            SnapshotItem(item.item_key, json.dumps(entry).encode("utf-8"), item.content_type)
        )
        assert results[0].body["author"] is None

    def test_it_carries_no_field_it_could_not_derive_from_the_payload(self) -> None:
        """The absence assertion DP-019 D1 is really about: no sentiment, no topic, no
        ingredient, no score."""
        _, results = normalize(an_item())
        for invented in ("sentiment", "topics", "ingredients", "score", "rank"):
            assert invented not in results[0].body


class TestItIsDeterministic:
    def test_two_runs_over_one_input_produce_equal_bodies(self) -> None:
        _, one = normalize(an_item(), an_item(link="https://blog.naver.com/other/1"))
        _, two = normalize(an_item(), an_item(link="https://blog.naver.com/other/1"))
        assert [r.body for r in one] == [r.body for r in two]

    def test_the_order_follows_the_snapshot(self) -> None:
        """The snapshot fixes the order (DP-019 D5), so the results follow it rather than
        imposing one of their own — two orderings would be two places to disagree."""
        a = an_item(link="https://blog.naver.com/a/1")
        b = an_item(link="https://blog.naver.com/b/1")
        _, results = normalize(b, a)
        assert [r.source_item_key for r in results] == [b.item_key, a.item_key]


class TestPerRecordFallback:
    """DP-030 D2: a record this add-on cannot fully normalize is emitted, not dropped.

    Replaces P0's `TestWhatItRefusesToNormalize` (`skipped` incremented, no result
    emitted). The run summary's own `notes["error_records"]` is the aggregate D2's text
    asks for: "the run summary aggregates the error-record count."
    """

    def test_an_item_that_is_not_json_gets_a_nulled_record_and_an_error_note(self) -> None:
        """A payload this add-on cannot parse at all carries no derivable data, so every
        field but `schema_version`/`record_type`/`language` nulls."""
        outcome, results = normalize(
            SnapshotItem("https://blog.naver.com/x/1", b"not json", "application/json")
        )
        assert isinstance(outcome, NormalizeOutcome)
        assert outcome.results_emitted == 1
        assert outcome.skipped == 0
        assert outcome.notes["error_records"] == 1
        [result] = results
        assert result.source_item_key == "https://blog.naver.com/x/1"
        assert result.body["schema_version"] == "0.1"
        assert result.body["record_type"] == "document"
        assert result.body["language"] == "ko"
        for field in ("external_id", "url", "title", "excerpt", "published_at", "author"):
            assert result.body[field] is None
        assert result.notes["normalize_error"] == {
            "field": "payload", "reason": "payload is not valid JSON",
        }

    def test_an_item_with_no_link_keeps_what_parsed_and_nulls_only_the_identity(self) -> None:
        """A payload that parses but has no usable `link` still has a title, an excerpt,
        a date, and a blogger name worth keeping — only the two fields `link` would have
        derived (`external_id`, `url`) null."""
        item = an_item()
        entry = json.loads(item.payload)
        del entry["link"]
        outcome, results = normalize(
            SnapshotItem("https://blog.naver.com/kept-by-item-key", json.dumps(entry).encode(
                "utf-8"), item.content_type)
        )
        assert outcome.results_emitted == 1
        assert outcome.skipped == 0
        assert outcome.notes["error_records"] == 1
        [result] = results
        # `source_item_key` always comes from the snapshot, never from the payload — it
        # is not what failed here.
        assert result.source_item_key == "https://blog.naver.com/kept-by-item-key"
        assert result.body["external_id"] is None
        assert result.body["url"] is None
        assert result.body["title"] == "촉촉한 수분크림 후기"
        assert result.body["excerpt"] == "발림성이 좋고 수분감이 오래갑니다"
        assert result.body["published_at"] == "2026-08-01"
        assert result.body["author"] == "어떤블로거"
        assert result.notes["normalize_error"] == {
            "field": "link", "reason": "missing or invalid `link` field",
        }

    def test_the_count_it_reports_matches_what_it_emitted(self) -> None:
        """The host cross-checks this and fails the attempt on a mismatch, so an add-on
        that miscounts is caught. Asserting it here as well means the add-on is not
        depending on the host to notice."""
        outcome, results = normalize(an_item(), an_item(link="https://blog.naver.com/z/1"))
        assert outcome.results_emitted == len(results) == 2

    def test_a_mixed_snapshot_of_one_bad_and_two_good_yields_three_results_one_error(
        self,
    ) -> None:
        """DP-030 D2's own regression shape: one bad row, two good rows -> three results,
        one error aggregated — not two results and a dropped third."""
        outcome, results = normalize(
            an_item(),
            SnapshotItem("https://blog.naver.com/x/1", b"{", "application/json"),
            an_item(link="https://blog.naver.com/z/1"),
        )
        assert outcome.results_emitted == 3
        assert outcome.skipped == 0
        assert outcome.notes["error_records"] == 1
        assert len(results) == 3
        errored = [r for r in results if "normalize_error" in r.notes]
        assert len(errored) == 1
        assert errored[0].source_item_key == "https://blog.naver.com/x/1"

    def test_a_clean_snapshot_carries_no_normalize_error_and_counts_zero(self) -> None:
        """Positive control: a run with nothing to fall back on reports zero errors,
        so the count above is doing something rather than always reading nonzero."""
        outcome, results = normalize(an_item())
        assert outcome.notes["error_records"] == 0
        assert "normalize_error" not in results[0].notes


class TestConformance:
    """`addon_kit.conformance.run_conformance` against the real add-on directory.

    `TestDeterminismIsDeliberatelyNotChecked` in `apps/tests/test_addon_conformance.py`
    already covers the DP-030 D1 half generically; this class is specific to this
    add-on's own manifest and handler.
    """

    def test_the_addon_is_conformant(self) -> None:
        snapshot = [
            SnapshotItem(
                item_key="https://blog.naver.com/someone/123",
                payload=an_item().payload,
                content_type="application/json",
            )
        ]

        report = run_conformance(ADDON_ROOT, snapshot=snapshot, config={"language": "ko"})

        assert report.passed, format_conformance_report(report)
        assert report.addon_id == "normalizer.naver.blog"
        names = [check.name for check in report.checks]
        assert names == [
            "manifest_is_valid",
            "contract_range_is_satisfiable",
            "entry_is_resolvable",
            "kind_capability_conformance",
        ]

    def test_a_snapshot_that_would_have_been_skipped_under_p0_still_passes(self) -> None:
        """DP-030 D2 in the conformance suite's own terms: this add-on's per-record
        fallback still returns a well-formed `NormalizeOutcome` whose own count matches
        what it emitted, which is exactly what `kind_capability_conformance` checks."""
        snapshot = [SnapshotItem(item_key="x", payload=b"not json", content_type="text/plain")]

        report = run_conformance(ADDON_ROOT, snapshot=snapshot, config={"language": "ko"})

        assert report.passed, format_conformance_report(report)


class TestDiscoveredFromTheRealAddonDirectory:
    """This add-on as installed, not as a fixture built by hand.

    See `test_collector_naver_blog.py`'s matching class for the full reasoning; this is
    the normalizer half of the same check.
    """

    def test_the_addon_is_among_what_the_default_root_discovers(self) -> None:
        paths = manifest_paths(DEFAULT_ADDON_DIR)
        assert ADDON_ROOT / "addon.toml" in paths

    def test_the_addon_loads_and_passes_the_version_gate(self) -> None:
        addon = load_addon(ADDON_ROOT / "addon.toml")
        assert addon.manifest.addon_id == "normalizer.naver.blog"
        assert addon.manifest.kind == "normalizer"
        assert addon.manifest.supports()
        assert addon.directory == ADDON_ROOT
        assert callable(addon.entry)
