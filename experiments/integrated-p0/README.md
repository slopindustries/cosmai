# Integrated P0

This directory contains the disposable Architecture Discovery Prototype for both P0-A and P0-B. Stage boundaries are governed by [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md) and the [P0 Execution Plan](../../docs/p0-execution-plan.md).

## P0-A

Build only the source- and normalization-independent platform core:

- PostgreSQL runtime, migrations, and source-neutral transaction foundations;
- handler-neutral jobs, API and worker lifecycle, claims, leases, retries, terminal states, interruption, and recovery;
- source-neutral dashboard health, generic job state, logs, metrics, correlation, failure inspection, and safe retry;
- redaction, loopback, secret-store location guards, synthetic handlers, and platform failure injection.

P0-A must not explore or select sources or create acquisition, Raw, snapshot, or normalization contracts, ports, fixtures, test doubles, persistence, UI behavior, or implementations. Synthetic handlers may exercise generic success and failure behavior but must not imitate a collector, importer, Raw payload, snapshot producer, or normalizer.

`[결정]` **The P0-A gate is accepted `GO` as of 2026-08-17, with no conditions.** The record is [PLATFORM-CORE-GATE-2026-08-17.md](PLATFORM-CORE-GATE-2026-08-17.md), written from [PLATFORM-CORE-GATE-TEMPLATE.md](PLATFORM-CORE-GATE-TEMPLATE.md); the experiment behind it is [EXP-001](EXP-001-platform-core.md) and every `PASS` claim was put to an [adversarial review](ADVERSARIAL-REVIEW-2026-08-17.md) first.

`[측정]` **P0-B's capability layer is built and reviewed, and its review is unrepaired.**
[EXP-003](EXP-003-capability-layer.md) put a collector on the platform; the
[adversarial review of `27f712b`](ADVERSARIAL-REVIEW-2026-08-18.md) then returned three
blocking findings against it. Read the review before building on the capability layer —
two of the three are properties EXP-003 claimed and the code does not have.

Read the gate's "What this gate does not claim" section before building on any of it. P0-A completion is not evidence that a real collector, dataset importer, Raw model, snapshot, or normalizer will work.

## P0-B

P0-B begins with bounded source exploration and selection. It then defines and implements the complete acquisition and normalization domain, runs the real-data and failure scenarios, and completes Architecture Synthesis, artifact disposition, `PoC Contract 0.1`, and the P1 reconstruction plan.

Source probe code remains under `experiments/source-probes/`; it is measurement code and must not be silently promoted into the integrated collector or importer.

Keep every disposable backend, dashboard, migration, and orchestration artifact inside this boundary so none can be mistaken for P1 application code. A gate decision must name the tested code revision and evidence; it cannot be inferred from code existence.

Create each integrated experiment from [`experiments/EXPERIMENT-TEMPLATE.md`](../EXPERIMENT-TEMPLATE.md). P0 may optimize for observability and experimental clarity over long-term maintainability, but it must not compromise source rights, secret handling, provenance, or result labeling.
