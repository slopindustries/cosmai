# DP-002 — Project Identity and Initial Technology Constraints

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-16
- Owners: Project team
- Related Open Questions: OQ-001, OQ-003, OQ-006

## Decision

- ~~`[결정]` Project and GitHub organization display name: **CosmaSignal**.~~ **Superseded by [DP-007](DP-007-project-rename-to-cosmai.md), 2026-08-17: the display name is Cosmai.** The original text is kept rather than rewritten, because a decision record that silently reads as the current answer stops being a record.
- ~~`[결정]` Local directory name: `cosma-signal`.~~ **Superseded by [DP-007](DP-007-project-rename-to-cosmai.md): `cosmai`.**
- `[결정]` Use a monorepo for the backend, dashboard, contracts, experiments, and tests.
- `[결정]` Backend language: Python.
- `[결정]` Primary database: PostgreSQL.
- `[결정]` Dashboard language and UI foundation: React with TypeScript.
- `[결정]` P0 must support both REST API collection and existing dataset import.

## Rationale

The stack is compatible with rapid data exploration, rule/ML/LLM normalizer providers, asynchronous workers, relational job and lineage modeling, and a dashboard control plane. The name describes the problem domain without coupling the project to AI as its only implementation method.

## Scope and reversibility

These are P0 constraints, not proof that every framework or deployment choice belongs in production. FastAPI, SQLAlchemy, Alembic, HTTPX, React Router, TanStack Query, and MUI remain strong defaults subject to P0 evidence.

## Remaining uncertainty

- Exact Python packaging and process entrypoints.
- Exact job-queue implementation.
- P0 dashboard component library details.
- Future service and deployment topology.
