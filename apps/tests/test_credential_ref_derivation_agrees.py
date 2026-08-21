"""M-X3 (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`): `domain.api.credential_ref_for`
must derive the same ref as `apps/dashboard/src/api/client.ts`'s `credentialRefName` for
the same `(source_id, purpose)` pair — the dashboard shows the operator this name so
they know which key to populate, and the write path that actually resolves it runs this
Python function. The two used to diverge on consecutive separators (`"a..b"` ->
`A__B` in TypeScript, `A_B` here) and leading/trailing ones (`".lead"` -> `_LEAD` there,
`LEAD` here). Same vector table, same order, asserted on both sides:
`apps/dashboard/src/api/__tests__/client.test.ts`.
"""

from __future__ import annotations

import pytest

from domain.api import credential_ref_for

VECTORS: list[tuple[str, str, str]] = [
    ("naver-blog", "client_id", "COSMA_SRC_NAVER_BLOG_CLIENT_ID"),
    ("probe-blog", "token", "COSMA_SRC_PROBE_BLOG_TOKEN"),
    ("a..b", "token", "COSMA_SRC_A_B_TOKEN"),
    (".lead", "token", "COSMA_SRC_LEAD_TOKEN"),
    ("trail.", "token", "COSMA_SRC_TRAIL_TOKEN"),
    ("mixed_CASE-123", "purpose", "COSMA_SRC_MIXED_CASE_123_PURPOSE"),
]


@pytest.mark.parametrize(("source_id", "purpose", "expected"), VECTORS)
def test_credential_ref_for_matches_the_shared_vector_table(
    source_id: str, purpose: str, expected: str
) -> None:
    assert credential_ref_for(source_id, purpose) == expected
