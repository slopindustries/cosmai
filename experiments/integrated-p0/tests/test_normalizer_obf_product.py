"""`normalizer.obf.product` — Open Beauty Facts rows into `Normalized Schema 0.3` `product`
records (DP-028, TASK-008).

**Fixtures are structural, per DP-022.** Every payload below reproduces the *shape* DP-028
D3 declares — a `code` that looks like a barcode, sparse `product_name`, `brands_tags` as a
list, `last_modified_t` as Unix seconds — and carries no row anyone actually contributed.
`8801234567890` and `"Example Whitening Cream"` are invented for this file; DP-027 D3 keeps
P0 publishing nothing real from this source even though ODbL would permit it with
obligations.

`[결정]` **Correction (TASK-010).** This paragraph previously attributed `brands_tags` as a
list to `SRC-003`. It does not: `SRC-003` measured `brands` (a comma-joined string) and used
`brands_tags` only as a search-facet parameter, never as a measured response field — the
attack report on TASK-008 named this as F1. The attribution is corrected here to DP-028 D3,
which is the actual source of the field name. `[측정]` TASK-008's `Review` section records
the orchestrator's own reading of TASK-007's real capture (`var/samples/obf/`, 247 rows
across both deltas): `brands_tags` present on 26 of 121 rows in delta A, a `list` in every
one of those rows, and every one of the 70 values across both deltas carrying an `xx:`
language prefix. TASK-010's own run through the installed host, recorded in
`test_obf_real_data.py` and `evidence/obf-dataset/README.md`, measures the same field
independently over the same real rows — see that record for whether it confirms or
contradicts the orchestrator's reading — so the *shape* this file's fixtures assumed is
grounded in a real capture, not merely assumed, even though the sentence that used to claim
the measurement named the wrong document.

**Why the DB-backed class is separate.** Every other class in this file exercises the
add-on in isolation, the way `normalizer.naver.trend`'s tests do — a `NormalizeContext`
built by hand, no database. `TestCoexistenceOverOneLineage` is the one acceptance criterion
(6) that cannot be shown that way: "stands beside" is a claim about what one lineage's
`normalized_result` rows look like together, which only `domain.store` can show. It is
marked `pytest.mark.usefixtures("database")` at the class level so a run without a reachable
PostgreSQL cluster skips that one class (via the `platform_database` fixture's own skip)
rather than failing the whole file or silently passing nothing.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from uuid import UUID

import psycopg
import pytest
from addon_api import CONTRACT_VERSION, AddonManifest, NormalizedResult, NormalizeOutcome
from addon_api.context import NormalizeContext
from addon_api.results import SnapshotItem
from domain.store import DomainStore, NormalizedResultRow, SourceRow

ADDON_ROOT = Path(__file__).resolve().parents[1] / "addons" / "normalizer.obf.product"


def load_entry() -> Any:
    spec = importlib.util.spec_from_file_location(
        "normalizer_obf_product_under_test", ADDON_ROOT / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def a_row(**overrides: Any) -> dict[str, Any]:
    """One structurally plausible Open Beauty Facts row. No field's *value* is real; every
    field's *shape* — type, nesting, and which fields co-occur — is what SRC-003 measured."""
    row: dict[str, Any] = {
        "code": "8801234567890",
        "product_name": "Example Whitening Cream",
        "brands_tags": ["brand-alpha", "brand-beta"],
        "ingredients_text": "aqua, glycerin, parfum",
        "last_modified_t": 1735689600,
    }
    row.update(overrides)
    return row


def drop(row: dict[str, Any], *keys: str) -> dict[str, Any]:
    """`a_row()` with the named keys absent rather than null — the source *omitting* a
    field and the source sending it as `null` are different claims, and OBF's own field
    documentation (SRC-003) describes omission, not nulls."""
    return {key: value for key, value in row.items() if key not in keys}


def a_snapshot_item(row: dict[str, Any] | None = None, item_key: str | None = None) -> SnapshotItem:
    payload = a_row() if row is None else row
    key = item_key if item_key is not None else str(payload.get("code", "item"))
    return SnapshotItem(
        item_key=key,
        payload=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )


def normalize(
    *items: SnapshotItem, config: dict[str, Any] | None = None
) -> tuple[NormalizeOutcome, list[NormalizedResult]]:
    emitted: list[NormalizedResult] = []
    context = NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config=config if config is not None else {},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: None,
    )
    return load_entry()(context), emitted


