# Integrated P0

This directory contains the disposable Architecture Discovery Prototype for both P0-A and P0-B. Stage boundaries are governed by [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md) and the [P0 Execution Plan](../../docs/p0-execution-plan.md).

## P0-A

Build only the source- and normalization-independent platform core:

- PostgreSQL runtime, migrations, and source-neutral transaction foundations;
- handler-neutral jobs, API and worker lifecycle, claims, leases, retries, terminal states, interruption, and recovery;
- source-neutral dashboard health, generic job state, logs, metrics, correlation, failure inspection, and safe retry;
- redaction, loopback, secret-store location guards, synthetic handlers, and platform failure injection.

P0-A must not explore or select sources or create acquisition, Raw, snapshot, or normalization contracts, ports, fixtures, test doubles, persistence, UI behavior, or implementations. Synthetic handlers may exercise generic success and failure behavior but must not imitate a collector, importer, Raw payload, snapshot producer, or normalizer.

Create the P0-A gate record from [PLATFORM-CORE-GATE-TEMPLATE.md](PLATFORM-CORE-GATE-TEMPLATE.md). P0-B starts only after that gate records `GO` or an explicitly accepted `CONDITIONAL GO`.

## P0-B

P0-B begins with bounded source exploration and selection. It then defines and implements the complete acquisition and normalization domain, runs the real-data and failure scenarios, and completes Architecture Synthesis, artifact disposition, `PoC Contract 0.1`, and the P1 reconstruction plan.

Source probe code remains under `experiments/source-probes/`; it is measurement code and must not be silently promoted into the integrated collector or importer.

Keep every disposable backend, dashboard, migration, and orchestration artifact inside this boundary so none can be mistaken for P1 application code. A gate decision must name the tested code revision and evidence; it cannot be inferred from code existence.

Create each integrated experiment from [`experiments/EXPERIMENT-TEMPLATE.md`](../EXPERIMENT-TEMPLATE.md). P0 may optimize for observability and experimental clarity over long-term maintainability, but it must not compromise source rights, secret handling, provenance, or result labeling.
