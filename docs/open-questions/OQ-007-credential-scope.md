# OQ-007 — Credential Resolution Scope

- Status: `OPEN`
- Priority: P0-A secret-location and redaction guard; P0-B source credential scope
- Owner: Project team
- Blocks: credential handling contract, worker boundary contract, `SEC-001` and `SEC-002` evidence scope
- Related experiments: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — `COMPLETED` 2026-08-17, covers only the P0-A minimum experiment below: the secret-store location guard (`SEC-001`), loopback boundary (`SEC-002`), configuration failure (`SEC-003`), and redaction (`SEC-004`). No credential is resolved and no `credential_ref` semantics are created, so H1, H2, and H3 remain untested.
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

### Proposed resolution path from DP-008

[DP-008](../decisions/DP-008-addon-architecture.md) D6 selects on-demand resolution scoped to the claimed job's `source_id`, and adds two things the alternatives above did not state.

- `[결정]` The **add-on never receives the credential.** The platform's `fetch` resolves it, attaches it, and strips protected headers from what it returns. This is the in-process form of the proxy alternative, and it narrows the exposed surface from "the worker" to "the platform's outbound path inside the worker".
- `[결정]` The dashboard writes a submitted secret to the repository-external store and records only `credential_ref` in the source row. That path is **write-only and never reads a credential back**, so the API process is a writer and never a reader.

`[확인 사실]` This does not resolve H1, H2, or H3. The worker process still holds the value for the life of the request inside `fetch`, so per-source scoping is still enforced by resolution discipline rather than by process boundary — which is exactly what H2 asks about. The question stays `OPEN`; DP-008 narrows what has to be tested, not whether it has to be.

## Minimum experiment

### P0-A

- Verify that the configured secret-store location is outside the repository working tree.
- Verify loopback, redaction, protected-debug, and configuration-failure behavior with non-domain synthetic values.
- Do not register sources, create `credential_ref` authorization semantics, or run synthetic collection handlers.

### P0-B

- Implement the credential-resolution boundary after the source and job-domain contracts exist.
- Register two sources with distinct synthetic credentials, claim a job for source A, and attempt to resolve source B's credential from the same execution context.
- Repeat under concurrent claims by two workers, then verify that the concrete selected-source collector preserves the accepted resolution and redaction boundary.
- Real credential values must not appear in recorded evidence.

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
