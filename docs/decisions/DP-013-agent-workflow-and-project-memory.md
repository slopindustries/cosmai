# DP-013 — Documented Memory and Role-Separated Agent Workflow

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project owner and project team
- Owner confirmation: `CONFIRMED (project owner, 2026-08-19 — scope: the instruction to merge b702c79 onto 6d1e965 and adopt it as far as it helps this project. The adapted text below was NOT reviewed clause by clause; §Decision's seven rules, the consequential boundary, and the threshold are in force on that instruction and nothing narrower.)`
- Origin: `b702c79` on `feat/agent-operating-model`, written 2026-08-18, held in isolation by [branching](../branching.md) after being reverted from `main` by agreement
- Renumbered: proposed as `DP-006`, which [DP-006](DP-006-p0a-platform-foundation.md) already held
- Related Open Questions: [OQ-011](../open-questions/OQ-011-agent-memory-and-area-boundary.md) — two rules this packet's own adoption wrote without asking. Otherwise none: this decision governs how consequential questions are asked and recorded, not the answer to any one of them.
- Affected contracts: agent task packets and review reports
- Affected acceptance tests: `tests/environment/test_agent_packet_record.py`

## Decision question

How should project memory, consequential direction changes, and agent responsibilities be
controlled so that work does not depend on conversation history or an agent's unstated
assumptions?

## Evidence and reasoning

- `[확인 사실]` The repository already separates current state, Open Questions, Decision
  Packets, contracts, experiments, and curated history.
- `[결정]` The project owner requires important memory to be documented and important
  directions to be asked rather than silently selected.
- `[결정]` The project owner requires planner, worker, and attacker roles that can be
  assigned and reviewed independently.
- `[추론]` Reusing the existing authoritative document types avoids a second, conflicting
  source of truth.
- `[추론]` A bounded task packet and an independent attack report make scope and acceptance
  evidence reviewable without exposing private evaluation material.

### What the repository already showed before this was merged

- `[확인 사실]` `27f712b` and `c0a266d` ran this flow's back half on 2026-08-18 without
  these documents: a reviewer with no write access attacked the work, returned ten findings,
  the report was committed beside the experiment rather than summarized into it, and the
  follow-up commit repaired nothing — it corrected only the claims that were false. The
  worker/attacker separation is therefore existing practice getting a name, not a new cost.
- `[확인 사실]` That review's first blocking finding is the measurement behind the
  planner/worker split: an add-on fetching 12 times and emitting 600 items against
  `max_pages=2, max_records=3` succeeded, because `max_pages` and `max_records` are enforced
  nowhere. One session wrote the acceptance criterion and the code that satisfied it.
- `[추론]` The diagnosis is the **author's**, not the reviewer's, and it is quoted here as an
  inference rather than a finding: *"the add-on cooperated" was read as "the platform
  enforced". That is the exact reading the experiment was designed to avoid, made by the person
  who designed it.* — [`EXP-003`](../../experiments/integrated-p0/EXP-003-capability-layer.md)
  §"Three defects", added by `c0a266d`. An earlier revision of this packet attributed it to the
  reviewer and labelled it `[확인 사실]`; [`REVIEW-TASK-001`](../agent-workflow/reviews/REVIEW-TASK-001.md)
  F6 is the correction. The accurate version is the stronger one — an independent reviewer
  measured the gap and the author, reading the measurement, named the mechanism. That is the
  split working.
