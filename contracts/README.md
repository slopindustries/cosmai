# Contracts

Contracts define behavior shared across the backend, workers, dashboard, stored data, and tests. Coupling occurs through versioned contracts rather than copied implementation code.

- `experimental/`: unstable contracts used to compare hypotheses during exploration and P0.
- Future accepted versions will receive explicit version directories or files after a Decision Packet.

A contract should state purpose, version, compatibility status, schema, invariants, expected behavior, error behavior, and acceptance criteria.

Create P0 candidates from [`experimental/CONTRACT-TEMPLATE.md`](experimental/CONTRACT-TEMPLATE.md). A completed template remains experimental until an accepted Decision Packet promotes a version.
