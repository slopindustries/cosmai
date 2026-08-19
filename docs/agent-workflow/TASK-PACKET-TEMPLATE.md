# TASK-XXX — Task title

- Status: `DRAFT | READY | IN_PROGRESS | WORKER_DONE | REVIEWING | ACCEPTED | REWORK | BLOCKED`
- Phase:
- Planner:
- Worker:
- Attacker:
- Orchestrator:
- Created:
- Updated:

`[확인 사실]` Four things in this file are checked by
`tests/environment/test_agent_packet_record.py`: that `Status` holds one of the values
above, and — when it is `ACCEPTED` — that `Attack report` carries a markdown link, that the
link names a path inside this repository, and that the path exists. `Result` must be `PASS`.
Everything else here is convention, which `docs/agent-workflow/README.md` lists rather than
implies.

`[결정]` A prose reference is not enough for an `ACCEPTED` packet. An attack report lives in
this repository — beside the experiment it attacks, or under `reviews/` — so a link is always
available for a real one, and "reviewed manually, no defects found" is the unverifiable claim
this guard exists to reject.

Not every change needs a packet. `docs/agent-workflow/README.md` states which work does.

## Objective

State one observable outcome.

## Authority and dependencies

- Project State:
- Accepted decisions:
- Contracts:
- Open Questions:
- Owner decisions required: `none | links`
- Required evidence or environment:

## Scope

### Included

-

### Excluded

-

### Allowed files

-

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
-

## Acceptance criteria

1.

## Verification

```sh
# Replayable commands only; never include secret values.
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.

## Worker handoff

- Changed files:
- Commands and results:
- Evidence locations:
- Limitations and remaining risks:
- Newly discovered questions or blockers:

## Review

- Attack report:
- Result: `PASS | FAIL | BLOCKED`
- Orchestrator disposition:
