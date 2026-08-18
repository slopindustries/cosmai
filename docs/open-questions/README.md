# Open Questions

An Open Question is a consequential uncertainty that must not be silently settled in implementation.

When the question changes a consequential project direction, the owner must be shown the material options, recommendation, evidence, tradeoffs, and blocked work. Implementation remains paused until the answer is recorded in a Decision Packet. Collecting bounded evidence that was already authorized may continue; choosing the direction may not.

Use [OQ-TEMPLATE.md](OQ-TEMPLATE.md) for new questions.

## Status lifecycle

```text
OPEN → EXPLORING → RESOLVED
                 ↘ DEFERRED
                 ↘ SUPERSEDED
```

- `OPEN`: the consequential uncertainty is recorded but no bounded experiment is running.
- `EXPLORING`: at least one linked experiment is actively collecting evidence.
- `RESOLVED`: an accepted Decision Packet records the scoped answer and required changes.
- `DEFERRED`: work is intentionally postponed with a reason, revisit trigger, and named blocker.
- `SUPERSEDED`: another Open Question replaces this framing and is linked from the record.

Starting code does not by itself change the status. Update the Open Question when the experiment begins, and do not mark it `RESOLVED` without a Decision Packet.

Each question records:

- why it matters and what it blocks;
- hypotheses and alternatives;
- falsification criteria;
- the minimum useful experiment;
- evidence and environment requirements;
- an explicit exit condition.

Facts, measurements, inferences, hypotheses, and decisions must use the shared definitions in [Evidence Labels](../conventions/evidence-labels.md). These labels describe the role of a claim and are not a confidence scale.

When evidence is sufficient, write a Decision Packet under `docs/decisions/`, update `docs/project-state.md`, and change or version affected contracts and acceptance tests.