class TestTheManifest:
    def test_it_declares_schema_0_3_as_its_output_contract(self) -> None:
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.kind == "normalizer"
        assert manifest.output_contract_version == "0.3"
        assert manifest.supports(CONTRACT_VERSION)

    def test_it_declares_no_host_endpoint_credential_or_stream(self) -> None:
        """DP-008 D4: a normalizer receives a sealed snapshot and nothing else, and
        `addon_api`'s manifest parser would refuse a normalizer declaring any of these."""
        manifest = AddonManifest.load(ADDON_ROOT / "addon.toml")
        assert manifest.declares.hosts == ()
        assert manifest.declares.endpoints == ()
        assert manifest.declares.needs_credential is False
        assert manifest.declares.streams == ()


class TestTheEnvelopeAndTheRecord:
    def test_every_schema_0_3_product_field_is_present(self) -> None:
        """DP-028 D3's five fields (`external_id` in the envelope, the other four in the
        body) plus the envelope's `schema_version`, `record_type`, and `language` — and
        nothing else."""
        _, results = normalize(a_snapshot_item())
        assert set(results[0].body) == {
            "schema_version",
            "record_type",
            "external_id",
            "language",
            "display_name",
            "brands",
            "observed_at",
            "has_ingredients",
        }

    def test_it_names_schema_0_3_and_the_product_record_type(self) -> None:
        """DP-028 D1: `product` is the third member of the union, additive over 0.2."""
        _, results = normalize(a_snapshot_item())
        assert results[0].body["schema_version"] == "0.3"
        assert results[0].body["record_type"] == "product"

    def test_the_external_id_is_the_code_and_matches_the_lineage_key(self) -> None:
        _, results = normalize(a_snapshot_item(a_row(code="8800000000017")))
        assert results[0].body["external_id"] == "8800000000017"
        assert results[0].source_item_key == "8800000000017"

    def test_language_is_configuration_and_not_detection(self) -> None:
        """DP-019 D2. `[측정]` DP-028 records 0/36 Korean rows carrying `product_name_ko`
        and no Hangul in any sampled `product_name`, which is why `en` is the *default* and
        not the *only* legal value — a run can still be configured otherwise."""
        _, results = normalize(a_snapshot_item(), config={"language": "ko"})
        assert results[0].body["language"] == "ko"

    def test_language_defaults_to_en(self) -> None:
        _, results = normalize(a_snapshot_item(), config={})
        assert results[0].body["language"] == "en"

    def test_a_blank_configured_language_falls_back_to_the_default(self) -> None:
        _, results = normalize(a_snapshot_item(), config={"language": "   "})
        assert results[0].body["language"] == "en"


class TestNoProductIdentityWork:
    """DP-028 D5 and the packet's stopping condition: no category, no ingredient taxonomy,
    no resolved brand. This is the positive-control counterpart of every "field X is
    present" assertion above — a body that additionally carried one of these would still
    pass every other test in this file, so it needs its own."""

    def test_no_category_ingredient_taxonomy_or_resolved_brand_field_exists(self) -> None:
        _, results = normalize(a_snapshot_item())
        body = results[0].body
        for invented in (
            "category",
            "categories",
            "category_id",
            "ingredient_list",
            "ingredients",
            "brand",
            "canonical_brand",
            "brand_id",
        ):
            assert invented not in body, f"{invented!r} is product-identity work DP-028 D5 forbids"


class TestDisplayName:
    """DP-028 D3: `product_name`, verbatim, null when the source omits it or it is blank."""

    def test_a_present_value_is_carried_exactly_as_sent(self) -> None:
        """`[가설]` pinned here: "verbatim" means untrimmed. A leading/trailing space in
        the source's `product_name` survives into `display_name` unchanged. Falsified by a
        real capture the project decides should have that whitespace stripped instead."""
        item = a_snapshot_item(a_row(product_name="  Example Whitening Cream  "))
        _, results = normalize(item)
        assert results[0].body["display_name"] == "  Example Whitening Cream  "

    def test_an_absent_product_name_abstains_to_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "product_name"))
        _, results = normalize(item)
        assert results[0].body["display_name"] is None

    def test_an_empty_string_abstains_to_null(self) -> None:
        item = a_snapshot_item(a_row(product_name=""))
        _, results = normalize(item)
        assert results[0].body["display_name"] is None

    def test_a_whitespace_only_string_abstains_to_null(self) -> None:
        item = a_snapshot_item(a_row(product_name="   "))
        _, results = normalize(item)
        assert results[0].body["display_name"] is None

    def test_a_non_string_product_name_abstains_to_null_rather_than_raising(self) -> None:
        item = a_snapshot_item(a_row(product_name=12345))
        outcome, results = normalize(item)
        assert outcome.results_emitted == 1
        assert results[0].body["display_name"] is None


