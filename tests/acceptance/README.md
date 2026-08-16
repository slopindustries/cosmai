# Acceptance Scenarios

Acceptance tests describe behavior before they bind to a particular P0 implementation.

Initial scenario families:

- `ACQ`: REST collection and dataset import.
- `RAW`: lossless storage, identity, duplicate, and observation behavior.
- `JOB`: claim, lease, retry, interruption, and final failure.
- `SNP`: snapshot sealing, replay, and tamper detection.
- `NRM`: provider validation, determinism, version coexistence, and lineage.
- `OPS`: dashboard control, diagnosis, and safe retry.
- `SEC`: credential redaction, source restrictions, and protected debug data.

The initial `SEC` scenarios are defined by the [P0 Security Baseline](../../docs/conventions/p0-security.md): secret redaction, registered-source enforcement, redirect/DNS validation, bounded response handling, and loopback-only default exposure.

Each scenario should name its input fixture, preconditions, action, expected state transitions, durable effects, telemetry, and failure classification.

Create each scenario from [SCENARIO-TEMPLATE.md](SCENARIO-TEMPLATE.md). Scenario IDs use the family prefix and a stable number, such as `RAW-001` or `SEC-003`.
