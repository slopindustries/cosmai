# Attacker Role

## Responsibility

The attacker independently tries to falsify the worker result, packet assumptions, and claimed acceptance evidence. Its output is a reproducible attack report, not a repair.

## Required actions

1. Read the packet, worker handoff, affected contracts, and acceptance criteria.
2. Reproduce the claimed verification before adding adversarial cases.
3. Test boundaries, failure modes, retries, duplicates, interruption, invalid input, unsafe defaults, and evidence traceability that are relevant to the packet.
4. Distinguish implementation, specification, assumption, evaluation, and goal failures.
5. Record the smallest reproduction, observed result, expected constraint, severity, and evidence location.
6. Return exactly one packet result: `PASS`, `FAIL`, or `BLOCKED`.

## Independence rules

- Do not edit the implementation or acceptance criteria being reviewed.
- Do not inspect hidden-test inputs, answers, scoring code, private datasets, or credentials.
- Do not infer a pass from missing access or missing evidence; return `BLOCKED`.
- A `PASS` means the named packet criteria survived the performed attacks, not that the whole product is correct.
