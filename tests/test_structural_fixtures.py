"""Structural fixtures — DP-022.

The tool under test takes a real captured response and produces a document that has every
structural property the capture had and none of its content. `data-handling.md` refuses to
let redaction create redistribution rights, and this is not redaction: nothing of the
original survives except the *shape*, which is our observation rather than anyone's work.

**The class that decides whether this is worth having** is `TestItPreservesWhatATestAsserts`.
DP-022 D2's falsification condition is "a test that passes against the fixture and fails
against the capture it came from", and the trap is concrete: replacing
`촉촉한 <b>수분크림</b> 후기` with `제품 후기` destroys the markup the blog normalizer's whole
first rule exists for, and the test over it would then pass while proving nothing. So the
markup positions survive and the words between them do not.

The tool lives in `tools/` rather than under `experiments/integrated-p0/` because it is not
disposable P0 code: a rule for turning captures into publishable evidence outlives P0, and
anything under the experiment root is committed to being thrown away with it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools.structural_fixture import (
    RULESET_VERSION,
    derive,
    manifest_for,
    shape_of,
)

# --------------------------------------------------------------------------- #
# The two real response shapes, as the vendor documents them
# --------------------------------------------------------------------------- #

BLOG_CAPTURE: dict[str, Any] = {
    "lastBuildDate": "Tue, 19 Aug 2026 00:28:22 +0900",
    "total": 1284003,
    "start": 1,
    "display": 2,
    "items": [
        {
            "title": "이플미 스킨 끈적이지 않는 촉촉한 <b>수분크림</b> 사용 후기",
            "link": "https://blog.naver.com/cvplmfdsqjz/224382729706",
            "description": "&quot;발림성&quot;이 좋고 <b>수분감</b>이 오래갑니다",
            "bloggername": "Jelly",
            "bloggerlink": "https://blog.naver.com/cvplmfdsqjz",
            "postdate": "20260818",
        },
        {
            "title": "홀츠포맨 남자 올인원 <b>수분크림</b> 420ml",
            "link": "https://blog.naver.com/emxb6euweiqx/224382744927",
            "description": "초보도 쉽게 다룰 수 있는 주름 관리",
            "bloggername": "결국엉뚱록",
            "bloggerlink": "https://blog.naver.com/emxb6euweiqx",
            "postdate": "20260818",
        },
    ],
}

TREND_CAPTURE: dict[str, Any] = {
    "startDate": "2026-07-01",
    "endDate": "2026-08-15",
    "timeUnit": "week",
    "results": [
        {
            "title": "수분크림",
            "keywords": ["수분크림"],
            "data": [
                {"period": "2026-06-29", "ratio": 96.10965},
                {"period": "2026-07-06", "ratio": 100},
            ],
        }
    ],
}


def derived(capture: dict[str, Any]) -> dict[str, Any]:
    parsed: dict[str, Any] = json.loads(derive(json.dumps(capture, ensure_ascii=False).encode()))
    return parsed


# --------------------------------------------------------------------------- #


class TestNothingOfTheOriginalSurvives:
    """The property that makes this publishable at all."""

    def test_no_title_no_excerpt_and_no_author_survives(self) -> None:
        text = json.dumps(derived(BLOG_CAPTURE), ensure_ascii=False)
        for original in ("이플미", "홀츠포맨", "발림성", "Jelly", "결국엉뚱록", "주름 관리"):
            assert original not in text, f"{original!r} survived into the fixture"

    def test_no_real_url_path_survives(self) -> None:
        """A blog URL identifies a person's blog and one of their posts."""
        text = json.dumps(derived(BLOG_CAPTURE), ensure_ascii=False)
        for original in ("cvplmfdsqjz", "emxb6euweiqx", "224382729706", "blog.naver.com"):
            assert original not in text

    def test_the_query_terms_we_sent_do_not_survive_either(self) -> None:
        """Our own search term is still the operator's business, and a fixture that leaked
        it would make every capture's fixture say what was being investigated."""
        text = json.dumps(derived(TREND_CAPTURE), ensure_ascii=False)
        assert "수분크림" not in text

    def test_numeric_magnitudes_do_not_survive(self) -> None:
        """A `total` of 1,284,003 and a ratio of 96.10965 are observations about the
        provider's index. The *types* are what a test asserts on; the values are not ours."""
        text = json.dumps(derived(BLOG_CAPTURE))
        assert "1284003" not in text
        assert "96.10965" not in json.dumps(derived(TREND_CAPTURE))