class TestBrands:
    """DP-028 D3: `brands_tags`, order preserved, never null — `[]` when the source has
    none."""

    def test_order_is_preserved_exactly_as_the_source_sent_it(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=["zzz-brand", "aaa-brand", "mmm-brand"]))
        _, results = normalize(item)
        assert results[0].body["brands"] == ["zzz-brand", "aaa-brand", "mmm-brand"]

    def test_an_absent_brands_tags_is_an_empty_list_not_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "brands_tags"))
        _, results = normalize(item)
        assert results[0].body["brands"] == []

    def test_an_empty_brands_tags_stays_an_empty_list(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=[]))
        _, results = normalize(item)
        assert results[0].body["brands"] == []

    def test_a_single_brand_survives_as_a_one_element_list(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=["solo-brand"]))
        _, results = normalize(item)
        assert results[0].body["brands"] == ["solo-brand"]


class TestObservedAt:
    """DP-028 D3: `last_modified_t`, Unix seconds to ISO-8601 UTC, null when the source
    omits it. Acceptance criterion: a non-numeric value abstains rather than raising."""

    def test_a_unix_seconds_value_converts_to_iso_8601_utc(self) -> None:
        item = a_snapshot_item(a_row(last_modified_t=1735689600))
        _, results = normalize(item)
        assert results[0].body["observed_at"] == "2025-01-01T00:00:00Z"

    def test_a_float_unix_seconds_value_also_converts(self) -> None:
        item = a_snapshot_item(a_row(last_modified_t=1735689600.0))
        _, results = normalize(item)
        assert results[0].body["observed_at"] == "2025-01-01T00:00:00Z"

    def test_an_absent_last_modified_t_abstains_to_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "last_modified_t"))
        _, results = normalize(item)
        assert results[0].body["observed_at"] is None

    def test_a_non_numeric_value_abstains_rather_than_raising(self) -> None:
        """`[가설]` pinned here: "non-numeric" means anything that is not a JSON `int` or
        `float`, including a numeric-looking string. Falsified by a real capture carrying
        `last_modified_t` as a string that the project decides should still convert."""
        item = a_snapshot_item(a_row(last_modified_t="not-a-number"))
        outcome, results = normalize(item)
        assert outcome.results_emitted == 1
        assert results[0].body["observed_at"] is None

    def test_a_numeric_looking_string_also_abstains(self) -> None:
        item = a_snapshot_item(a_row(last_modified_t="1735689600"))
        _, results = normalize(item)
        assert results[0].body["observed_at"] is None

    def test_a_boolean_is_not_treated_as_a_numeric_timestamp(self) -> None:
        """`bool` is an `int` subclass in Python; a timestamp of `True` would be a type
        checker's blind spot rather than an observation."""
        item = a_snapshot_item(a_row(last_modified_t=True))
        _, results = normalize(item)
        assert results[0].body["observed_at"] is None


class TestHasIngredients:
    """DP-028 D4: a presence flag over `ingredients_text`, never null."""

    def test_present_non_blank_text_is_true(self) -> None:
        item = a_snapshot_item(a_row(ingredients_text="aqua, glycerin"))
        _, results = normalize(item)
        assert results[0].body["has_ingredients"] is True

    def test_an_absent_ingredients_text_is_false_not_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "ingredients_text"))
        _, results = normalize(item)
        assert results[0].body["has_ingredients"] is False

    def test_blank_text_is_false(self) -> None:
        item = a_snapshot_item(a_row(ingredients_text="   "))
        _, results = normalize(item)
        assert results[0].body["has_ingredients"] is False

    def test_a_non_string_value_is_false_rather_than_raising(self) -> None:
        item = a_snapshot_item(a_row(ingredients_text=123))
        outcome, results = normalize(item)
        assert outcome.results_emitted == 1
        assert results[0].body["has_ingredients"] is False

    def test_it_is_not_a_quality_judgement(self) -> None:
        """DP-028 D4: presence is not completeness. A short, clearly partial ingredient
        text is still `True` — this add-on does not threshold it."""
        item = a_snapshot_item(a_row(ingredients_text="water"))
        _, results = normalize(item)
        assert results[0].body["has_ingredients"] is True


