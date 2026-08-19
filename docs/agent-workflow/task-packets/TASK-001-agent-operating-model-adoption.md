# TASK-001 — Adopt the isolated agent operating model on the current branch

- Status: `REWORK`
- Phase: P0-B
- Planner: none — see "How this packet came to exist" below
- Worker: main session, 2026-08-19
- Attacker: `adversarial-reviewer`
- Orchestrator: main session. `ORCHESTRATOR.md` says the role is the session that spawns the others; an earlier revision of this line named the project owner, which collapses the one action the role is defined by — REVIEW-TASK-001 F8
- Created: 2026-08-19
- Updated: 2026-08-19 (reworked after REVIEW-TASK-001 returned `FAIL`)

## How this packet came to exist

`[확인 사실]` **This packet was written after the work, not before it.** The owner assigned
the merge directly; no planner produced acceptance criteria in advance, and the worker and
the person recording this are the same session.

`[결정]` It is written anyway, and written as what it is. `docs/agent-workflow/README.md`
says work that changes an item accepted in `project-state.md` §4 requires the full flow, and
this work changes one. Recording the packet honestly is worth more than either pretending
the front half ran or leaving the first application of the model undocumented — which is the
gap `DP-013` lists as the proposal's own self-exemption. The planning separation did not
happen, and is recorded as not having happened.

`[확인 사실]` An earlier revision of this paragraph said "the independent attack below is real"
while the `Attack report:` field was still empty — an intention written in the present tense,
which is the first item on the list of things this project punishes. The attack has since run
and returned `FAIL`; [`REVIEW-TASK-001`](../reviews/REVIEW-TASK-001.md) F15 is the finding
against that sentence.

## Objective

Bring `b702c79` — the agent operating model held in isolation by `docs/branching.md` — onto
`6d1e965` as `agent/operating-model`, resolving the conflicts and the number collision, and
adapt it so that every claim it makes about this project is true of this project.

## Authority and dependencies

- Project State: [0.7, P0-B](../../project-state.md)
- Accepted decisions: [DP-013](../../decisions/DP-013-agent-workflow-and-project-memory.md),
  and [DP-011](../../decisions/DP-011-p0b-product-and-delivery-scope.md) for the delivery
  boundary the threshold is calibrated against
- Contracts: none
- Open Questions: none
- Owner decisions required: `none` — the owner instructed the merge and the adaptation on 2026-08-19
- Required evidence or environment: the checkout's virtualenv; `.venv/bin/python -m pytest`

## Scope

### Included

- `--no-ff` merge of `b702c79`, preserving it as a merge parent
- conflict resolution in `docs/project-state.md` and `docs/decisions/README.md`
- renumbering the incoming Decision Packet off the number `DP-006` already holds
- adapting the merged documents to the current project name, phase, roles, and enforcement
- one repository guard making the checkable part of the model executable

### Excluded

- any change to `main`, or a pull request toward it
- any change to `.claude/agents/` definitions
- automation beyond the single guard
- any product, platform, domain, or add-on code

### Allowed files

- `AGENTS.md`, `README.md`
- `docs/agent-workflow/**`
- `docs/conventions/project-memory.md`
- `docs/decisions/DP-013-agent-workflow-and-project-memory.md`, `docs/decisions/README.md`
- `docs/decisions/DP-TEMPLATE.md`, `docs/open-questions/OQ-TEMPLATE.md`, `docs/open-questions/README.md`
- `docs/project-state.md`, `docs/branching.md`
- `tests/environment/test_agent_packet_record.py`

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- everything under `experiments/`, `contracts/`, and `.claude/`

## Acceptance criteria

1. `b702c79` is a parent of the merge commit, so the original proposal remains readable.
2. No two Decision Packets claim the same number, and `DP-006` still resolves to the P0-A
   platform foundation packet everywhere it is referenced by number.
3. No document changed by this work uses `CosmaSignal` as the project's live name, claims
   phase P0-A, or claims the P0-A Completion Gate is still ahead. The name survives on
   purpose in superseded `DP-002`, in `docs/history/`, and in `DP-013`'s account of what the
   proposal said — `DP-007` left history untouched deliberately.
4. Every relative link in every changed document resolves, and every repository path a
   changed document names in backticks exists.
5. Each role states which part of its prohibition the harness enforces and which part is
   convention, and no convention is described as a control.
6. A threshold states which work requires the full flow and which does not.
7. `tests/environment/test_agent_packet_record.py` rejects an `ACCEPTED` packet with no
   resolvable attack report, and its positive controls fail when the validator is weakened.
8. `.venv/bin/python -m pytest tests/environment/ -q` passes.

## Verification

```sh
# Replayable commands only; never include secret values.
git log --oneline --graph -3 agent/operating-model     # b702c79 present as a merge parent
# Expect hits only in superseded DP-002, docs/history/, and DP-013's account of the proposal.
# This packet and its review are excluded: criterion 3 names the string it tests for.
git grep -n 'CosmaSignal' -- docs AGENTS.md README.md ':!docs/agent-workflow'
ls docs/decisions/                                     # one DP-006, one DP-013
.venv/bin/python -m pytest tests/environment/ -q
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.

## Worker handoff

- Changed files: see the two commits on `agent/operating-model` above `6d1e965`.
- Commands and results: recorded in the commit messages and in the attack report below.
- Evidence locations: the merge commit message for the conflicts and the number collision;
  `DP-013` §"What changed from the proposal" for every deviation from `b702c79`.
- Limitations and remaining risks: the planner separation did not happen for this packet, as
  stated above. Role laundering remains unenforceable; `DP-013` records it as a risk rather
  than solving it. Whether path-scoped `permissions` work in agent frontmatter is untested,
  so no planner binding is claimed.
- Newly discovered questions or blockers: `DP-009` is unused on every ref with no recorded
  reason, and was left unused. Whether `main` takes this work is a separate acceptance.

## Review

- Attack report: [REVIEW-TASK-001](../reviews/REVIEW-TASK-001.md)
- Result: `FAIL`
- Orchestrator disposition: **reworked, not accepted.** Two blocking and four major findings.
  The claims that were false in the present tense are corrected in the commit that records the
  report, repairing nothing — the `c0a266d` pattern. The defects themselves (the guard's path
  check and its section scoping, the threshold's overlap, `docs/p0-execution-plan.md`'s stale
  rows, the criteria that cannot fail) are repaired in the commit after it. This packet stays
  `REWORK` rather than `ACCEPTED`: no second independent review has run, and marking it
  `ACCEPTED` on a `FAIL` report would be the acceptance control failing in its first use.
