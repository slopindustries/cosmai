# Agent Operating Model

This directory defines how agent sessions are separated, assigned, and reviewed. It is an operating protocol, not a product architecture.

## Required flow

```text
Consequential ambiguity
→ orchestrator records and asks the project owner
→ owner answer is recorded as a decision
→ planner writes one bounded task packet
→ worker implements and verifies only that packet
→ attacker tries to falsify the result
→ orchestrator accepts the result or requests a new packet
```

If no consequential ambiguity exists, the orchestrator may start at planning. `FAIL` produces a new or revised packet; the attacker does not repair the reviewed work.

## Roles

| Role | Owns | Must not do |
|---|---|---|
| [Orchestrator](ORCHESTRATOR.md) | owner questions, role assignment, boundary enforcement, final acceptance | silently choose consequential direction or implement a packet it is accepting |
| [Planner](PLANNER.md) | one bounded task packet and one-line role prompts | implement product code or accept its own plan |
| [Worker](WORKER.md) | one packet's allowed changes and verification | expand scope, edit forbidden files, or choose blocked direction |
| [Attacker](ATTACKER.md) | independent falsification and reproducible review result | fix the reviewed implementation or inspect private evaluation material |

## Required artifacts

- [Task Packet Template](TASK-PACKET-TEMPLATE.md)
- [Attack Report Template](ATTACK-REPORT-TEMPLATE.md)
- [One-Line Prompts](PROMPTS.md)
- [Project Memory Convention](../conventions/project-memory.md)

Create active packets under `docs/agent-workflow/task-packets/` and review reports under `docs/agent-workflow/reviews/`. Do not create an assignment until its dependencies and consequential decisions are recorded.

## Result states

- `PASS`: all packet acceptance criteria were tested and no blocking contradiction was found.
- `FAIL`: a reproducible defect, scope violation, or unmet criterion was found.
- `BLOCKED`: the result cannot be determined because a named dependency, permission, environment, or owner decision is missing.

Only the orchestrator closes a packet after reading the worker evidence and attacker report.