class TestARowWithNoUsableCodeIsSkipped:
    """DP-028 D3: `code` is never null in the output — a row without one is `skipped` and
    counted rather than being emitted with an invented `external_id`."""

    def test_a_missing_code_is_skipped_and_counted(self) -> None:
        item = a_snapshot_item(drop(a_row(), "code"), item_key="raw-missing-code")
        outcome, results = normalize(item)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []
        assert outcome.notes["skipped_item_keys"] == ("raw-missing-code",)

    def test_a_non_string_code_is_skipped(self) -> None:
        item = a_snapshot_item(a_row(code=8801234567890), item_key="raw-numeric-code")
        outcome, _ = normalize(item)
        assert outcome.skipped == 1

    def test_a_blank_code_is_skipped(self) -> None:
        item = a_snapshot_item(a_row(code="   "), item_key="raw-blank-code")
        outcome, _ = normalize(item)
        assert outcome.skipped == 1

    def test_an_unparseable_payload_is_skipped_and_counted(self) -> None:
        item = SnapshotItem("raw-not-json", b"not json", "application/json")
        outcome, results = normalize(item)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []

    def test_a_json_array_payload_is_skipped_rather_than_mangled(self) -> None:
        item = SnapshotItem("raw-array", b"[1, 2, 3]", "application/json")
        outcome, _ = normalize(item)
        assert outcome.skipped == 1

    def test_a_mixed_snapshot_normalizes_what_it_can(self) -> None:
        """The positive control for every skip case above."""
        good = a_snapshot_item(a_row(code="8800000000123"))
        bad = a_snapshot_item(drop(a_row(), "code"), item_key="raw-bad")
        outcome, results = normalize(good, bad)
        assert (outcome.results_emitted, outcome.skipped) == (1, 1)
        assert len(results) == 1
        assert results[0].source_item_key == "8800000000123"


class TestOutcomeCountsAddUp:
    """Acceptance criterion 5: `results_emitted + skipped == item_count`, asserted so a
    deliberate swap of the two would be caught rather than passing by accident."""

    def test_results_emitted_plus_skipped_equals_the_snapshot_s_item_count(self) -> None:
        items = [
            a_snapshot_item(a_row(code="8800000000001")),
            a_snapshot_item(drop(a_row(), "code"), item_key="raw-bad-1"),
            a_snapshot_item(a_row(code="8800000000002")),
        ]
        outcome, _ = normalize(*items)
        assert outcome.results_emitted + outcome.skipped == len(items)

    def test_the_individual_counts_are_pinned_so_a_swap_of_the_two_is_detectable(self) -> None:
        """The control the sum-equality test above needs: addition commutes, so a handler
        that swapped `results_emitted` and `skipped` when building `NormalizeOutcome` would
        still satisfy the sum test. Pinning the two counts to *different* values here means
        such a swap fails this test even though it would pass the one above."""
        items = [
            a_snapshot_item(a_row(code="8800000000001")),
            a_snapshot_item(a_row(code="8800000000002")),
            a_snapshot_item(drop(a_row(), "code"), item_key="raw-bad-1"),
        ]
        outcome, results = normalize(*items)
        assert outcome.results_emitted == 2
        assert outcome.skipped == 1
        assert outcome.results_emitted != outcome.skipped
        assert len(results) == 2


