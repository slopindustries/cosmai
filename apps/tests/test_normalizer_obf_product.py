"""`normalizer.obf.product` — Open Beauty Facts rows into `Normalized Schema 0.3` `product`
records (DP-028, TASK-008).

Copy-adapted from ``experiments/integrated-p0/tests/test_normalizer_obf_product.py`` (M4).
Fixture names follow this tree's convention: ``job_connection`` for P0's ``connection``. The
scenarios below are the P0 originals plus this tree's own repairs of five weak assertions
``docs/architecture-synthesis/P1-INHERITED-DEFECTS.md`` §3 named (sourced in full detail from
``experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-OBF-PRODUCT.md`` F2-F6), plus new
coverage for this tree's own addition, ``_build_body``'s DP-030 D2 per-field fallback:

- **F2 repaired** — `TestTheEnvelopeAndTheRecord`'s old lineage test used to build its
  snapshot item with `item_key` defaulted from `code`, so `source_item_key == code` held
  even for a handler that used the wrong one of the two.
  `test_source_item_key_traces_to_the_snapshot_item_key_even_when_it_differs_from_the_code`
  below uses a snapshot item whose `item_key` is deliberately unequal to its row's `code`, so
  the two assertions can no longer be satisfied by the same coincidence.
- **F3 not repaired, and said so where a reader will look** — `TestCoexistenceOverOneLineage`'s
  own docstring below states plainly that "no row updated in place" is unfalsifiable through
  `DomainStore`, because no UPDATE path exists to fail it. Turning this into a real assertion
  needs a store-level UPDATE method nothing in this codebase has a reason to add; recorded as
  left, not silently dropped.
- **F4 repaired** — the `[가설]` for a blank-after-trim `code` is now on
  `test_a_blank_code_is_skipped` itself, not only in `handler.py`'s module docstring, and the
  class docstring no longer lets a reader think DP-028 D3 settles it. The `[가설]` for rejecting
  a numeric-looking string is now on `test_a_numeric_looking_string_also_abstains` — the case
  that actually needs it — rather than only on the uncontested non-numeric case beside it. The
  ISO literal's `Z`-suffix choice is now named as a `[가설]` on
  `test_a_unix_seconds_value_converts_to_iso_8601_utc`, where P0 left it unlabelled anywhere.
- **F5 repaired** — the `skipped_item_keys` assertions now compare through `tuple(...)` rather
  than pinning the in-process container type a JSON round trip does not preserve (P0's own
  measurement: `to_json` turns the tuple into a `list`), and the two previously-untested
  `notes` keys (`schema_version`, `language`) now have their own assertions.
- **F6 repaired** — `normalize()` below now captures every `context.log` call instead of
  discarding it, and `TestARowWithNoUsableCodeIsSkipped` gains a case asserting the two skip
  *reasons* are actually distinguished, which is what P0's mutant `M24` (making the
  not-an-object path report "no usable code" instead) would now kill.
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

pytestmark = pytest.mark.usefixtures("_migrations_applied")

ADDON_ROOT = Path(__file__).resolve().parents[1] / "addons" / "normalizer.obf.product"


def load_module() -> Any:
    """A fresh copy of the handler module, isolated per call.

    `normalize()` below calls this once per invocation rather than caching a module-level
    import, so one test's monkeypatch of a helper function (`TestPerRecordFallback`) can
    never leak into another test's run.
    """
    spec = importlib.util.spec_from_file_location(
        "normalizer_obf_product_under_test", ADDON_ROOT / "handler.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_entry() -> Any:
    return load_module().run


def a_row(**overrides: Any) -> dict[str, Any]:
    """One structurally plausible Open Beauty Facts row. No field's *value* is real; every
    field's *shape* — type, nesting, and which fields co-occur — is what SRC-003 measured.
    DP-022: a structural fixture, not a captured row."""
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
) -> tuple[NormalizeOutcome, list[NormalizedResult], list[tuple[str, dict[str, Any]]]]:
    """Run the handler once and return its outcome, its emitted results, and every
    `context.log` call it made — F6's repair needs the log calls; P0's version discarded
    them with `log=lambda event, fields: None`."""
    emitted: list[NormalizedResult] = []
    logged: list[tuple[str, dict[str, Any]]] = []
    context = NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config=config if config is not None else {},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: logged.append((event, dict(fields))),
    )
    return load_entry()(context), emitted, logged


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
        _, results, _ = normalize(a_snapshot_item())
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
        _, results, _ = normalize(a_snapshot_item())
        assert results[0].body["schema_version"] == "0.3"
        assert results[0].body["record_type"] == "product"

    def test_the_external_id_is_the_code_and_matches_the_lineage_key(self) -> None:
        _, results, _ = normalize(a_snapshot_item(a_row(code="8800000000017")))
        assert results[0].body["external_id"] == "8800000000017"
        assert results[0].source_item_key == "8800000000017"

    def test_source_item_key_traces_to_the_snapshot_item_key_even_when_it_differs_from_the_code(
        self,
    ) -> None:
        """F2's repair. P0's own version of this test always built its snapshot item with
        `item_key` defaulted from `code`, so `source_item_key == code` held whether the
        handler used `item.item_key` (the contract's own lineage requirement — DP-028's
        acceptance criterion 2, *"source_item_key traces to the sealed item"*) or the
        `external_id` it had just computed from `code`. `addon_host._check_lineage`
        enforces the correct one at runtime, but nothing in this file exercised the two
        cases as distinct until now: `item_key` and `code` differ here on purpose, so a
        handler that used `external_id` for `source_item_key` fails this assertion while a
        handler that used `item.item_key` (the one this add-on actually uses) passes it.
        """
        item = a_snapshot_item(a_row(code="8800000000099"), item_key="raw-item-42")
        _, results, _ = normalize(item)
        assert results[0].source_item_key == "raw-item-42"
        assert results[0].body["external_id"] == "8800000000099"

    def test_language_is_configuration_and_not_detection(self) -> None:
        """DP-019 D2. `[측정]` DP-028 records 0/36 Korean rows carrying `product_name_ko`
        and no Hangul in any sampled `product_name`, which is why `en` is the *default* and
        not the *only* legal value — a run can still be configured otherwise."""
        _, results, _ = normalize(a_snapshot_item(), config={"language": "ko"})
        assert results[0].body["language"] == "ko"

    def test_language_defaults_to_en(self) -> None:
        _, results, _ = normalize(a_snapshot_item(), config={})
        assert results[0].body["language"] == "en"

    def test_a_blank_configured_language_falls_back_to_the_default(self) -> None:
        _, results, _ = normalize(a_snapshot_item(), config={"language": "   "})
        assert results[0].body["language"] == "en"


class TestNoProductIdentityWork:
    """DP-028 D5 and the packet's stopping condition: no category, no ingredient taxonomy,
    no resolved brand. This is the positive-control counterpart of every "field X is
    present" assertion above — a body that additionally carried one of these would still
    pass every other test in this file, so it needs its own."""

    def test_no_category_ingredient_taxonomy_or_resolved_brand_field_exists(self) -> None:
        _, results, _ = normalize(a_snapshot_item())
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
        _, results, _ = normalize(item)
        assert results[0].body["display_name"] == "  Example Whitening Cream  "

    def test_an_absent_product_name_abstains_to_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "product_name"))
        _, results, _ = normalize(item)
        assert results[0].body["display_name"] is None

    def test_an_empty_string_abstains_to_null(self) -> None:
        item = a_snapshot_item(a_row(product_name=""))
        _, results, _ = normalize(item)
        assert results[0].body["display_name"] is None

    def test_a_whitespace_only_string_abstains_to_null(self) -> None:
        item = a_snapshot_item(a_row(product_name="   "))
        _, results, _ = normalize(item)
        assert results[0].body["display_name"] is None

    def test_a_non_string_product_name_abstains_to_null_rather_than_raising(self) -> None:
        item = a_snapshot_item(a_row(product_name=12345))
        outcome, results, _ = normalize(item)
        assert outcome.results_emitted == 1
        assert results[0].body["display_name"] is None


class TestBrands:
    """DP-028 D3: `brands_tags`, order preserved, never null — `[]` when the source has
    none."""

    def test_order_is_preserved_exactly_as_the_source_sent_it(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=["zzz-brand", "aaa-brand", "mmm-brand"]))
        _, results, _ = normalize(item)
        assert results[0].body["brands"] == ["zzz-brand", "aaa-brand", "mmm-brand"]

    def test_an_absent_brands_tags_is_an_empty_list_not_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "brands_tags"))
        _, results, _ = normalize(item)
        assert results[0].body["brands"] == []

    def test_an_empty_brands_tags_stays_an_empty_list(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=[]))
        _, results, _ = normalize(item)
        assert results[0].body["brands"] == []

    def test_a_single_brand_survives_as_a_one_element_list(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=["solo-brand"]))
        _, results, _ = normalize(item)
        assert results[0].body["brands"] == ["solo-brand"]


class TestObservedAt:
    """DP-028 D3: `last_modified_t`, Unix seconds to ISO-8601 UTC, null when the source
    omits it. Acceptance criterion: a non-numeric value abstains rather than raising."""

    def test_a_unix_seconds_value_converts_to_iso_8601_utc(self) -> None:
        """`[가설]` pinned here (F4 gap 4, unlabelled in P0): DP-028 D3 says only "Unix
        seconds -> ISO-8601 UTC", and `moment.isoformat()` (`2025-01-01T00:00:00+00:00`) is
        equally valid ISO-8601 UTC. The `Z`-suffix literal below is this add-on's own
        choice, not something D3 fixes. Falsified by an owner ruling that normalized
        timestamps should use the offset form instead."""
        item = a_snapshot_item(a_row(last_modified_t=1735689600))
        _, results, _ = normalize(item)
        assert results[0].body["observed_at"] == "2025-01-01T00:00:00Z"

    def test_a_float_unix_seconds_value_also_converts(self) -> None:
        item = a_snapshot_item(a_row(last_modified_t=1735689600.0))
        _, results, _ = normalize(item)
        assert results[0].body["observed_at"] == "2025-01-01T00:00:00Z"

    def test_an_absent_last_modified_t_abstains_to_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "last_modified_t"))
        _, results, _ = normalize(item)
        assert results[0].body["observed_at"] is None

    def test_a_non_numeric_value_abstains_rather_than_raising(self) -> None:
        item = a_snapshot_item(a_row(last_modified_t="not-a-number"))
        outcome, results, _ = normalize(item)
        assert outcome.results_emitted == 1
        assert results[0].body["observed_at"] is None

    def test_a_numeric_looking_string_also_abstains(self) -> None:
        """`[가설]` pinned here (F4 gap 3's repair): P0 pinned this reading's falsification
        condition on the *uncontested* case above (`"not-a-number"`) instead of on this one,
        the case that actually needs it. "Non-numeric" means anything that is not a JSON
        `int` or `float`, including a numeric-looking string — SRC-003 measured
        `last_modified_t` as a JSON number in every sampled row and never as a string.
        Falsified by a real capture carrying it as a string that the project decides should
        still convert."""
        item = a_snapshot_item(a_row(last_modified_t="1735689600"))
        _, results, _ = normalize(item)
        assert results[0].body["observed_at"] is None

    def test_a_boolean_is_not_treated_as_a_numeric_timestamp(self) -> None:
        """`bool` is an `int` subclass in Python; a timestamp of `True` would be a type
        checker's blind spot rather than an observation."""
        item = a_snapshot_item(a_row(last_modified_t=True))
        _, results, _ = normalize(item)
        assert results[0].body["observed_at"] is None


class TestHasIngredients:
    """DP-028 D4: a presence flag over `ingredients_text`, never null."""

    def test_present_non_blank_text_is_true(self) -> None:
        item = a_snapshot_item(a_row(ingredients_text="aqua, glycerin"))
        _, results, _ = normalize(item)
        assert results[0].body["has_ingredients"] is True

    def test_an_absent_ingredients_text_is_false_not_null(self) -> None:
        item = a_snapshot_item(drop(a_row(), "ingredients_text"))
        _, results, _ = normalize(item)
        assert results[0].body["has_ingredients"] is False

    def test_blank_text_is_false(self) -> None:
        item = a_snapshot_item(a_row(ingredients_text="   "))
        _, results, _ = normalize(item)
        assert results[0].body["has_ingredients"] is False

    def test_a_non_string_value_is_false_rather_than_raising(self) -> None:
        item = a_snapshot_item(a_row(ingredients_text=123))
        outcome, results, _ = normalize(item)
        assert outcome.results_emitted == 1
        assert results[0].body["has_ingredients"] is False

    def test_it_is_not_a_quality_judgement(self) -> None:
        """DP-028 D4: presence is not completeness. A short, clearly partial ingredient
        text is still `True` — this add-on does not threshold it."""
        item = a_snapshot_item(a_row(ingredients_text="water"))
        _, results, _ = normalize(item)
        assert results[0].body["has_ingredients"] is True


class TestARowWithNoUsableCodeIsSkipped:
    """DP-028 D3: `code` is never null in the output — a row without one is `skipped` and
    counted rather than being emitted with an invented `external_id`.

    `[가설]` A blank-after-trim `code` is treated the same as an absent one, mirroring the
    rule DP-028 states for `display_name`, even though D3's `code` row only says "never" for
    the null case and does not mention blank strings by name — that extension is this
    add-on's own reading, not something DP-028 D3 itself settles (F4 gap 2's repair: P0's
    version of this class docstring cited D3 as the authority for every case below,
    including this one, which a reader would then wrongly take as a `[결정]`). Falsified by
    an owner ruling that a whitespace-only `code` should be carried through as `external_id`
    rather than skipped.
    """

    def test_a_missing_code_is_skipped_and_counted(self) -> None:
        item = a_snapshot_item(drop(a_row(), "code"), item_key="raw-missing-code")
        outcome, results, _ = normalize(item)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []
        assert tuple(outcome.notes["skipped_item_keys"]) == ("raw-missing-code",)

    def test_a_non_string_code_is_skipped(self) -> None:
        item = a_snapshot_item(a_row(code=8801234567890), item_key="raw-numeric-code")
        outcome, _, _ = normalize(item)
        assert outcome.skipped == 1

    def test_a_blank_code_is_skipped(self) -> None:
        item = a_snapshot_item(a_row(code="   "), item_key="raw-blank-code")
        outcome, _, _ = normalize(item)
        assert outcome.skipped == 1

    def test_an_unparseable_payload_is_skipped_and_counted(self) -> None:
        item = SnapshotItem("raw-not-json", b"not json", "application/json")
        outcome, results, _ = normalize(item)
        assert (outcome.results_emitted, outcome.skipped) == (0, 1)
        assert results == []

    def test_a_json_array_payload_is_skipped_rather_than_mangled(self) -> None:
        item = SnapshotItem("raw-array", b"[1, 2, 3]", "application/json")
        outcome, _, _ = normalize(item)
        assert outcome.skipped == 1

    def test_a_mixed_snapshot_normalizes_what_it_can(self) -> None:
        """The positive control for every skip case above."""
        good = a_snapshot_item(a_row(code="8800000000123"))
        bad = a_snapshot_item(drop(a_row(), "code"), item_key="raw-bad")
        outcome, results, _ = normalize(good, bad)
        assert (outcome.results_emitted, outcome.skipped) == (1, 1)
        assert len(results) == 1
        assert results[0].source_item_key == "8800000000123"

    def test_the_two_skip_reasons_are_actually_distinguished(self) -> None:
        """F6's repair. P0's mutant `M24` (`_parse` returning `{}` instead of `None` for a
        payload that parses but is not an object) survived all 41 of P0's tests: the row
        was still skipped and counted correctly, but through the "no usable code" branch
        rather than the "payload is not a JSON object" branch, and nothing asserted on the
        *reason* a `normalize.skipped` log line carried. This test would kill that mutant:
        it names the two rows by their distinct `item_key`s and checks each one's logged
        reason separately, not merely that both were skipped."""
        not_an_object = SnapshotItem("raw-not-object", b"[1, 2, 3]", "application/json")
        no_code = a_snapshot_item(drop(a_row(), "code"), item_key="raw-no-code")

        _, _, logged = normalize(not_an_object, no_code)

        reasons = {
            fields["item_key"]: fields["reason"]
            for event, fields in logged
            if event == "normalize.skipped"
        }
        assert reasons["raw-not-object"] == "payload is not a JSON object"
        assert reasons["raw-no-code"] == "no usable code"
        assert reasons["raw-not-object"] != reasons["raw-no-code"]


class TestOutcomeCountsAddUp:
    """Acceptance criterion 5: `results_emitted + skipped == item_count`, asserted so a
    deliberate swap of the two would be caught rather than passing by accident."""

    def test_results_emitted_plus_skipped_equals_the_snapshot_s_item_count(self) -> None:
        items = [
            a_snapshot_item(a_row(code="8800000000001")),
            a_snapshot_item(drop(a_row(), "code"), item_key="raw-bad-1"),
            a_snapshot_item(a_row(code="8800000000002")),
        ]
        outcome, _, _ = normalize(*items)
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
        outcome, results, _ = normalize(*items)
        assert outcome.results_emitted == 2
        assert outcome.skipped == 1
        assert outcome.results_emitted != outcome.skipped
        assert len(results) == 2


class TestOutcomeNotesAreComplete:
    """F5's repair. P0's mutant `M26` (removing `"schema_version"` and `"language"` from
    `notes` entirely) survived all 41 of P0's tests, because only `skipped_item_keys` was
    ever asserted. Both keys get their own assertion here."""

    def test_notes_carries_schema_version_and_language_alongside_skipped_item_keys(self) -> None:
        item = a_snapshot_item(drop(a_row(), "code"), item_key="raw-bad")
        outcome, _, _ = normalize(item, config={"language": "ko"})
        assert outcome.notes["schema_version"] == "0.3"
        assert outcome.notes["language"] == "ko"
        assert tuple(outcome.notes["skipped_item_keys"]) == ("raw-bad",)

    def test_skipped_item_keys_survives_a_json_round_trip_as_a_list(self) -> None:
        """F5's own measurement: `NormalizeOutcome.to_json()` -> JSON -> `from_json` turns
        the in-process `tuple` into a `list`. Asserted directly here — through the
        contract's own serialization pair, not by inspection — so this add-on's tests do not
        pin a container type the wire form does not preserve."""
        item = a_snapshot_item(drop(a_row(), "code"), item_key="raw-bad")
        outcome, _, _ = normalize(item)
        wire = NormalizeOutcome.from_json(json.loads(json.dumps(outcome.to_json())))
        assert wire.notes["skipped_item_keys"] == ["raw-bad"]


#: A `brands_tags` value that only ever exists inside this test class, so the substitute
#: `_brands` below can trigger on it without changing behaviour for every other test in this
#: file.
_TRIGGER_BRANDS = ["__trigger_normalize_error__"]


def _broken_brands(value: object) -> list[str]:
    """A drop-in `_brands` that fails exactly for `_TRIGGER_BRANDS`, otherwise behaves like
    the real one. Used by `TestPerRecordFallback` in place of a genuinely unanticipated
    failure — see that class's own docstring for why one cannot be produced honestly."""
    if value == _TRIGGER_BRANDS:
        raise RuntimeError("simulated failure: no shape DP-028 or this add-on's tests produce")
    if not isinstance(value, list):
        return []
    return [str(entry) for entry in value]


def normalize_with_broken_brands(
    *items: SnapshotItem,
) -> tuple[NormalizeOutcome, list[NormalizedResult], list[tuple[str, dict[str, Any]]]]:
    """`normalize()`'s shape, over a module whose `_brands` is replaced by
    `_broken_brands` before `run` is called."""
    module = load_module()
    module._brands = _broken_brands
    emitted: list[NormalizedResult] = []
    logged: list[tuple[str, dict[str, Any]]] = []
    context = NormalizeContext(
        run_id="run-1",
        snapshot_id="snap-1",
        config={},
        read_snapshot=lambda: iter(items),
        emit_result=emitted.extend,
        log=lambda event, fields: logged.append((event, dict(fields))),
    )
    return module.run(context), emitted, logged


class TestPerRecordFallback:
    """DP-030 D2, this tree's own addition over P0: an unexpected failure in one field's
    extraction does not abort the run or drop the record.

    **Why this is exercised by substitution rather than by a malformed row.** Every field
    this add-on reads comes from `json.loads`, so a row can only ever carry the handful of
    types JSON has — `str`, `int`, `float`, `bool`, `None`, `list`, `dict` — and Python's
    `str()` never raises on any of them. There is therefore no snapshot payload that can
    make `_brands`'s `str(entry)` call — or any of the other three field helpers, all of
    which are already total over every JSON-decoded shape (see `TestDisplayName`,
    `TestBrands`, `TestObservedAt`, `TestHasIngredients` above) — raise through the ordinary
    JSON pipeline. DP-030 D2's fallback exists for exactly that gap: a failure neither DP-028
    nor this add-on's own abstain logic anticipated. Reaching it honestly means simulating
    one: `_broken_brands` above stands in for `_brands`, raising only for one sentinel value
    (`_TRIGGER_BRANDS`) so every other row in a run is unaffected, exactly as a real,
    unanticipated bug in one helper would leave the other three alone.
    """

    def test_a_field_that_raises_gets_its_own_abstain_default_and_the_row_still_emits(
        self,
    ) -> None:
        row = a_row(brands_tags=_TRIGGER_BRANDS)
        item = a_snapshot_item(row, item_key="raw-triggered")

        outcome, results, _ = normalize_with_broken_brands(item)

        assert outcome.results_emitted == 1
        assert outcome.skipped == 0
        assert results[0].body["brands"] == []
        assert results[0].body["display_name"] == row["product_name"]

    def test_the_failure_is_named_in_notes_normalize_error(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=_TRIGGER_BRANDS), item_key="raw-x")

        _, results, _ = normalize_with_broken_brands(item)

        error = results[0].notes["normalize_error"]
        assert error["field"] == "brands"
        assert "simulated failure" in error["reason"]

    def test_the_outcome_counts_only_the_error_record(self) -> None:
        """The positive control: a good row in the same run must not be counted as an
        error just because another row in it was."""
        good = a_snapshot_item(a_row(code="8800000000777"))
        bad = a_snapshot_item(a_row(brands_tags=_TRIGGER_BRANDS), item_key="raw-y")

        outcome, results, _ = normalize_with_broken_brands(good, bad)

        assert outcome.results_emitted == 2
        assert outcome.notes["normalize_error_count"] == 1
        assert len(results) == 2
        good_result = next(r for r in results if r.source_item_key != "raw-y")
        assert good_result.notes == {}

    def test_an_ordinary_run_reports_zero_normalize_errors(self) -> None:
        """The control: a run with nothing wrong reports the counter at zero rather than
        omitting it, so a reader can trust its absence-of-error meaning."""
        outcome, _, _ = normalize(a_snapshot_item())
        assert outcome.notes["normalize_error_count"] == 0

    def test_a_record_error_is_logged(self) -> None:
        item = a_snapshot_item(a_row(brands_tags=_TRIGGER_BRANDS), item_key="raw-z")

        _, _, logged = normalize_with_broken_brands(item)

        record_errors = [fields for event, fields in logged if event == "normalize.record_error"]
        assert len(record_errors) == 1
        assert record_errors[0]["item_key"] == "raw-z"
        assert record_errors[0]["field"] == "brands"


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
        _, one, _ = normalize(*items)
        _, two, _ = normalize(*items)
        assert [r.body for r in one] == [r.body for r in two]

    def test_the_order_follows_the_snapshot(self) -> None:
        first = a_snapshot_item(a_row(code="8800000000001"))
        second = a_snapshot_item(a_row(code="8800000000002"))
        _, results, _ = normalize(first, second)
        assert [r.source_item_key for r in results] == [first.item_key, second.item_key]

    def test_it_reads_no_clock_and_no_random_source(self) -> None:
        """`NormalizeContext` offers neither, so this is a property of the context rather
        than of the handler — pinned here as the reason the two tests above are expected to
        hold rather than a coincidence of this add-on's particular logic."""
        assert not hasattr(NormalizeContext, "clock")
        assert not hasattr(NormalizeContext, "random")


