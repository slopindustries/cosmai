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

Superseded decisions:

- [DP-004 — Core-first P0 and deferred collector/normalizer implementations](DP-004-p0-implementation-order.md), superseded by DP-005
