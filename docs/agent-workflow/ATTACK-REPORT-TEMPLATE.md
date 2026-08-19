# REVIEW-TASK-XXX — Attack report

- Packet:
- Worker revision:
- Attacker:
- Date:
- Result: `PASS | FAIL | BLOCKED`

> **The tables below are a floor, not a ceiling.** The 2026-08-18 review this template
> describes runs to 351 lines, and its three blocking findings needed the room: each had to
> state the claim, the code that contradicted it, the command that showed it, and why the
> existing test passed anyway. A finding compressed into a table cell is a finding its
> reader cannot check. Fill the tables, then write.

## Reproduced worker evidence

| Claim | Command or procedure | Observed result | Evidence |
|---|---|---|---|
| | | | |

## Adversarial cases

| Case | Failure class | Expected constraint | Observed result | Severity | Reproduction |
|---|---|---|---|---|---|
| | `implementation | specification | assumption | evaluation | goal` | | | | |

## Scope and decision-boundary review

- Allowed-file compliance:
- Accepted-decision compliance:
- Unanswered consequential direction:
- Prohibited material exposure:

## Conclusion

Explain why the packet is `PASS`, `FAIL`, or `BLOCKED`. A pass is limited to the named packet criteria and performed attacks.

## Required follow-up

- New or revised packet:
- Open Question or Decision Packet update:
- Project State or contract update:

## Where this file belongs

Beside the experiment it attacks when there is one; under
`docs/agent-workflow/reviews/` when there is not. `reviews/README.md` has the reason.
Link it from the reviewed packet either way — a packet marked `ACCEPTED` without a
resolvable link fails `tests/environment/test_agent_packet_record.py`.

