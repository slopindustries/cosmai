# Decisions

Decision Packets convert exploration evidence into scoped, reviewable decisions.

Use [DP-TEMPLATE.md](DP-TEMPLATE.md). A Decision Packet must not hide inconclusive evidence. If evidence is insufficient, keep the Open Question open or choose a clearly reversible `ACCEPTED_FOR_POC` default with remaining uncertainty recorded.

Active decisions:

- [DP-001 — Disposable P0 and clean P1 reconstruction](DP-001-p0-lifecycle.md)
- [DP-002 — Project identity and initial technology constraints](DP-002-project-identity-and-stack.md)
- [DP-003 — Development environment and Python packaging](DP-003-development-environment.md)
- [DP-005 — Two-part pre-P1 execution](DP-005-two-part-pre-p1-execution.md)

Proposed, not yet accepted:

- [DP-006 — P0-A platform foundation choices](DP-006-p0a-platform-foundation.md) — `DRAFT`. Written before the work it governs so that no A1 foundation choice is resolved silently, and proposed for acceptance at the P0-A Completion Gate together with the evidence showing whether each choice held. Until then it is a recorded proposal, not a project constraint.

Superseded decisions:

- [DP-004 — Core-first P0 and deferred collector/normalizer implementations](DP-004-p0-implementation-order.md), superseded by DP-005
