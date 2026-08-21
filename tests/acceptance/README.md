# Acceptance Scenarios

Acceptance tests describe behavior before they bind to a particular P0 implementation.

Under [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md), P0-A may draft and execute only handler-neutral `JOB`, platform `OPS`, and platform `SEC` scenarios. P0-B drafts and executes `ACQ`, `RAW`, `SNP`, `NRM`, and domain `OPS` and `SEC` scenarios after source evidence exists, first against bounded domain test doubles where useful and then against the concrete components and real inputs.

Initial scenario families:

- `ACQ`: REST collection and dataset import.
- `RAW`: lossless storage, identity, duplicate, and observation behavior.
- `JOB`: claim, lease, retry, interruption, and final failure.
- `SNP`: snapshot sealing, replay, and tamper detection.
- `NRM`: provider validation, determinism, version coexistence, and lineage.
- `OPS`: dashboard control, diagnosis, and safe retry.
- `SEC`: credential redaction, source restrictions, and protected debug data.

The initial `SEC` scenarios are defined by the [P0 Security Baseline](../../docs/conventions/p0-security.md). P0-A covers loopback exposure, redaction, protected debug behavior, and secret-store location guards. P0-B adds registered-source enforcement, credential scope, redirect/DNS validation, and bounded response handling.

Each scenario should name its input fixture, preconditions, action, expected state transitions, durable effects, telemetry, and failure classification.

Create each scenario from [SCENARIO-TEMPLATE.md](SCENARIO-TEMPLATE.md). Scenario IDs use the family prefix and a stable number, such as `RAW-001` or `SEC-003`.

⚠️ `[확인 사실]` **A `SEC-00N` here is not the `SEC-00N` in the
[P0 Security Baseline](../../docs/conventions/p0-security.md).** Two numbering schemes share
the prefix and none of the four overlapping numbers agree — this file's `SEC-002` is the
baseline's `SEC-005`, and this file's `SEC-004` is the baseline's `SEC-001`. The baseline
carries the full mapping table. Cite through it rather than by number alone.
