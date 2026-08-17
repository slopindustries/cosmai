# SEC-002 — Operator surfaces and the database are unreachable from off the host

- Status: `DRAFT`
- Family: `SEC`
- Related contract and version: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) — "Provenance and security"
- Related Open Question or Decision Packet: [OQ-005](../../docs/open-questions/OQ-005-operations-contract.md), [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D2
- Input fixture and metadata: none. Observes the running processes' listening sockets.
- Owner: Project team

## Intent

Protect the charter's exit criterion *"Operator surfaces bind to loopback by default."*

The criterion says "by default," and this scenario deliberately goes further: in P0-A a non-loopback bind is refused outright rather than merely being off by default. There is no P0-A reason to expose an operator surface beyond the host, the dashboard has no authentication of any kind, and a default is a thing that gets overridden by accident. Relaxing this later is a one-line change with a recorded reason; discovering it was already relaxed is not recoverable.

The database is covered here too, because it is the same class of exposure and [DP-006](../../docs/decisions/DP-006-p0a-platform-foundation.md) D2 made it stronger than a binding choice: the cluster has no TCP listener at all.

## Preconditions

- Initial durable state: migrations applied.
- Worker or service state: the operator API started from a default configuration; the local cluster running.
- Configuration with secrets excluded: `COSMA_API_HOST` unset, so the default applies.
- Time, retry, and concurrency assumptions: none.

## Action

1. Start the operator API with no `COSMA_API_HOST` set. Record the address it bound to.
2. Connect to the API over loopback and confirm it responds.
3. Enumerate the host's non-loopback addresses and attempt to connect to the API on each.
4. Enumerate listening TCP sockets on the host and look for a PostgreSQL listener.
5. Confirm the database is reachable over its Unix socket, and that the connection is not a TCP connection.
6. Restart the API with `COSMA_API_HOST` set to `0.0.0.0`, then to a routable host address. Observe each exit.
7. Restart the API with `COSMA_API_HOST` set to `::1`. Observe the exit.

## Expected state transitions

| Step | Entity | From | To | Required timestamp or reason |
|---|---|---|---|---|
| 1 | API process | starting | running, bound to `127.0.0.1` | Default with no configuration |
| 6 | API process | starting | exited non-zero | `CONFIGURATION_INVALID`, non-loopback bind refused |
| 7 | API process | starting | running, bound to `::1` | IPv6 loopback is loopback |

## Expected durable effects

- Created or changed records: none.
- Effects that must not occur: no TCP listener for PostgreSQL on any address; no API listener on a non-loopback address; the API must not silently fall back to loopback when given `0.0.0.0` — silently correcting the configuration would hide a mistake the operator needs to see.
- Idempotency or duplicate expectation: n/a.
- Lineage expectation: none.

## Expected telemetry

- Correlation identifiers: n/a.
- Structured event or log fields: the API logs the exact address and port it bound to at startup. "Bound to loopback" as a claim in a document is not evidence; the recorded address is.
- Metrics and units: none required.
- Protected debug behavior: the protected-debug representation that `SEC-004` describes is available only on this loopback binding. That is the whole reason the binding is worth constraining.

## Failure classification and recovery

- Expected error class and code: `CONFIGURATION_INVALID` for a non-loopback bind.
- Retryable: no.
- Operator-visible explanation: the rejected address, and that P0-A permits loopback only.
- Safe retry or final action: use a loopback address, or record a decision to relax the constraint.

## Verification

- Execution command or procedure: `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k sec_002`
- Assertions: the bound address of the default API is a loopback address; connections from every enumerated non-loopback address of the host are refused; no listening PostgreSQL TCP socket exists; a database session reports `inet_server_addr() IS NULL`, which is true only over a Unix socket; `0.0.0.0` and a routable address are both refused; `::1` is accepted.
- Output and evidence location: `experiments/integrated-p0/evidence/<date>-<sha7>/`, including the listening-socket enumeration as recorded output rather than a summarised claim.
- Environment and versions: recorded in that directory's `ENVIRONMENT.md`.

## Result

- Last executed at: 2026-08-17
- `PASS`
- Linked experiment measurement: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — 25 passed via `./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k sec_002`
- Known limitation: evidence about binding, not authorization. Anything running on the host reaches both the API and the database with no credential. Accepted for a disposable single-host P0 and a boundary P0-B must revisit before anything real is stored.
