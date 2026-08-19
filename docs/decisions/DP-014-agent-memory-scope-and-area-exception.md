# DP-014 — Project memory scope, and the development-area exception

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-19 — answered as two separate questions, R1 and R2, with the options and tradeoffs presented)`
- Amends: [DP-013](DP-013-agent-workflow-and-project-memory.md) D5, and its §"What changed from the proposal" items 10 and 14
- Resolves: [OQ-011](../open-questions/OQ-011-agent-memory-and-area-boundary.md)
- Affected contracts: none
- Affected acceptance tests: none

## Decision question

`DP-013`'s own adoption wrote two rules without putting them to the owner, which is the thing
`DP-013` exists to prevent. [`REVIEW-TASK-001`](../agent-workflow/reviews/REVIEW-TASK-001.md) F4
found them by diffing rather than by reading the disclosure list that claimed to be complete.
Both were marked `[가설]` proposed where they live and asked as `OQ-011`. Do they bind, and in
what form?

## Evidence and reasoning

- `[확인 사실]` Neither rule was in `b702c79`. Both were written while adapting the merge, and
  neither appeared in `DP-013`'s deviation list until the review added them as items 10 and 14.
- `[확인 사실]` R2's worked example is the branch that introduced it. A rule that exempts its own
  change from a rule `AGENTS.md` states is the case where inferring agreement is least
  defensible, which is why the review flagged it hardest.
- `[측정]` The concrete problem R1 targets is real and current: operating constraints for this
  project — a subagent concurrency limit and a verification-before-handoff rule — were living
  only in an assistant's private memory store, where no one on the team could read or
  contradict them and where a change of session loses them.
- `[확인 사실]` `docs/areas/README.md` labels its five-area split a `[가설]` and names the P0
  Charter question it is a draft answer to: *which component and process boundaries are useful
  rather than ceremonial*. All five areas map to a code directory under
  `experiments/integrated-p0/`.

## Decision

### R1 — project memory scope

`[결정]` **The repository half binds; the claim on a private store is withdrawn.**

`docs/conventions/project-memory.md` states where a project fact must live and does not
regulate what any private memory store may hold. The routing table and the test — would a new
session, or a different person, be wrong without it? — carry the whole of the intended effect.

Rejected: the original two-part form. `[추론]` A repository convention constraining an
individual's tooling reaches past what the document can back up and past anything anyone can
check, and it buys nothing the repository half does not already buy. A fact recorded in the
repository is recorded whether or not a private copy also exists.

Rejected: withdrawing the section entirely. The routing question is worth answering explicitly
even though `DP-013` D1 already makes repository documents the durable record.

**Consequence, and it is not optional.** Withdrawing the constraint is only honest if the facts
it was aimed at actually reach the repository. The subagent concurrency limit and the
verification-before-handoff rule are recorded in
[`project-state.md`](../project-state.md) §4 by this decision.

### R2 — the development-area exception

`[결정]` **Recorded as an exception, as written.**

Documents that change the project's operating method — `docs/branching.md`,
`docs/agent-workflow/`, `docs/conventions/project-memory.md` — belong to no development area,
and `<area>/<what>` does not reach them. `agent/operating-model` is the example.

Rejected: a sixth area. `[추론]` It would place a directory owning no code beside five that own
code, inside the very table `docs/areas/README.md` calls a hypothesis for P0-B to judge.
Answering "is this boundary useful or ceremonial" by adding a boundary prejudges it.

Rejected: withdrawing the exception. Forcing governance work into an existing area would put a
branch name in the wrong area, and the areas doc is what branch names are read against.

`docs/areas/README.md` is unchanged: the five areas are unchanged, and the exception is about
what the naming rule does **not** cover rather than about the areas themselves.

## Tradeoffs and risks

- Benefit: the private-memory constraint's removal costs nothing, because the facts it targeted
  are now in `project-state.md` where they can be reviewed and contradicted.
- Benefit: the area exception is one sentence and touches no accepted hypothesis.
- Cost: nothing prevents a project fact from living only in a private store again. `[결정]` That
  is accepted. The convention says where facts belong; noticing when one has drifted is a
  reading problem, not a rule problem, and no rule here could have caught it either.
- Risk: `[추론]` "operating method" is not sharply bounded, so the area exception could be
  stretched to cover work that does belong to an area. The test is whether the work changes a
  code directory; if it does, it has an area.

## Remaining uncertainty

- Whether the five-area split survives P0-B's synthesis is unchanged by this decision and
  remains the open question `docs/areas/README.md` records.
- `[확인 사실]` This packet does not address whether `main` takes the branch. That is a separate
  acceptance under [branching](../branching.md), and `TASK-001` is `REWORK` rather than
  `ACCEPTED`.

## Required changes

- `docs/conventions/project-memory.md`: narrow the section to the repository half, drop the
  proposed marker. **Done.**
- `docs/branching.md`: drop the proposed marker, record the exception as accepted. **Done.**
- `docs/project-state.md`: record both decisions in §4, record the two operating facts R1's
  narrowing requires be moved into the repository, and move `OQ-011` to `RESOLVED`. **Done.**
- `DP-013`: mark D5's private-memory clause amended, and items 10 and 14 resolved. **Done.**
- `OQ-011`: `RESOLVED`, linking this packet. **Done.**
