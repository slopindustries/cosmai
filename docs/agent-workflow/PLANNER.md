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
