"""DP-008 D4 asserted at every add-on, not at the ones somebody remembered to list.

**Why this file exists rather than a parametrized case inside one add-on's tests.**
`[측정]` The scan this replaces was parametrized over `[TREND, SHOPPING]` — two of the
three collectors that declare `needs_credential`. `collector.naver.blog` was scanned by
nothing, and planting `X-NCP-APIGW-API-KEY` and a vendor URL in its executable code left
the suite fully green. A guard that names its subjects stops covering the next one, and
nothing announces that it has stopped. `ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5.

The list of subjects is therefore **discovered from the filesystem**, and a separate test
asserts the discovery still finds every installed add-on. That second test is the one that
fails when the mechanism rots.

**What the property is.** The platform attaches credential headers at the worker boundary
and hands the add-on a response; an add-on never holds a credential and never names a
destination. A header name, a key name, or a URL appearing in executable code is the first
thing that would show up if that ever stopped being true.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ADDONS = Path(__file__).resolve().parent.parent / "addons"

#: Header names, key names, and destinations — the things an add-on that had reached past
#: DP-008 D4 would actually contain.
#:
#: `[측정]` `credential` was on this list and matched
#: `"…rejected the configured credential (401)"` in three add-ons — an error message
#: explaining *why* a request was refused. Saying why a credential was rejected is not
#: holding one, so the word is not forbidden.
FORBIDDEN = (
    "x-ncp-apigw",
    "client_secret",
    "client_id",
    "https://",
    "authorization",
    "cosma_src_",
)


def executable_names(source: str) -> list[str]:
    """Every string literal, attribute, and name an add-on's code actually evaluates.

    `[측정]` The first version of this scanned the file as text and failed on add-ons whose
    module docstrings **cite the vendor documentation URLs**, which is exactly what a
    docstring should do. The property is about what the code names, not about what the prose
    explains, so docstrings are removed before the search rather than the forbidden list
    being weakened.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # Removing the docstring statement is what keeps it out of the literal walk below;
        # `ast.get_docstring` only finds it.
        if (
            isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef)
            and node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            node.body.pop(0)
    return (
        [
            node.value.lower()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        + [node.attr.lower() for node in ast.walk(tree) if isinstance(node, ast.Attribute)]
        + [node.id.lower() for node in ast.walk(tree) if isinstance(node, ast.Name)]
    )


def installed_addons() -> list[Path]:
    """Every directory under `addons/` that an add-on manifest makes an add-on."""
    return sorted(path.parent for path in ADDONS.glob("*/addon.toml"))


def scanned_addons() -> list[Path]:
    """Every installed add-on that has a handler to scan."""
    return [root for root in installed_addons() if (root / "handler.py").exists()]


@pytest.mark.parametrize("root", scanned_addons(), ids=lambda root: root.name)
def test_no_executable_line_names_a_credential_a_header_or_a_url(root: Path) -> None:
    names = executable_names((root / "handler.py").read_text(encoding="utf-8"))
    for forbidden in FORBIDDEN:
        offending = sorted({item for item in names if forbidden in item})
        assert not offending, f"{root.name} names {forbidden!r}: {offending}"


def test_every_installed_addon_is_scanned() -> None:
    """The guard on the guard.

    An add-on added without a handler, or a discovery that quietly stops matching, would
    make the case above pass by covering nothing. This is the test that fails then.
    """
    assert scanned_addons() == installed_addons(), (
        "an installed add-on has no handler.py and is therefore scanned by nothing: "
        f"{sorted(root.name for root in set(installed_addons()) - set(scanned_addons()))}"
    )
    assert len(scanned_addons()) >= 6, (
        f"only {len(scanned_addons())} add-ons were discovered; the tree has more"
    )


def test_the_scan_finds_a_credential_that_is_there() -> None:
    """Positive control, independent of what any add-on happens to contain."""
    planted = (
        '"""Docs: https://example.invalid/reference"""\n'
        "def run(context):\n"
        '    return context.fetch("blog", headers={"X-NCP-APIGW-API-KEY": "secret"})\n'
    )
    names = executable_names(planted)
    assert any("x-ncp-apigw" in name for name in names), "the scan read no header name"


def test_the_scan_does_not_fire_on_a_documentation_url_in_a_docstring() -> None:
    """The known false positive that shaped the scan, pinned so it cannot come back."""
    documented = (
        '"""Reference: https://api.example.invalid/guide"""\n'
        "def run(context):\n"
        "    return None\n"
    )
    assert not [name for name in executable_names(documented) if "https://" in name]
