# DP-004 — Core-First P0 and Deferred Collector/Normalizer Implementations

- Status: `SUPERSEDED`
- Date: 2026-08-16
- Superseded at: 2026-08-17
- Superseded by: [DP-005](DP-005-two-part-pre-p1-execution.md)
- Owners: Project team

## Historical decision

DP-004 previously required source selection and acquisition and normalization contracts before a core-first implementation and Collector/Normalizer Implementation Gate.

## Supersession reason

`[결정]` The project owner replaced that boundary with two pre-P1 stages. P0-A now remains entirely source- and normalization-independent. P0-B owns source exploration and selection, acquisition, Raw, snapshot, normalization, concrete integration, real-data verification, Architecture Synthesis, artifact disposition, and P1 entry.

## Active replacement

This packet has no active implementation requirements. Follow [DP-005](DP-005-two-part-pre-p1-execution.md) and the [P0 Execution Plan](../p0-execution-plan.md).
