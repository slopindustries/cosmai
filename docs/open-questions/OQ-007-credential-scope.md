# OQ-007 — Credential Resolution Scope

- Status: `OPEN`
- Priority: P0 — required before a worker resolves a real credential
- Owner: Project team
- Blocks: credential handling contract, worker boundary contract, `SEC-001` and `SEC-002` evidence scope
- Related experiments: not started
- Resolution Decision Packet: not created

## Question

Which credentials must a worker be able to resolve at the moment it executes a job, and what enforces that boundary?

## Why this cannot be decided yet

No worker implementation exists, and the claim model in [OQ-006](OQ-006-job-concurrency.md) is undecided. Whether a worker processes arbitrary sources or is partitioned by source determines whether per-source credential scoping is enforceable or merely cosmetic. Choosing process-global resolution now would silently fix that boundary before the evidence exists.

## Scope

### Included

- The resolution boundary for `credential_ref` at job execution time.
- Whether resolution is process-global or scoped to the claimed job's `source_id`.
- What a worker can read while processing an unrelated source.
- Evidence that the boundary holds under at-least-once delivery and concurrent claims.

### Excluded

- Secret manager product selection, rotation design, multi-tenant authorization, and production identity provider choice. These are non-goals in [P0 Security Baseline](../conventions/p0-security.md).

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Resolving on demand from the secret store, never through the process environment, is sufficient to scope a worker to the credential of the source it is currently processing. | A tested execution path resolves or exposes a credential belonging to a source other than the claimed job's source. |
| H2: Per-source scoping is enforceable without partitioning workers by source. | Enforcement requires dedicated per-source worker processes or per-source stores, which changes the job model in OQ-006. |
| H3: A flat key-per-`credential_ref` store can express the required boundary. | Expressing the boundary requires access control that a flat store cannot represent. |

## Alternatives

- Process-global resolution; any worker may read any credential. Cheapest, consistent with a disposable P0, but produces no scoping evidence.
- On-demand resolution scoped to the claimed job's `source_id`.
- A separate store per source, located from `source_id`.
- Injection at the network boundary by a proxy, so the worker never holds the value.

## Minimum experiment

Register two sources with distinct synthetic credentials. Run one worker, claim a job for source A, and attempt to resolve source B's credential from the same execution context. Repeat under concurrent claims by two workers. Record what is resolvable at each point.

## Evidence requirements

- Required measurements: what is resolvable at claim time, at execution time, and after failure; whether a redaction wrapper is preserved across error paths.
- Environment and versions: worker runtime, store backend, claim model in effect.
- Input and fixture identity: source ids and synthetic credential values only.
- Rights and provenance: no real credential appears in any recorded evidence.
- Known limitations to preserve: single-host P0 execution; no rotation or revocation tested.

## Exit condition

The team can state which credential a worker may resolve, what enforces that limit, and whether the answer changes the OQ-006 job model — enough to write the credential section of `PoC Contract 0.1`.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`.
