# OQ-008 — May an operator re-execute work that already succeeded?

- Status: `OPEN`
- Priority: P0-B operations contract; blocks nothing in P0-A
- Owner: Project team
- Blocks: the operator action set in `PoC Contract 0.1`
- Related experiments: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) — surfaced during P0-A, deliberately not answered there
- Resolution Decision Packet: not created

## Question

Retrying a failure and re-running a success are different operations. P0-A implements only the first. Should the platform offer the second, and if so, what distinguishes a deliberate re-execution from a mistake?

## Why this exists

`[확인 사실]` This is not a question anyone set out to ask. `JOB-008` case A was written asking for an operator safe retry of a `SUCCEEDED` job, and its transition table said `SUCCEEDED → PENDING`. `[확인 사실]` [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) defines safe retry from `FAILED` only, and `JobStore.request_retry` matches the contract.

`[확인 사실]` The conflict was resolved by amending the scenario: case A now takes two sequential jobs sharing an `effect_key`, and asserts that a retry of a succeeded job is refused. `[확인 사실]` `experiments/integrated-p0/tests/test_job_concurrency.py` still records that resolving it "needs a Decision Packet", and no such packet exists.

An adversarial review of the P0-A gate found that gap (F14) and was right to. AGENTS.md: *"Do not silently resolve a consequential ambiguity. Create or update an Open Question or Decision Packet."* Amending a scenario in place is a resolution; the amendment carries the reasoning, but the reasoning was never routed anywhere a future reader would look before designing the P0-B operator surface. This document is that routing.

## Why it cannot be decided yet

P0-A's answer — refuse — is correct for P0-A and rests on an argument that does not obviously survive contact with the domain:

- the platform cannot distinguish a deliberate re-execution from a misclick on the wrong row;
- the charter asks only that an operator diagnose and retry *a failure*;
- capability beyond that reduces no named uncertainty and adds a way to lose work.

`[추론]` The third clause is what P0-B may falsify. A collection run that succeeded against stale upstream data, or a normalization run whose rules were later corrected, are cases where re-executing succeeded work is the operator's actual intent — and P0-A has no such cases because its handlers are synthetic and its effects carry no meaning.

## Scope

### Included

- Whether a terminal-and-successful job can be re-executed through the operator surface.
- What would distinguish that from safe retry: a different action, a confirmation, an explicit reason, or a new job carrying the same input.
- What the durable effect means on re-execution — suppression, a second effect, or a versioned one.

### Excluded

- Authorization and authentication. Nothing in P0 is authenticated, and *who* may re-execute is a separate question from *whether* the platform offers it.
- Scheduling and backfill design.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Refusing re-execution of succeeded work costs P0-B nothing, because creating a new job with the same input is always an adequate substitute. | A P0-B operator scenario requires re-execution to preserve the original job's identity or lineage, so that a new job is not equivalent. |
| H2: If re-execution is offered, `effect_key` suppression is the wrong default — an operator re-running deliberately wants the effect applied again. | A P0-B case appears where re-execution must be idempotent against the first run's effect, meaning one action cannot serve both intents. |

## Alternatives

- **Refuse, as P0-A does.** Cheapest, and loses nothing while effects carry no meaning.
- **A distinct action** — "run again" separate from "retry" — so the operator states which they mean rather than the platform inferring it.
- **A new job carrying the same input**, leaving the original untouched. Preserves history at the cost of a weaker link between the two runs.
- **Safe retry from any terminal state**, which P0-A rejected because it makes a misclick indistinguishable from an intent.

## Minimum experiment

### P0-A

Already done, and its boundary is worth stating: `JOB-008` case A asserts the refusal changes nothing, and `OPS-002` asserts the same through the operator surface with the response naming both the current and the required state. No re-execution path exists to test.

### P0-B

- Record whether any provisional decision use requires re-running a succeeded collection or normalization run.
- If one does, implement the smallest action that expresses the intent and test it against the effect semantics that exist by then.
- If none does, close this question by recording that the P0-A answer held, rather than by leaving it open indefinitely.

## Evidence requirements

- The concrete P0-B operator scenario that needs it, or a recorded finding that none does.
- What the durable effect must do on re-execution, tested against a real effect rather than a single-row synthetic one.
- Whether the original job's identity must be preserved.

## Exit condition

The team can state whether the operator surface offers re-execution, what distinguishes it from retry, and what happens to the durable effect — enough to write the operator action set in `PoC Contract 0.1`.

## Resolution

Not completed while status is `OPEN`. Resolution links the P0-B operator scenario that settled it, the accepted contract change if any, and the reasoning if the P0-A refusal is kept.