class TestItPreservesWhatATestAsserts:
    """DP-022 D2. Its falsification condition is a test that passes against the fixture and
    fails against the capture, so the strongest check available is to compare the two
    *shapes* directly — `shape_of` is what a test can see, and it must be identical."""

    @pytest.mark.parametrize(
        "capture", [BLOG_CAPTURE, TREND_CAPTURE], ids=["blog", "trend"]
    )
    def test_the_shape_is_identical(self, capture: dict[str, Any]) -> None:
        assert shape_of(capture) == shape_of(derived(capture))

    def test_markup_survives_because_a_rule_depends_on_it(self) -> None:
        """`normalizer.naver.blog`'s first rule strips `<b>`. A fixture without the tags
        would let that rule's test pass against nothing."""
        for item in derived(BLOG_CAPTURE)["items"]:
            assert "<b>" in item["title"] and "</b>" in item["title"]

    def test_entities_survive_because_the_same_rule_decodes_them(self) -> None:
        assert "&quot;" in derived(BLOG_CAPTURE)["items"][0]["description"]

    def test_an_item_without_markup_stays_without_markup(self) -> None:
        """The control. Preserving markup must not mean *adding* it — the second item's
        description has none, and a fixture that gave it some would invent an edge case."""
        assert "<b>" not in derived(BLOG_CAPTURE)["items"][1]["description"]

    def test_the_date_format_survives_because_the_second_rule_parses_it(self) -> None:
        """`postdate` is `yyyymmdd`. The parser refuses anything else, so the format is the
        property and the date is not."""
        for item in derived(BLOG_CAPTURE)["items"]:
            assert len(item["postdate"]) == 8
            assert item["postdate"].isdigit()

    def test_the_iso_date_format_survives_separately(self) -> None:
        """DataLab uses `yyyy-mm-dd`. Two date formats, two shape classes, and a tool that
        collapsed them would make one of the two collectors untestable."""
        assert derived(TREND_CAPTURE)["startDate"].count("-") == 2
        assert len(derived(TREND_CAPTURE)["results"][0]["data"][0]["period"]) == 10

    def test_the_int_float_distinction_survives(self) -> None:
        """`[측정]` The real API returned `ratio: 100` as an int and `96.10965` as a float in
        one response. The normalizer accepts both; a fixture that normalised them would stop
        testing that."""
        points = derived(TREND_CAPTURE)["results"][0]["data"]
        assert isinstance(points[0]["ratio"], float)
        assert isinstance(points[1]["ratio"], int) and not isinstance(points[1]["ratio"], bool)

    def test_a_url_stays_a_url_of_the_same_depth(self) -> None:
        """The collector keys items on `link`, so it must still be a usable absolute URL —
        and the path depth is what tells a reader it addresses a post rather than a blog."""
        item = derived(BLOG_CAPTURE)["items"][0]
        assert item["link"].startswith("https://")
        assert item["link"].count("/") == BLOG_CAPTURE["items"][0]["link"].count("/")

    def test_array_lengths_survive(self) -> None:
        assert len(derived(BLOG_CAPTURE)["items"]) == 2
        assert len(derived(TREND_CAPTURE)["results"][0]["data"]) == 2

    def test_key_order_survives(self) -> None:
        """Not asserted on by any current test, and preserved anyway: a reader comparing a
        fixture to the vendor's documentation reads them in order."""
        assert list(derived(BLOG_CAPTURE)["items"][0]) == list(BLOG_CAPTURE["items"][0])


