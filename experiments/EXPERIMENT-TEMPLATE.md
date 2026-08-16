# EXP-XXX — Experiment title

Copy this file into the experiment directory and replace every placeholder. Do not use the template itself as a running log.

## Identity and status

- Experiment ID: `EXP-XXX`
- Type: `SOURCE_PROBE | INTEGRATED_P0 | OTHER`
- Status: `PLANNED | RUNNING | COMPLETED | INCONCLUSIVE | ABORTED`
- Related Open Question or Decision Packet: `OQ-XXX | DP-XXX`
- Owner:
- Created at: ISO 8601 timestamp with timezone
- Last executed at: ISO 8601 timestamp with timezone

Status meanings:

- `PLANNED`: hypothesis, falsification, exit condition, and procedure are drafted but execution has not begun.
- `RUNNING`: the bounded procedure is actively collecting evidence.
- `COMPLETED`: the recorded procedure and exit condition completed with a supported or refuted outcome.
- `INCONCLUSIVE`: the exit condition was reached but the evidence cannot support or refute the hypothesis.
- `ABORTED`: execution stopped before its exit condition because of a recorded safety, rights, cost, environment, or design blocker.

Fix the hypothesis, falsification condition, and exit condition before changing the status to `RUNNING`. If they must change, record the revision and reason rather than silently overwriting the original boundary.

## Question

State the single uncertainty this experiment is intended to reduce. If several independent questions are present, split the experiment.

## Hypothesis

`[가설]` Write one falsifiable claim. Avoid implementation goals such as “build a collector.”

## Falsification condition

Describe the observable result that would refute the hypothesis. Define thresholds and units before execution where possible.

## Exit condition

State when the experiment stops, independently of whether the result is favorable. Include time, sample, attempt, or cost limits when relevant.

## Scope

### Included

-

### Excluded

-

## Inputs and provenance

| Input | Source or provider | Captured at | License or usage basis | Version or hash | Storage note |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

Do not include credentials, restricted data, or raw conversation material. For non-redistributable input, record only a checksum and retrieval procedure.

## Environment

- Code revision:
- Runtime and dependency versions:
- External service or database versions:
- Relevant configuration with secrets removed:
- Reproduction command:

## Procedure

1.
2.
3.

Specify retries, concurrency, fixtures, failure injection, and cleanup when they affect the result.

## Evidence collection

- Metrics and units:
- Log or trace location:
- Output artifact location:
- Integrity check or hash procedure:

## Observations

Record direct experimental outcomes as `[측정]`. Include input size, environment, execution time, units, and error bounds or known limits.

```text
[측정]
```

Do not rewrite an unfavorable observation to match the hypothesis. Append a correction with its reason if an earlier observation was invalid.

## Interpretation

Separate meaning derived from the observations as `[추론]`. Link each inference to the measurements that support it.

```text
[추론]
```

## Result

- Outcome: `SUPPORTED | REFUTED | INCONCLUSIVE`
- Falsification condition met: `YES | NO | NOT TESTED`
- Exit condition met: `YES | NO`
- Known limitations:

- `SUPPORTED`: the recorded evidence is consistent with the hypothesis within the bounded inputs and environment; this is not universal proof.
- `REFUTED`: the predeclared falsification condition was observed.
- `INCONCLUSIVE`: neither support nor falsification is justified within the exit boundary; this is not a favorable result.

## Impact and next action

- Uncertainty reduced:
- New uncertainty discovered:
- Proposed next experiment:
- Proposed contract change:
- Proposed Decision Packet update:

Do not present a proposal as `[결정]`. Record a decision only after it is accepted through the project's decision process.

## Artifacts

- Experiment record:
- Code:
- Fixture or retrieval procedure:
- Logs, metrics, traces, or screenshots:
- Output and hashes:
- Data class and retention responsibility:

## Completion checklist

- [ ] The hypothesis is falsifiable.
- [ ] The falsification and exit conditions were fixed before interpreting the result.
- [ ] Inputs, rights, environment, versions, and hashes are recorded.
- [ ] The procedure is replayable without relying on undocumented session context.
- [ ] Observations and interpretations use the project evidence labels correctly.
- [ ] Secrets, restricted inputs, and raw conversations are absent.
- [ ] The result includes limitations and a concrete next action.
