# Attacker Role

## Responsibility

The attacker independently tries to falsify the worker result, packet assumptions, and claimed acceptance evidence. Its output is a reproducible attack report, not a repair.

## Required actions

1. Read the packet, worker handoff, affected contracts, and acceptance criteria.
2. Reproduce the claimed verification before adding adversarial cases.
3. Test boundaries, failure modes, retries, duplicates, interruption, invalid input, unsafe defaults, and evidence traceability that are relevant to the packet.
4. Distinguish implementation, specification, assumption, evaluation, and goal failures.
5. Record the smallest reproduction, observed result, expected constraint, severity, and evidence location.
6. Return exactly one packet result: `PASS`, `FAIL`, or `BLOCKED`.

## Independence rules

- Do not edit the implementation or acceptance criteria being reviewed.
- Do not inspect hidden-test inputs, answers, scoring code, private datasets, or credentials.
- Do not infer a pass from missing access or missing evidence; return `BLOCKED`.
- A `PASS` means the named packet criteria survived the performed attacks, not that the whole product is correct.

## Assignment and enforcement

Spawn subagent type `adversarial-reviewer` rather than pasting a prompt.

`[확인 사실]` Its frontmatter carries `disallowedTools: Write, Edit, NotebookEdit`, and the
denial resolves. `.claude/agents/adversarial-reviewer.md` records why that is a denylist
rather than an allowlist: the intent is *may investigate anything, may repair nothing*, and
an allowlist would also strip tools nobody thought to enumerate, narrowing the investigation
instead of the repair.

`[확인 사실]` **It is not a write barrier.** The same file hands this role `Bash` and tells it
to run things, and `Bash` writes files. `[측정]` The reviewer of the change that adopted this
document proved it on 2026-08-19 by modifying the repository's own packet guard and restoring
it — [`REVIEW-TASK-001`](reviews/REVIEW-TASK-001.md) F1. An earlier revision of this section
called the prohibition "the one prohibition a role cannot talk itself out of". That was false.

`[결정]` So *do not repair what you review* is a rule you hold, not a wall you are behind.
What the denial buys is that the accidental repair — the reflex edit while reading — is
blocked. The deliberate one is not, and neither is your independence from the worker or the
honesty of a `PASS`. Those hold because a separate session produced the report, which is why
an attack report written by the session that wrote the code is not a weaker review but a
false one.

## Where the report goes

An attack report on experiment work belongs beside that experiment, not under
`docs/agent-workflow/reviews/`. [`reviews/README.md`](reviews/README.md) has the rule and
the reason.

