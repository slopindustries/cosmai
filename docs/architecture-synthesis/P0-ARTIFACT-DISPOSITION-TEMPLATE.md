# P0 Artifact Disposition Register

- Status: `DRAFT | ACCEPTED`
- Governing decisions: [DP-001](../decisions/DP-001-p0-lifecycle.md), [DP-005](../decisions/DP-005-two-part-pre-p1-execution.md)
- P0-B experiment:
- Reviewed code revision:
- Review date and timezone:
- Reviewers:

## Purpose

Record what P1 receives, rebuilds, keeps only as historical reference, deletes after evidence capture, or carries forward as unresolved. No P0 implementation becomes a P1 runtime or package dependency through this register.

## Disposition values

- `PROMOTE`: accepted contract, scenario, eligible fixture, decision, or evidence artifact.
- `REBUILD_FROM_CONTRACT`: behavior required in P1 and reimplemented from an accepted contract.
- `ARCHIVE_REFERENCE_ONLY`: P0 artifact retained by Git tag or equivalent history but not imported or depended on by P1.
- `DELETE_AFTER_EVIDENCE_CAPTURE`: runtime or protected artifact deleted after required metadata, hashes, and summaries are recorded.
- `UNRESOLVED`: insufficient evidence; carry as an explicit P1 Open Question or blocker.

## Register

| Artifact | Identity or hash | Data class | Evidence used | Disposition | P1 contract or question | Retention/deletion owner | Rationale |
|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |

## Required inventories

- Experimental and promoted contracts
- Acceptance scenarios and deterministic expected outputs
- Public, local, and private fixtures or runtime inputs
- Source capability records, hashes, and retrieval instructions
- P0 backend, dashboard, migrations, and orchestration
- Logs, metrics, traces, screenshots, and temporary databases
- Architecture decisions, rejected alternatives, and unresolved questions

## Acceptance checks

- [ ] Every material P0 artifact has exactly one disposition.
- [ ] Every `PROMOTE` item has an accepted decision and compatibility status where required.
- [ ] Every `REBUILD_FROM_CONTRACT` item links the accepted contract and P1 owner.
- [ ] Every `ARCHIVE_REFERENCE_ONLY` implementation is prohibited as a P1 runtime or package dependency.
- [ ] Every `DELETE_AFTER_EVIDENCE_CAPTURE` item has required metadata, hashes, summaries, and deletion responsibility recorded.
- [ ] Every `UNRESOLVED` item links an Open Question or explicit blocker.
- [ ] Restricted data, credentials, and raw conversations are not preserved contrary to project conventions.

## Decision

- Outcome: `ACCEPTED | NOT ACCEPTED`
- `[결정]`:
- Remaining blockers to P1 entry:
