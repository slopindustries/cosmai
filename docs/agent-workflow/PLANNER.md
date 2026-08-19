# Planner Role

## Responsibility

The planner converts one accepted objective into one bounded, verifiable task packet. It does not implement product code and does not resolve consequential direction.

## Required output

- one task packet created from `TASK-PACKET-TEMPLATE.md`;
- one-line worker and attacker prompts copied from `PROMPTS.md` and filled with the packet path;
- explicit allowed and forbidden files;
- observable acceptance criteria and replayable verification commands;
- linked decisions, contracts, evidence, dependencies, and known risks.

## Planning rules

- Prefer the smallest task that can produce decision-relevant evidence or accepted behavior.
- Do not include speculative features, unrelated cleanup, or hidden requirements.
- If an unresolved consequential direction changes the packet, return it to the orchestrator as `BLOCKED` with a draft owner question.
- Separate implementation acceptance from broader product success. A passing packet does not close an Open Question unless the named exit evidence exists.

## Prohibited actions

- editing product code or test expectations to make the plan appear complete;
- assigning multiple unrelated objectives in one packet;
- giving the worker access to private evaluation answers or attacker-only material;
- leaving scope, allowed files, verification, or stopping conditions implicit.

## Assignment and the enforcement this role does not have

`[확인 사실]` The planner has **no `.claude/agents/` definition, and its central
prohibition cannot be given one.** `disallowedTools` denies a tool, not a path: the
planner needs `Write` to produce the packet, so denying `Write` denies the packet.

`[결정]` No binding is claimed instead of a plausible one. Whether path-scoped
`permissions` work in agent frontmatter is unverified in this repository, and `fcf4b8a`
recorded what assuming otherwise costs — `effort`, `reasoningEffort`, and
`reasoning_effort` are all silently ignored, so a setting that looked applied was not. A
frontmatter key nobody tested is worse than an absent one.

`[추론]` The planner's separation from implementation is therefore held by whoever assigns
the work, and the only observable evidence of it is that the packet's acceptance criteria
were written before the code and by a different session. That evidence is worth producing
deliberately, because the failure it prevents has already happened here: the 2026-08-18
adversarial review's first blocking finding was an acceptance criterion satisfied by the
add-on's cooperation rather than by the platform, written and read by the same person.

