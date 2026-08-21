"""The helpers several add-ons implement identically, checked in every copy.

Copy-adapted from ``experiments/integrated-p0/tests/test_addon_duplicated_helpers.py`` (M4),
pointed at this tree's own ``apps/addons`` rather than P0's experiment tree.

`[결정]` [OQ-013](../../../docs/open-questions/OQ-013-addon-responsibility-boundary.md)
records the duplication as an accepted cost rather than removing it: an add-on may import
`addon_api` and nothing else, so source-independent plumbing is written once per add-on by
rule. What the question does **not** accept is testing one copy and assuming the others.

`[측정]` `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5 measured the consequence:
`_MONTH_LENGTH` is duplicated between the two DataLab collectors and making February accept
31 days was **GREEN in both**. Nothing outside an add-on knows how long February is, so
nothing outside the add-on can notice — which is the second clause of OQ-013 in miniature.

`[측정]` **M4 lane note.** This worktree installs only the two add-ons M4's importer/OBF
task builds — `importer.local.jsonl` and `normalizer.obf.product`. Neither declares
`_day_after`; that helper belongs to the NAVER DataLab collectors, each built in its own
parallel M4 worktree this one cannot see. Ported here anyway, pointed at `apps/addons/`
directly rather than left out, so the scan exists and needs no further change once M7 merges
every M4 lane's add-ons into one `apps/addons/` — at that point, if two or more installed
add-ons declare `_day_after`, `TestEveryCopyOfTheDayAfterArithmetic` starts running against
them automatically and the guard below stops skipping. Until then this file records absence
rather than a false failure: the guard skips, it does not pass vacuously and it does not
fail for a reason that has nothing to do with this batch's own two add-ons.

The subjects are discovered, not listed, for the reason
`test_addon_credential_hygiene.py` gives: a guard that names its subjects stops covering
the next one and says nothing when it does.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ADDONS = Path(__file__).resolve().parent.parent / "addons"


def load_module(root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"{root.name}_helpers", root / "handler.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def addons_with(helper: str) -> list[Path]:
    """Every installed add-on whose handler defines `helper`."""
    return sorted(
        path.parent
        for path in ADDONS.glob("*/handler.py")
        if hasattr(load_module(path.parent), helper)
    )


DAY_AFTER = addons_with("_day_after")


@pytest.mark.parametrize("root", DAY_AFTER, ids=lambda root: root.name)
class TestEveryCopyOfTheDayAfterArithmetic:
    """`_day_after` advances a `yyyy-mm-dd` cursor by one day.

    The documented intent is a start date the API accepts, not a correct calendar:
    February is 29 in every year on purpose, because asking for a 29th that does not exist
    costs one empty day while a wrong rollover costs a wrong window. These cases pin that
    intent — including the part that is deliberately not a real calendar.

    `[측정]` Collects zero parameters in this worktree (see the module docstring's M4 lane
    note) — pytest generates no test cases for an empty parametrization, which is why the
    module-level guard below exists as a separate, non-parametrized test.
    """

    def test_it_advances_inside_a_month(self, root: Path) -> None:
        assert load_module(root)._day_after("2026-03-14") == "2026-03-15"

    def test_february_rolls_over_to_march(self, root: Path) -> None:
        assert load_module(root)._day_after("2026-02-29") == "2026-03-01"

    def test_february_is_twenty_nine_days_in_every_year(self, root: Path) -> None:
        """Deliberate, and the clause the mutation review found untested in both copies."""
        assert load_module(root)._day_after("2026-02-28") == "2026-02-29"

    def test_a_thirty_day_month_rolls_over(self, root: Path) -> None:
        assert load_module(root)._day_after("2026-04-30") == "2026-05-01"

    def test_the_end_of_a_year_rolls_over(self, root: Path) -> None:
        assert load_module(root)._day_after("2026-12-31") == "2027-01-01"


def test_the_arithmetic_was_found_in_more_than_one_add_on() -> None:
    """The guard on the guard: discovery that matched nothing would pass every case above.

    `[측정]` M4 lane note: skips rather than fails when this worktree's own `apps/addons/`
    holds fewer than two `_day_after` implementations — true here by construction, since
    this batch installs only `importer.local.jsonl` and `normalizer.obf.product`, and a red
    result caused by that would be a false failure about worktree scope, not about this
    batch's own two add-ons. M7 re-runs this file over the merged `apps/addons/` set, where
    the two DataLab collectors are both present and this assertion is meant to hold.
    """
    if len(DAY_AFTER) < 2:
        pytest.skip(
            f"only {[root.name for root in DAY_AFTER]} declare _day_after in this worktree; "
            "M7 re-runs this scan over the merged apps/addons/ set"
        )
    assert len(DAY_AFTER) >= 2, f"only {[root.name for root in DAY_AFTER]} were discovered"
