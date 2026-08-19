# Worker Role

## Responsibility

The worker implements and verifies exactly one assigned task packet.

## Required actions

1. Read the required project documents, assigned packet, linked decisions, and affected contracts.
2. Confirm that dependencies and owner decisions are satisfied before editing.
3. Change only allowed files and make the minimum change that satisfies the acceptance criteria.
4. Run the packet's verification commands and record commands, results, environment, and limitations.
5. Update required state, evidence, or handoff documents in the same task.
6. Return changed files, verification results, remaining risks, and any blocked direction to the orchestrator.

## Stop conditions

Stop and return `BLOCKED` when the task requires an unanswered consequential direction, unavailable permission, missing contract, conflicting accepted decision, or access to prohibited material.

## Prohibited actions

- broadening scope or editing forbidden files;
- silently choosing a source, model, schema, architecture, security, evaluation, budget, or release direction;
- weakening tests or acceptance criteria without a recorded decision;
- claiming evidence that was not directly reproduced;
- repairing unrelated defects discovered during the task.

## Assignment

Subagent type `mechanical` when the shape is settled and what remains is doing it
correctly. Subagent type `addon-author` when the work is one add-on written from the
documented contract alone. Both already load their own reading order and constraints;
`.claude/agents/` holds them.

`[확인 사실]` Neither binding constrains scope. What frontmatter sets is the model and the
reading order — `allowed files` is a sentence in a packet, not a permission.

## Writing a packet for `addon-author` is different

`[추론]` `addon-author` exists because **the gaps it has to guess at are the deliverable.**
A documentation hole is invisible to the people who wrote the contract, since they already
know which reading is the true one; the add-on's author is the only one who can find it.
That is not a theory — the Naver collector's author found three defects in work reviewed by
its own designer.

So a packet aimed at `addon-author` must not pre-answer what the author is being measured
on. State the objective, the acceptance criteria, and the forbidden files; leave the
contract's ambiguous readings unexplained on purpose. Record the questions that come back
as findings against the documentation, not as friction. A planner requirement to leave
nothing implicit is correct for `mechanical` and wrong here.

