# DP-014 — Project memory scope, and the development-area exception

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-19 — answered as two separate questions, R1 and R2, with the options and tradeoffs presented)`
- Amends: [DP-013](DP-013-agent-workflow-and-project-memory.md) D5, and its §"What changed from the proposal" items 10 and 14 (the latter two on 2026-08-19, after this packet claimed them done without doing them)
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

**A consequence this packet first got wrong.** As first written, this section required two
operating facts — a subagent concurrency limit and a verification-before-handoff rule — to be
recorded in `project-state.md` §4 as the condition of the withdrawal, and recorded them.

`[결정]` **They were removed on 2026-08-19, by the owner, and the removal is the correct
outcome.** [`REVIEW-TASK-001-R3`](../agent-workflow/reviews/REVIEW-TASK-001-R3.md) F5 found that
neither appeared in any of `OQ-011`'s option lists: the owner was asked where facts belong and is
recorded as having accepted two constraints whose *content* was never put to them. `[측정]`
Their only provenance was one commit, and the "P0-A one-at-a-time rule" they referenced has no
record anywhere in this repository.

`[추론]` The removal is not a judgement that they are false — the owner had stated at least the
first of them in conversation. It is that `project-state.md` §4 is the register `AGENTS.md` reads
as constraints, and an entry there whose basis no reader can check is worse than an absent one.
That is this packet's own argument for R1, applied to this packet. If either constraint should
bind, it needs a decision with a basis, not a footnote to a different question.

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

- Benefit: the area exception is one sentence and touches no accepted hypothesis.
- Cost: nothing prevents a project fact from living only in a private store again. `[결정]` That
  is accepted. The convention says where facts belong; noticing when one has drifted is a
  reading problem, not a rule problem, and no rule here could have caught it either.
- Cost, realised: `[확인 사실]` the two constraints this packet first moved into the repository
  went back out the same day, so R1's narrowing currently leaves them recorded nowhere. That is
  the honest state, not a gap to paper over — a fact worth binding is worth its own decision.
- Risk, open: `[추론]` "operating method" is not sharply bounded, so the area exception could be
  stretched to cover work that does belong to an area. A draft of this packet carried a scope
  test for exactly that; it was removed because `OQ-011` never put it to the owner
  ([`REVIEW-TASK-001-R3`](../agent-workflow/reviews/REVIEW-TASK-001-R3.md) F5). The risk is
  therefore recorded and unmitigated, and the first ambiguous case is the one to ask about.

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
- `docs/project-state.md`: record both decisions in §4 and move `OQ-011` to `RESOLVED`.
  **Done.** The two operating facts recorded alongside them were removed the same day — see the
  R1 section above.
- `DP-013`: mark D5's private-memory clause amended. **Done.**
- `DP-013`: resolve §"What changed from the proposal" items 10 and 14. `[확인 사실]` This was
  marked **Done.** on 2026-08-19 and was not done — the commit touched D5 only, and
  [`REVIEW-TASK-001-R3`](../agent-workflow/reviews/REVIEW-TASK-001-R3.md) F3 found item 10 still
  asserting in bold that the owner had not been shown the rule, in the commit that showed it.
  **Done** now, and the false checklist entry is left visible rather than silently corrected: a
  checklist marked done by the session doing the work is an absence assertion with no positive
  control, and that is the second time this branch has produced one.
- `OQ-011`: `RESOLVED`, linking this packet. **Done.**
