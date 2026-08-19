# TASK-XXX — Task title

- Status: `DRAFT | READY | IN_PROGRESS | WORKER_DONE | REVIEWING | ACCEPTED | REWORK | BLOCKED`
- Phase:
- Planner:
- Worker:
- Attacker:
- Orchestrator:
- Created:
- Updated:

`[확인 사실]` What `tests/environment/test_agent_packet_record.py` checks, exactly: `Status`,
`Attack report`, and `Result` must each appear **at most once** in the file — a duplicate is its
own defect, whatever its position, which is how the three override bypasses
[`REVIEW-TASK-001`](reviews/REVIEW-TASK-001.md) F3 found are closed without parsing heading
boundaries. `Status` must hold one of the values above. When it is `ACCEPTED`, `Attack report`
must carry a markdown link whose target — `#fragment` stripped, then resolved — lies **inside
this repository**, is a file rather than a directory, and exists; and `Result` must be `PASS`.

`[확인 사실]` It does **not** judge whether the linked file is a credible report, whether a
packet exists at all for a given piece of work, or whether the attacker was independent of the
worker. `docs/agent-workflow/README.md` lists what is convention rather than implying it.

`[확인 사실]` An earlier revision of this note counted the checks wrong and described the
containment test the guard did not yet have. F2 of the review is the finding; the guard now has
it, and rejects `/etc/hosts`, a `..` escape out of the tree, and a directory.
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
