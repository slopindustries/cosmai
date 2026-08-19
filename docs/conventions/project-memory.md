# Project Memory Convention

- 문서 지위: 활성 프로젝트 convention
- Governing decision: [DP-013](../decisions/DP-013-agent-workflow-and-project-memory.md)
- 최종 수정일: 2026-08-19

## Purpose

Project memory lives in reviewable repository documents, not in a person's or model's
conversation memory. Record a consequential item in the same work session in which it
becomes known, changes, or blocks progress.

## Authoritative destinations

| Information | Authoritative location |
|---|---|
| Current phase, accepted constraints, active blockers | `docs/project-state.md` |
| Consequential uncertainty | `docs/open-questions/` |
| Owner-confirmed choice, rationale, tradeoffs | `docs/decisions/` |
| Versioned interface or data meaning | `contracts/` |
| Hypothesis, procedure, measurement, failure evidence | `experiments/` |
| How a recurring kind of work is done, and what it must show before review | `docs/conventions/` |
| Agent role constraints the harness actually enforces | `.claude/agents/` |
| Non-authoritative background and superseded rationale | `docs/history/` |
| Assigned scope, allowed files, verification, handoff | task packet under `docs/agent-workflow/task-packets/` |
| Independent falsification result | beside the experiment it attacks; `docs/agent-workflow/reviews/` when there is no experiment |

Do not duplicate the same claim across documents. Link to the authoritative record and
summarize only what the reader needs.

`[결정]` **A convention document that already carries scope, required evidence, and a
review checklist is that path's packet.** [Collector integration
handoff](collector-integration-handoff.md) §6–§8 is the collector integration path's. A
second packet over the same work produces two records that can disagree, and the one that
disagrees is the one somebody will follow.

## What does not belong in an agent's private memory

`[결정]` A fact about **this project** belongs in this repository. An assistant's or a
person's private memory store may hold how the owner prefers to be addressed, which
language a reply is written in, or how a command behaves on one machine. It must not be the
only place holding a project constraint, a concurrency limit, a verification requirement,
or a decision.

`[추론]` The test is whether a new session, or a different person, would be wrong without
it. If so it is project memory, and private memory is the wrong home for two reasons: it
does not survive a change of session or of person, and it cannot be contradicted by anyone
who cannot read it. A constraint nobody can review is a constraint nobody can correct.

## Required recording rules

- Record a consequential direction as an Open Question before implementation chooses it.
- Ask the project owner with material options, recommendation, evidence, tradeoffs, and the
  work that is blocked.
- After the answer, create or update a Decision Packet and then update Project State and
  affected contracts.
- Record measurements with input identity, environment, procedure, capture time, and
  limitations.
- **Where a control is claimed, record what it does not cover.** An overstated control is
  the defect this project produces most often, and a recorded absence is worth more than a
  guard that reads stronger than it is.
- Record unfinished work, blockers, and handoff state before ending a task.
- If a new fact invalidates an accepted premise, reopen the affected question or decision
  explicitly; do not edit history to make the conflict disappear.

## Prohibited memory

Never commit raw chat transcripts, session snapshots, credentials, tokens, cookies, private
evaluation answers, private datasets, or unredacted personal data. Preserve only the minimum
redacted fact, hash, reference, or decision needed by the project.

## Completion check

A task with a consequential result is incomplete until its authoritative record and links
are updated. "Discussed earlier," "the agent remembers," and an unlinked chat message are
not completion evidence.

`[확인 사실]` One narrow part of this is executable rather than trusted:
`tests/environment/test_agent_packet_record.py` fails the suite when a task packet claims
`ACCEPTED` without a resolvable attack-report link and a `PASS` result. Nothing checks that
a packet exists for a given piece of work, or that its report is any good.
`docs/agent-workflow/README.md` lists what is enforced and what is convention, separately
and on purpose.