class TestCoexistenceOverOneLineage:
    """Acceptance criterion 6 / DP-019 D3: a `0.3` result stands beside a `0.1` and a `0.2`
    result over one Raw lineage, with no row updated in place.

    `[측정]` **F3, recorded rather than repaired.** The assertion below cannot go red for
    "no row updated in place": `DomainStore.record_results` has no UPDATE path at all, so a
    collision is structurally impossible to construct through this store, and the property
    this class's own name promises is proven by `0003_normalized_result.sql`'s absent-UPDATE
    design and its unique index — not by anything this test can be made to assert. Turning
    it into a real assertion would need a store-level UPDATE method nothing else in this
    codebase has a reason to add; a reader relying on this class for that guarantee should
    read the migration and the unique index instead of this test.

    P0's version of this class carried `pytest.mark.usefixtures("database")`, a fixture
    named after P0's per-test cloned database (this file's own module docstring explains the
    rename). This tree has no fixture under that name; the class-level marker is dropped
    rather than pointed at a fixture that does not exist, because `job_connection` — the
    parameter the one test below already asks for — already depends on `_migrations_applied`
    through its own fixture chain (`tests/conftest.py`), so a run without a reachable
    PostgreSQL cluster still fails the same way every other DB-backed test in this suite does.
    """

    def test_a_0_3_result_stands_beside_0_1_and_0_2_over_one_lineage(
        self, job_connection: psycopg.Connection[Any]
    ) -> None:
        domain = DomainStore(job_connection)
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

        outcome, results, _ = normalize(a_snapshot_item(a_row(code="8800000000099")))
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
