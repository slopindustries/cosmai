# DP-006 — Documented Memory and Role-Separated Agent Workflow

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-18
- Owners: Project owner and project team
- Owner confirmation: `CONFIRMED (project owner request, 2026-08-18)`
- Related Open Questions: all consequential project-direction questions
- Affected contracts: agent task packets and review reports
- Affected acceptance tests: none directly

## Decision question

How should project memory, consequential direction changes, and agent responsibilities be controlled so that work does not depend on conversation history or an agent's unstated assumptions?

## Evidence and reasoning

- `[확인 사실]` The repository already separates current state, Open Questions, Decision Packets, contracts, experiments, and curated history.
- `[결정]` The project owner requires important memory to be documented and important directions to be asked rather than silently selected.
- `[결정]` The project owner requires planner, worker, and attacker roles that can be assigned and reviewed independently.
- `[추론]` Reusing the existing authoritative document types avoids a second, conflicting source of truth.
- `[추론]` A bounded task packet and an independent attack report make scope and acceptance evidence reviewable without exposing private evaluation material.

## Decision

`[결정]` Adopt the following operating rules for P0 and later phases until superseded:

1. Repository documents are the durable project memory. A consequential fact, decision, risk, blocker, result, or handoff is not durable until it is recorded in its authoritative document.
2. Consequential directions are presented to the project owner with material options, recommendation, evidence, and tradeoffs. Implementation that depends on the answer waits for explicit confirmation.
3. Agent work is separated into orchestrator, planner, worker, and attacker roles defined under `docs/agent-workflow/`.
4. A planner issues one bounded task packet. A worker implements only that packet. An attacker independently tries to falsify the result. The orchestrator accepts the result or requests a new packet.
5. Raw conversations, session snapshots, credentials, private evaluation material, and private datasets are not project memory and are not committed.

## Consequential direction boundary

The following always require an owner question when they are new, changed, or ambiguous:

- product goal, decision consumer, phase, schedule, or material scope;
- source selection, collection method, terms or rights basis, retention, or personal-data policy;
- model strategy, canonical entity or schema meaning, quality threshold, or human-review boundary;
- architecture, persistence, external service, security, credential, or deployment boundary;
- evaluation protocol, hidden-test access, material budget, release, or gate criteria.

Names, formatting, private helper structure, and equivalent internal algorithms may remain local implementation choices when they do not change observable behavior or an accepted constraint.

## Rejected alternatives

- A single free-form memory file was rejected as the only record because it would duplicate current state, decisions, evidence, and history without clear authority.
- Letting each agent infer consequential choices was rejected because the resulting behavior would be difficult to audit and could silently change project direction.
- Combining planning, implementation, and acceptance in one role was rejected as the default because it weakens independent scope and failure review.

## Tradeoffs and risks

- Benefit: decisions and handoffs survive session changes and team turnover.
- Benefit: user-owned direction remains distinguishable from implementation discretion.
- Cost: consequential work pauses while a question is unanswered.
- Cost: each completed packet requires a small amount of documentation and independent review.
- Risk: too many questions can stall routine implementation.
- Control: the consequential boundary is explicit; reversible local choices do not require owner approval.

## Remaining uncertainty

- The project may later automate packet and report validation, but no automation is required by this decision.
- Team staffing and the number of parallel workers remain scheduling choices within the accepted project scope.

## Required changes

- Project State: record the memory and agent workflow decision.
- Agent instructions: add owner-question, memory, and role-boundary rules.
- Templates: add task packet and attack report templates.
- Repository guide: link the new convention and operating model.
- Implementation handoff: use the workflow for new agent-assigned work after this decision.
