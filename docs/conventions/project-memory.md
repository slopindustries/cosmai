# Project Memory Convention

## Purpose

Project memory lives in reviewable repository documents, not in a person's or model's conversation memory. Record a consequential item in the same work session in which it becomes known, changes, or blocks progress.

## Authoritative destinations

| Information | Authoritative location |
|---|---|
| Current phase, accepted constraints, active blockers | `docs/project-state.md` |
| Consequential uncertainty | `docs/open-questions/` |
| Owner-confirmed choice, rationale, tradeoffs | `docs/decisions/` |
| Versioned interface or data meaning | `contracts/` |
| Hypothesis, procedure, measurement, failure evidence | `experiments/` |
| Non-authoritative background and superseded rationale | `docs/history/` |
| Assigned scope, allowed files, verification, handoff | task packet under `docs/agent-workflow/task-packets/` |
| Independent falsification result | attack report under `docs/agent-workflow/reviews/` |

Do not duplicate the same claim across documents. Link to the authoritative record and summarize only what the reader needs.

## Required recording rules

- Record a consequential direction as an Open Question before implementation chooses it.
- Ask the project owner with material options, recommendation, evidence, tradeoffs, and the work that is blocked.
- After the answer, create or update a Decision Packet and then update Project State and affected contracts.
- Record measurements with input identity, environment, procedure, capture time, and limitations.
- Record unfinished work, blockers, and handoff state before ending a task.
- If a new fact invalidates an accepted premise, reopen the affected question or decision explicitly; do not edit history to make the conflict disappear.

## Prohibited memory

Never commit raw chat transcripts, session snapshots, credentials, tokens, cookies, private evaluation answers, private datasets, or unredacted personal data. Preserve only the minimum redacted fact, hash, reference, or decision needed by the project.

## Completion check

A task with a consequential result is incomplete until its authoritative record and links are updated. “Discussed earlier,” “the agent remembers,” and an unlinked chat message are not completion evidence.
