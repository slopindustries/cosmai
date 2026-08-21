"""Credential hygiene: what an add-on's executable code may never name.

`CONTRACT-ADDON-1.3.md` §Provenance and security: "Prohibited in an add-on's
executable code: header names, secret-store key names, URLs, and the `COSMA_SRC_`
prefix. Docstrings citing vendor documentation URLs are permitted — the scan reads
what the code *names*, not what the prose explains."

Copy-adapted from `experiments/integrated-p0/tests/test_addon_credential_hygiene.py`
(M3 batch 3c), and promoted from a test-only scan to a load-time refusal.

`[측정]` **Why promoted.** P0 never enforced this rule anywhere but a pytest run: the
scan there was itself discovered as a defect once, "parametrized over
`[TREND, SHOPPING]` — two of the three collectors that declare `needs_credential`.
`collector.naver.blog` was scanned by nothing, and planting `X-NCP-APIGW-API-KEY`
and a vendor URL in its executable code left the suite fully green"
(`ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` B5). The fix P0 shipped — discovering
subjects from the filesystem rather than a name list — repairs the *coverage* gap
but not the *enforcement* one: a hygiene rule checked only by a test suite is
checked only when someone remembers to run that suite, on that add-on, before it
reaches a running host. Wiring the same scan into `addon_host.loading` makes it a
load-time refusal instead — the same discipline the version gate and the entry
check already have, for the identical reason: an operator installing a bad add-on
gets one clear, non-retryable failure at process start, not a job that ran and
leaked a credential into Raw before anyone looked.

**Where it runs.** Before the entry module is imported, on the raw source text —
never after, and never by executing anything. `addon_host.loading`'s own docstring
states the version gate's ordering rule ("must not have its module body executed
on the way to being refused"); this scan is read-only and needs no different
ordering to honour it, but running before import means an add-on that fails this
check never runs at all, matching the version gate's own guarantee rather than
merely resembling it.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

__all__ = ["FORBIDDEN", "executable_names", "hygiene_violations", "scan_source_file"]

#: Header names, key names, and destinations — the things an add-on that had
#: reached past DP-008 D4 would actually contain.
#:
#: `[측정]` `credential` was deliberately left off this list. P0's own scan found it
#: matched `"…rejected the configured credential (401)"` in three add-ons — an error
#: message explaining *why* a request was refused. Saying why a credential was
#: rejected is not holding one, so the word is not forbidden.
FORBIDDEN: Final[tuple[str, ...]] = (
    "x-ncp-apigw",
    "client_secret",
    "client_id",
    "https://",
    "authorization",
    "cosma_src_",
)


def executable_names(source: str) -> list[str]:
    """Every string literal, attribute, and name an add-on's code actually evaluates.

    `[측정]` The first version of the P0 scan this is copy-adapted from read the file
    as text and failed on add-ons whose module docstrings **cite the vendor
    documentation URLs**, which is exactly what a docstring should do. The property
    is about what the code *names*, not about what the prose explains, so
    docstrings are removed before the search rather than the forbidden list being
    weakened.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # Removing the docstring statement is what keeps it out of the literal walk
        # below; `ast.get_docstring` only finds it.
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


def hygiene_violations(source: str) -> dict[str, tuple[str, ...]]:
    """Every forbidden term this source names, and what literal or identifier
    matched it. Empty means clean.

    Keyed by the forbidden term rather than flattened into one list, so a refusal
    can say which rule fired and what it found — the same shape every other
    refusal in this project uses to name the rule rather than only the failure.
    """
    names = executable_names(source)
    violations: dict[str, tuple[str, ...]] = {}
    for forbidden in FORBIDDEN:
        offending = tuple(sorted({item for item in names if forbidden in item}))
        if offending:
            violations[forbidden] = offending
    return violations


def scan_source_file(path: Path) -> dict[str, tuple[str, ...]]:
    """`hygiene_violations` over one file on disk."""
    return hygiene_violations(path.read_text(encoding="utf-8"))