class TestTheDerivationIsDeterministic:
    """DP-022 D3. A fixture nobody can re-derive is an assertion nobody can re-check."""

    def test_two_runs_over_one_capture_agree_byte_for_byte(self) -> None:
        raw = json.dumps(BLOG_CAPTURE, ensure_ascii=False).encode("utf-8")
        assert derive(raw) == derive(raw)

    def test_a_different_capture_produces_a_different_fixture(self) -> None:
        """The control. A deriver that returned a constant would pass the test above."""
        assert derive(json.dumps(BLOG_CAPTURE).encode()) != derive(
            json.dumps(TREND_CAPTURE).encode()
        )

    def test_one_changed_character_changes_the_fixture(self) -> None:
        """Substitution is keyed on the input, so the fixture tracks the capture rather than
        being one of a handful of canned outputs."""
        altered = json.loads(json.dumps(BLOG_CAPTURE))
        altered["items"][0]["bloggername"] = "Jellz"
        assert derive(json.dumps(BLOG_CAPTURE).encode()) != derive(
            json.dumps(altered, ensure_ascii=False).encode()
        )

    def test_equal_inputs_in_different_places_get_equal_substitutes(self) -> None:
        """Both items carry the same `postdate`. Keeping equal things equal preserves a
        property a test could assert on — that two posts share a date."""
        items = derived(BLOG_CAPTURE)["items"]
        assert items[0]["postdate"] == items[1]["postdate"]


class TestTheManifest:
    """DP-022 D4 and D5. Without the original's digest a structural fixture is
    indistinguishable from something invented, and inventing one is what it replaces."""

    def test_it_records_the_digest_of_the_capture_it_came_from(self) -> None:
        raw = json.dumps(BLOG_CAPTURE, ensure_ascii=False).encode("utf-8")
        manifest = manifest_for(
            raw,
            endpoint="https://naverapihub.apigw.ntruss.com/search/v1/blog",
            captured_at="2026-08-19T00:28:22+09:00",
            represents=["one page of results"],
            does_not_represent=["a 429", "an empty result set"],
        )
        assert manifest["original_sha256"] == __import__("hashlib").sha256(raw).hexdigest()

    def test_it_records_its_own_digest_and_the_ruleset(self) -> None:
        raw = json.dumps(TREND_CAPTURE, ensure_ascii=False).encode("utf-8")
        manifest = manifest_for(
            raw, endpoint="e", captured_at="t", represents=[], does_not_represent=[]
        )
        assert manifest["fixture_sha256"] == __import__("hashlib").sha256(
            derive(raw)
        ).hexdigest()
        assert manifest["ruleset_version"] == RULESET_VERSION

    def test_it_carries_what_the_sample_does_not_represent(self) -> None:
        """`data-handling.md` requires this of any promoted fixture, and D5 puts it here."""
        manifest = manifest_for(
            json.dumps(TREND_CAPTURE).encode(),
            endpoint="e",
            captured_at="t",
            represents=["one weekly window"],
            does_not_represent=["a rate limit response"],
        )
        assert manifest["does_not_represent"] == ["a rate limit response"]

    def test_the_manifest_carries_no_content_either(self) -> None:
        """A manifest that quoted the capture to describe it would put the content back."""
        raw = json.dumps(BLOG_CAPTURE, ensure_ascii=False).encode("utf-8")
        rendered = json.dumps(
            manifest_for(
                raw, endpoint="e", captured_at="t", represents=[], does_not_represent=[]
            ),
            ensure_ascii=False,
        )
        for original in ("이플미", "Jelly", "cvplmfdsqjz"):
            assert original not in rendered


class TestShapeOf:
    """`shape_of` is the comparison the whole packet rests on, so it is tested directly
    rather than only through the fixtures it validates."""

    def test_it_ignores_string_content(self) -> None:
        assert shape_of({"a": "hello"}) == shape_of({"a": "world"})

    def test_it_does_not_ignore_markup(self) -> None:
        assert shape_of({"a": "x <b>y</b>"}) != shape_of({"a": "xy"})

    def test_it_does_not_ignore_the_int_float_distinction(self) -> None:
        assert shape_of({"a": 1}) != shape_of({"a": 1.0})

    def test_it_does_not_ignore_null_versus_empty(self) -> None:
        assert shape_of({"a": None}) != shape_of({"a": ""})

    def test_it_does_not_ignore_an_absent_key(self) -> None:
        assert shape_of({"a": 1, "b": 2}) != shape_of({"a": 1})

    def test_it_does_not_ignore_array_length(self) -> None:
        assert shape_of({"a": [1, 2]}) != shape_of({"a": [1]})

    def test_it_does_not_ignore_date_format_class(self) -> None:
        assert shape_of({"a": "20260818"}) != shape_of({"a": "2026-08-18"})