- `[확인 사실]` **No role prohibition in this model is structural.** An earlier revision of
  this packet said one was — `adversarial-reviewer`'s `disallowedTools: Write, Edit,
  NotebookEdit` — and [`REVIEW-TASK-001`](../agent-workflow/reviews/REVIEW-TASK-001.md) F1
  refuted it by measurement: the denial resolves, but it does not remove `Bash`, and the same
  agent definition hands the role `Bash` and tells it to run things. The denial blocks the
  reflex edit and raises the cost of a deliberate one. It is a mitigation.
- `[확인 사실]` The planner's prohibition is not expressible as a tool denial either, for a
  different reason: the planner needs `Write` to produce the packet.
- `[추론]` So the whole model rests on convention, and one repository guard. Both facts belong
  in the same sentence whenever this model is described — which is why
  `docs/agent-workflow/README.md` keeps the enforced and convention columns apart and why its
  enforced column now holds one item instead of two.

## Decision

`[결정]` Adopt the following operating rules for P0 and later phases until superseded:

1. Repository documents are the durable project memory. A consequential fact, decision,
   risk, blocker, result, or handoff is not durable until it is recorded in its
   authoritative document.
2. Consequential directions are presented to the project owner with material options,
   recommendation, evidence, and tradeoffs. Implementation that depends on the answer waits
   for explicit confirmation. **Collecting evidence that was already authorized continues;
   choosing the direction does not.**
3. Agent work is separated into orchestrator, planner, worker, and attacker roles defined
   under `docs/agent-workflow/`.
4. A planner issues one bounded task packet. A worker implements only that packet. An
   attacker independently tries to falsify the result. The orchestrator accepts the result
   or requests a new packet.
5. Raw conversations, session snapshots, credentials, private evaluation material, and
   private datasets are not project memory and are not committed. A fact about this project
   is not kept only in an agent's private memory store.
6. **The full flow is required by threshold, not by default.** `docs/agent-workflow/README.md`
   names the work that requires a packet and an independent report, and the work that does not.
   **When both lists fire, "required" wins**, and an exemption from the packet is never an
   exemption from the independent attack report. Deciding which list a piece of work falls under
   is the orchestrator's call and recording the call is part of it; resolving an *overlap* is
   not — that is settled here. `[확인 사실]` This clause originally left the overlap to
   discretion, `297fbee` bounded it in the convention document without amending the packet, and
   [`REVIEW-TASK-001-R2`](../agent-workflow/reviews/REVIEW-TASK-001-R2.md) F3 found the
   contradiction.
7. **What the harness enforces and what is convention are recorded separately**, in the
   same document, and neither is described in the other's language.

## Consequential direction boundary

The following always require an owner question when they are new, changed, or ambiguous:

- product goal, decision consumer, phase, schedule, or material scope;
- source selection, collection method, terms or rights basis, retention, or personal-data
  policy;
- model strategy, canonical entity or schema meaning, quality threshold, or human-review
  boundary;
- architecture, persistence, external service, security, credential, or deployment
  boundary;
- evaluation protocol, hidden-test access, material budget, release, or gate criteria.

Names, formatting, private helper structure, and equivalent internal algorithms may remain
local implementation choices when they do not change observable behavior or an accepted
constraint. [`project-state.md`](../project-state.md) §7 is the enumerated list.

## Rejected alternatives

- A single free-form memory file was rejected as the only record because it would duplicate
  current state, decisions, evidence, and history without clear authority.
- Letting each agent infer consequential choices was rejected because the resulting behavior
  would be difficult to audit and could silently change project direction.
- Combining planning, implementation, and acceptance in one role was rejected as the default
  because it weakens independent scope and failure review.
- **A `planner` entry under `.claude/agents/` was rejected.** Its central prohibition cannot
  be expressed as a tool denial, and whether path-scoped `permissions` work in agent
  frontmatter is unverified here. `fcf4b8a` recorded what assuming otherwise costs: `effort`,
  `reasoningEffort`, and `reasoning_effort` are all silently ignored, so a setting that read
  as applied was not. An untested frontmatter key is worse than an absent one.
- **Making the full flow mandatory for every change was rejected.** A rule that costs three
  documents for a typo gets skipped, and a rule applied when convenient has stopped being a
  rule.
- **Moving attack reports into `docs/agent-workflow/reviews/` unconditionally was rejected.**
  A report on experiment work stays beside that experiment, for the reason `c0a266d` gives.

## Tradeoffs and risks

- Benefit: decisions and handoffs survive session changes and team turnover.
- Benefit: user-owned direction remains distinguishable from implementation discretion.
- Benefit: the back half of the flow is already practiced here, so most of the cost is
  paperwork over work that was happening anyway.
- Cost: consequential work pauses while a question is unanswered.
- Cost: each completed packet in scope requires documentation and independent review.
- Risk: too many questions can stall routine implementation.
- Risk: **role laundering.** One session can write the packet, the code, and the attack
  report while naming itself three roles, and no check in this repository would notice. A
  forged review is worse than no review, because the record will be believed later.
- Risk: **template floor becoming a ceiling.** The 2026-08-18 review needed 351 lines. A
  finding compressed into a table cell cannot be checked by its reader.
- Risk: the 2026-08-26 build and 2026-08-27 verification boundary
  [DP-011](DP-011-p0b-product-and-delivery-scope.md) fixes makes both over- and
  under-application more expensive than usual.
- Control: the consequential boundary is explicit; reversible local choices do not require
  owner approval, and the flow threshold is written down.

## What changed from the proposal

`b702c79` is preserved as a merge parent. Every deviation from it is listed here so the
owner can reverse any of them:

1. `DP-006` → `DP-013`. The proposed number was taken by a packet accepted a day earlier at
   the P0-A gate and referenced by number in DP-008, `docs/areas/README.md`, and
   `project-state.md` §4.
2. Project State kept at Cosmai / P0-B and moved to 0.7. The proposal wrote CosmaSignal,
   version 0.4, phase P0-A, with the P0-A gate still ahead of it.
3. `PROMPTS.md` says Cosmai. [DP-007](DP-007-project-rename-to-cosmai.md) renamed the project
   the day before the proposal was written, so its four prompts were the only live text left
   using the old name — in a file meant to be copied.
4. Each role is bound to the `.claude/agents/` definition that enforces it, and the roles with
   no such definition say so.
5. An enforced-versus-convention split was added, following `docs/branching.md`.
6. A threshold for when the full flow applies was added, and the collector integration handoff
   guide is named as that path's existing packet rather than duplicated.
7. Attack reports on experiment work stay beside the experiment.
8. `tests/environment/test_agent_packet_record.py` was added so that one claim in this model
   is checked rather than trusted.
9. `Status`/`Owner confirmation` in this packet were set from the owner's adoption
   instruction; the adapted content itself has not been reviewed line by line.

`[확인 사실]` Items 10-14 were **missing** from this list when it first claimed to be complete.
[`REVIEW-TASK-001`](../agent-workflow/reviews/REVIEW-TASK-001.md) F4 found them by diffing
`b702c79` against the result rather than reading the intent, which is how the list should have
been produced in the first place.

10. `project-memory.md` gained a section, "What does not belong in an agent's private memory".
    It is a `[결정]` that reaches outside this repository: a private memory store must not be
    the only place holding a project constraint. **This is consequential and the owner has not
    been shown it as a decision.**
11. `project-memory.md` gained a required recording rule: "Where a control is claimed, record
    what it does not cover." F1 is the first thing it catches.
12. `project-memory.md`'s routing table gained two rows, `docs/conventions/` and
    `.claude/agents/` — the latter designating a directory `TASK-001` also lists as forbidden
    material.
13. `AGENTS.md` promoted the attacker's `BLOCKED` rule to a project-wide one. In `b702c79` it
    bound only the attacker; it now binds every agent that reads `AGENTS.md`.
14. `branching.md` gained an exception to the one-area rule for documents that change the
    project's operating method — **whose worked example is this branch.** A rule that
    legitimizes the change introducing it belongs on a disclosure list, not inferred from a
    diff. `docs/areas/README.md` was not updated to match. It is now
    [OQ-011](../open-questions/OQ-011-agent-memory-and-area-boundary.md) R2 and is marked
    `[가설]` proposed where it lives; this item said `[확인 사실]` until
    [`REVIEW-TASK-001-R2`](../agent-workflow/reviews/REVIEW-TASK-001-R2.md) F9 caught it
    describing the state one commit earlier.
15. **The threshold's exemption gained two bounding rules** (`README.md` §"When this flow is
    required"): the exemption is from the packet and never from the attacker, and "required"
    wins when both lists fire. Both were added by `297fbee` to repair
    [`REVIEW-TASK-001`](../agent-workflow/reviews/REVIEW-TASK-001.md) F5, and the second amends
    D6 above rather than merely refining it — which is why it is listed rather than folded into
    item 6.

## Remaining uncertainty

- `[확인 사실]` The proposal was reverted from `main` **by agreement among the people
  involved**, not unilaterally. This packet records adoption on a working branch. Whether
  `main` takes it is a separate acceptance, and `docs/branching.md` says `main` moves only at
  gates and accepted Decision Packets.
- The owner instructed adoption of the proposal and of the adaptations judged useful. The
  adapted text above has not been reviewed clause by clause, so item 9 of the previous
  section is the honest state of `Owner confirmation`.
- `[확인 사실]` `DP-009` is unused on every ref in this repository and no commit message
  explains why. It was left unused rather than filled by this packet.
- `[결정]` `DP-001` through `DP-012` predate the `Owner confirmation` field and are **not
  backfilled.** Writing a confirmation onto a decision accepted before the field existed
  would invent the record the field exists to hold. The field applies to packets written
  after this one, which also means no test can require it of every packet.
- The project may later automate packet and report validation beyond the one guard added
  here. No further automation is required by this decision.
- Whether path-scoped `permissions` in `.claude/agents/` frontmatter take effect is untested.
  If they do, the planner's prohibition becomes expressible and rejected alternative 4 should
  be revisited.
- Team staffing and the number of parallel workers remain scheduling choices within the
  accepted project scope.

## Required changes

- Project State: record the memory and agent workflow decision. **Done**, §4.
- Agent instructions: add owner-question, memory, and role-boundary rules. **Done**, `AGENTS.md`.
- Templates: add task packet and attack report templates. **Done**.
- Repository guide: link the new convention and operating model. **Done**, `README.md`.
- Branching: retire the isolated-branch note now that the branch is merged, and record the
  area exception the rule does not cover. **Done**, marked proposed pending OQ-011 R2.
- Project memory convention: routing table, the control-disclosure rule, and the private-memory
  rule. **Done**, the last marked proposed pending OQ-011 R1.
- Execution plan: correct the branch-disposition rows this reapplication made stale. **Done**.
- Open Question: record the two rules written without an owner question.
  **Done**, [OQ-011](../open-questions/OQ-011-agent-memory-and-area-boundary.md).
- Implementation handoff: use the workflow for new agent-assigned work above the threshold
  after this decision.
