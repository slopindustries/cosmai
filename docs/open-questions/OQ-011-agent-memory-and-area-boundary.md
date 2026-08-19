# OQ-011 — Two rules the operating-model adoption wrote without asking

- Status: `RESOLVED`
- Priority: low for delivery, immediate for the record
- Owner: project owner
- Owner decision: `CONFIRMED ([DP-014](../decisions/DP-014-agent-memory-scope-and-area-exception.md))`
- Blocks: nothing. Neither rule blocked work while open; both are now in force in the form DP-014 records.
- Related experiments: none
- Resolution Decision Packet: [DP-014](../decisions/DP-014-agent-memory-scope-and-area-exception.md), amending [DP-013](../decisions/DP-013-agent-workflow-and-project-memory.md)

## Question

`DP-013` requires that a consequential direction be put to the owner before implementation
chooses it. Two rules were added by the adoption of that very packet without being put to
anyone. Does the owner adopt them, and in what form?

**R1 — private memory.** `docs/conventions/project-memory.md` says a private memory store
"must not be the only place holding a project constraint, a concurrency limit, a verification
requirement, or a decision."

**R2 — the area exception.** `docs/branching.md` says documents that change the project's
operating method belong to no development area, so `<area>/<what>` does not apply to them, and
gives `agent/operating-model` as the example.

## Why this surfaced

`[확인 사실]` [`REVIEW-TASK-001`](../agent-workflow/reviews/REVIEW-TASK-001.md) F4 found five
substantive changes missing from `DP-013`'s list of deviations from `b702c79`, and identified
these two as consequential. The reviewer's §"Scope and decision-boundary review" records that
`TASK-001`'s "Owner decisions required: `none`" was wrong.

`[추론]` R2 is the sharper of the two, because **its worked example is the branch that
introduced it.** A rule that exempts the change carrying it from a rule `AGENTS.md` states is
the one case where inferring the owner's agreement is least defensible.

## Scope

### Included

- whether R1 binds, and whether it reaches an agent's private store or only the repository side
- whether R2 becomes a recorded exception, a new sixth area, or is withdrawn
- whether `docs/areas/README.md` changes if R2 stands — it currently names five areas, each
  mapping to a code directory, and was not updated

### Excluded

- the rest of `DP-013`, which the owner's 2026-08-19 instruction covers
- whether `main` takes this work — a separate acceptance under `docs/branching.md`

## Alternatives

**R1.**

1. **As written.** A project fact must exist in the repository; a private store may mirror it
   but not own it.
2. **Repository side only.** State where project facts belong and say nothing about private
   stores. Same practical effect, no claim on anyone's tooling.
3. **Withdraw.** `AGENTS.md` already forbids committing transcripts, and `DP-013` D1 already
   makes repository documents the durable record.

**R2.**

1. **Recorded exception, as written.** Operating-method documents belong to no area.
2. **A sixth area.** Something like `project/` or `process/`, added to
   `docs/areas/README.md`. Makes the branch-name rule uniform again; adds an area with no code.
3. **Withdraw.** Pick an existing area for such work, or accept that branch names for it are
   irregular and unnamed.

## Owner question

- **Decision needed:** adopt, narrow, or withdraw R1 and R2, independently of each other.
- **Options and tradeoffs:** above. R1 option 2 gets the benefit without the reach. R2 option 2
  keeps one rule instead of a rule plus an exception, at the cost of an area that owns no code —
  and `docs/areas/README.md` calls its five-area split a `[가설]` the P0-B synthesis is meant to
  judge, so adding a sixth would prejudge that.
- **Recommendation and evidence:** R1 option 2 and R2 option 1. `[추론]` R1's value is entirely
  in the repository half — it exists because project facts were sitting only in an assistant's
  private memory, and stating where they belong fixes that without constraining tooling nobody
  reviewed. R2 option 1 because a recorded exception is cheap and honest, whereas a sixth area
  would put a process directory beside five code directories and weaken the question
  `docs/areas/README.md` exists to answer.
- **Work blocked until answer:** none. Both rules are written and both carry a pointer here
  saying they are proposed. `[결정]` Nothing waits on this, which is exactly why it must not be
  left implicit — an unasked question with no deadline is the kind that becomes a constraint by
  default.

## Exit condition

A Decision Packet amending `DP-013` records the owner's answer for R1 and R2, the affected
documents drop their "proposed" markers or the rules are removed, and `docs/areas/README.md` is
updated if R2 option 2 is chosen.

## Resolution

- Outcome: **R1 — option 2, the repository half only.** The rule states where a project fact
  belongs and no longer regulates what a private memory store may hold.
- `[확인 사실]` `DP-014` first attached a condition to that narrowing — two operating facts moved
  into `project-state.md` §4 — and the owner removed both on 2026-08-19. Neither appeared in the
  §Alternatives above, so answering *where facts belong* had been recorded as accepting *what two
  particular facts say*. See [`REVIEW-TASK-001-R3`](../agent-workflow/reviews/REVIEW-TASK-001-R3.md) F5.
- Outcome: **R2 — option 1, recorded as an exception.** A sixth area was rejected because it
  would answer `docs/areas/README.md`'s open hypothesis by adding a boundary to it.
  `docs/areas/README.md` is unchanged.
- Decision Packet: [DP-014](../decisions/DP-014-agent-memory-scope-and-area-exception.md),
  accepted 2026-08-19.
