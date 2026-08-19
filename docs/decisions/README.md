# Decisions

Decision Packets convert exploration evidence into scoped, reviewable decisions.

Use [DP-TEMPLATE.md](DP-TEMPLATE.md). A Decision Packet must not hide inconclusive evidence. If evidence is insufficient, keep the Open Question open or choose a clearly reversible `ACCEPTED_FOR_POC` default with remaining uncertainty recorded.

Active decisions:

- [DP-001 — Disposable P0 and clean P1 reconstruction](DP-001-p0-lifecycle.md)
- [DP-002 — Project identity and initial technology constraints](DP-002-project-identity-and-stack.md)
- [DP-003 — Development environment and Python packaging](DP-003-development-environment.md)
- [DP-005 — Two-part pre-P1 execution](DP-005-two-part-pre-p1-execution.md)
- [DP-006 — P0-A platform foundation choices](DP-006-p0a-platform-foundation.md) — accepted at the P0-A Completion Gate, 2026-08-17
- [DP-007 — Project rename to Cosmai](DP-007-project-rename-to-cosmai.md) — accepted 2026-08-17; supersedes DP-002's two naming decisions only
- [DP-008 — Add-on architecture for collectors and normalizers](DP-008-addon-architecture.md) — accepted 2026-08-18; supersedes DP-005's P0-B order steps 4–6 and DP-006's module layout
- [DP-010 — Durable work inside the completion transaction](DP-010-durable-work-in-the-completion-transaction.md) — accepted 2026-08-18; supersedes one clause of DP-008 D1
- [DP-011 — P0-B product decision and delivery scope](DP-011-p0b-product-and-delivery-scope.md) — accepted 2026-08-19; fixes the two-category R&D review flow and the 2026-08-26/27 delivery boundary
- [DP-012 — Independent scraper services and COSMAI REST adapters](DP-012-independent-scraper-services.md) — accepted 2026-08-19; keeps scraper runtimes and first-stage storage outside COSMAI and integrates them through in-repository REST adapter add-ons
- [DP-013 — Documented memory and role-separated agent workflow](DP-013-agent-workflow-and-project-memory.md) — accepted 2026-08-19; renumbered from the `DP-006` the isolated branch used, which [DP-006](DP-006-p0a-platform-foundation.md) already held
- [DP-014 — Project memory scope, and the development-area exception](DP-014-agent-memory-scope-and-area-exception.md) — accepted 2026-08-19; resolves OQ-011 and amends DP-013 D5
- [DP-018 — Credential parts, and where the platform attaches them](DP-018-credential-parts-and-attachment.md) — accepted 2026-08-18; resolves OQ-009 for P0-B on one source's evidence
- [DP-019 — Normalized Schema 0.1, the result table, and what a snapshot selects](DP-019-normalized-schema-0-1-and-results.md) — accepted 2026-08-18; narrows OQ-003 and OQ-004, records the provisional decision use OQ-002 still owes
- [DP-020 — Request method and body in the outbound guard](DP-020-request-method-and-body.md) — accepted 2026-08-18; bumps `addon_api` to contract 1.1
- [DP-021 — Normalized Schema 0.2: a second record type](DP-021-schema-0-2-trend-points.md) — accepted 2026-08-19; records that `project-state.md` §5 hypothesis 5 is refuted in its strong form
- [DP-022 — Structural fixtures](DP-022-structural-fixtures.md) — accepted 2026-08-19; how a real capture becomes evidence this project may publish
- [DP-023 — SEC-006 waived for P0](DP-023-sec-006-waived-for-p0.md) — accepted 2026-08-19; an accepted risk, not a satisfied control, expiring at the P1 Entry Gate
- [DP-024 — the local input registry](DP-024-local-input-registry.md) — accepted 2026-08-19; an importer names an input and the operator's approved profile says which file that is, which is what bound `open_input` and the `importer` kind
- [DP-025 — Reconciling two decision records that grew from the same commit](DP-025-two-branch-record-reconciliation.md) — accepted 2026-08-20; keeps the published numbers, closes OQ-014 into DP-012, and states what the P0-B completion claim is measured against
- [DP-026 — What ends P0, and where a collector lives](DP-026-p0-closure-scope-and-collector-topology.md) — accepted 2026-08-20; closes P0 against the charter, moves DP-011's product scope to P1, and binds DP-012's adapter topology to new collectors rather than the existing three

`[측정]` This list omitted DP-018 through DP-022 until 2026-08-19, while `AGENTS.md` instructs
every reader to treat an `ACCEPTED_FOR_POC` decision as a constraint. Found by
`ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md` M5. An index that silently lags the decisions it
indexes is worse than no index, because a reader who checks it concludes there is nothing to
find.

Superseded decisions:

- [DP-004 — Core-first P0 and deferred collector/normalizer implementations](DP-004-p0-implementation-order.md), superseded by DP-005