class TestItIsDeterministic:
    """OQ-003 / DP-019: the same snapshot must produce byte-identical results.

    `[측정]` Verified as a mutation, not only as a passing assertion: with the emission
    loop's `results.append(...)` temporarily changed to `results.insert(0, ...)` — which
    reverses emission order for a multi-item snapshot — `test_the_order_follows_the_snapshot`
    below went red (`AssertionError`, order reversed) while every other test in this class
    stayed green. The change was reverted before this file was finalized; see this add-on's
    task-packet handoff for the exact commands run and their before/after output.
    """

    def test_two_runs_over_one_snapshot_produce_equal_bodies(self) -> None:
        items = [
            a_snapshot_item(a_row(code="8800000000001")),
            a_snapshot_item(a_row(code="8800000000002", product_name="Other Cream")),
        ]
        _, one = normalize(*items)
        _, two = normalize(*items)
        assert [r.body for r in one] == [r.body for r in two]

    def test_the_order_follows_the_snapshot(self) -> None:
        first = a_snapshot_item(a_row(code="8800000000001"))
        second = a_snapshot_item(a_row(code="8800000000002"))
        _, results = normalize(first, second)
        assert [r.source_item_key for r in results] == [first.item_key, second.item_key]

    def test_it_reads_no_clock_and_no_random_source(self) -> None:
        """`NormalizeContext` offers neither, so this is a property of the context rather
        than of the handler — pinned here as the reason the two tests above are expected to
        hold rather than a coincidence of this add-on's particular logic."""
        assert not hasattr(NormalizeContext, "clock")
        assert not hasattr(NormalizeContext, "random")


@pytest.mark.usefixtures("database")
class TestCoexistenceOverOneLineage:
    """Acceptance criterion 6 / DP-019 D3: a `0.3` result stands beside a `0.1` and a `0.2`
    result over one Raw lineage, with no row updated in place.

    Needs a reachable PostgreSQL cluster (`platform_database`'s own fixture skips this class
    cleanly when one is not configured or not reachable) — see this file's module docstring
    for why only this one class needs it.
    """

    def test_a_0_3_result_stands_beside_0_1_and_0_2_over_one_lineage(
        self, connection: psycopg.Connection[Any]
    ) -> None:
        domain = DomainStore(connection)
        source_id = "obf-probe"
        domain.register_source(
            SourceRow(
                source_id=source_id,
                addon_id="importer.local.jsonl",
                addon_version="0.1.0",
                kind="importer",
                config_schema_version="1",
            )
        )
        snapshot_id: UUID = domain.seal_snapshot_from_raw(source_id)

        outcome, results = normalize(a_snapshot_item(a_row(code="8800000000099")))
        assert outcome.results_emitted == 1
        product_body = results[0].body

        document_body: dict[str, Any] = {
            "schema_version": "0.1",
            "record_type": "document",
            "external_id": "https://blog.example.invalid/post-1",
            "url": "https://blog.example.invalid/post-1",
            "title": "제품 후기",
            "excerpt": "본문 일부",
            "published_at": "2026-08-01",
            "author": "someone",
            "language": "ko",
        }
        trend_body: dict[str, Any] = {
            "schema_version": "0.2",
            "record_type": "trend_point",
            "external_id": "수분크림|2026-08-01",
            "language": "ko",
            "series": "수분크림",
            "dimension": "search_keyword",
            "terms": ["수분크림"],
            "period": "2026-08-01",
            "time_unit": "week",
            "ratio": 100.0,
            "segment": {"device": None, "gender": None, "ages": None},
        }

        domain.record_results(
            snapshot_id, source_id, "normalizer.naver.blog", "0.1.0", "0.1",
            [
                NormalizedResultRow(
                    source_item_key="https://blog.example.invalid/post-1",
                    body=document_body,
                )
            ],
        )
        domain.record_results(
            snapshot_id, source_id, "normalizer.naver.trend", "0.1.0", "0.2",
            [NormalizedResultRow(source_item_key="수분크림|2026-08-01", body=trend_body)],
        )
        domain.record_results(
            snapshot_id, source_id, "normalizer.obf.product", "0.1.0", "0.3",
            [NormalizedResultRow(source_item_key="8800000000099", body=product_body)],
        )

        rows = domain.read_results(snapshot_id)
        assert len(rows) == 3, "all three coexist; none replaced another"

        record_types = sorted(row["body"]["record_type"] for row in rows)
        assert record_types == ["document", "product", "trend_point"]

        output_contract_versions = sorted(row["output_contract_version"] for row in rows)
        assert output_contract_versions == ["0.1", "0.2", "0.3"]

        product_rows = [row for row in rows if row["body"]["record_type"] == "product"]
        assert len(product_rows) == 1
        assert product_rows[0]["body"]["schema_version"] == "0.3"
        assert product_rows[0]["source_item_key"] == "8800000000099"
