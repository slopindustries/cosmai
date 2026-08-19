# Agent Operating Model

This directory defines how agent sessions are separated, assigned, and reviewed. It is an
operating protocol, not a product architecture.

- 문서 지위: 활성 프로젝트 convention
- Governing decision: [DP-013](../decisions/DP-013-agent-workflow-and-project-memory.md)
- 최종 수정일: 2026-08-19

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

If no consequential ambiguity exists, the orchestrator may start at planning. `FAIL`
produces a new or revised packet; the attacker does not repair the reviewed work.

**Collecting evidence that was already authorized is not blocked by an open owner
question — choosing the direction is.** An experiment may keep running while the answer
that decides what to do with its result is outstanding. [Open
Questions](../open-questions/README.md) states the same rule from the other side.

## Roles

| Role | Owns | Must not do | Enforced by |
|---|---|---|---|
| [Orchestrator](ORCHESTRATOR.md) | owner questions, role assignment, boundary enforcement, final acceptance | silently choose consequential direction or implement a packet it is accepting | nothing — it is the session that spawns the others |
| [Planner](PLANNER.md) | one bounded task packet and one-line role prompts | implement product code or accept its own plan | nothing expressible in frontmatter; see `PLANNER.md` |
| [Worker](WORKER.md) | one packet's allowed changes and verification | expand scope, edit forbidden files, or choose blocked direction | `.claude/agents/mechanical.md`, `.claude/agents/addon-author.md` — reading order and model, not scope |
| [Attacker](ATTACKER.md) | independent falsification and reproducible review result | fix the reviewed implementation or inspect private evaluation material | `.claude/agents/adversarial-reviewer.md` denies three edit tools — a mitigation, **not** a barrier; `Bash` remains. See below |

Spawn the subagent type rather than pasting a prompt where one exists. A constraint in
frontmatter is loaded before the role can forget it; [`PROMPTS.md`](PROMPTS.md) has the
one-liners for the cases with no agent definition.

## What is enforced and what is convention

**Reading these mixed together is how a protocol comes to be believed rather than
checked**, so they are written separately — the same split, for the same reason, that
[branching](../branching.md) uses.

### Enforced by the test suite

One item. An earlier revision of this section listed two and was wrong about the second;
[`REVIEW-TASK-001`](reviews/REVIEW-TASK-001.md) F1 is the correction and the demonstration.

- `[확인 사실]` `tests/environment/test_agent_packet_record.py` fails the suite when a packet
  claims `ACCEPTED` without a `PASS` result and a markdown link to a file that exists inside
  this repository, or when it carries a duplicate `Status`, `Attack report`, or `Result` line.
  [`TASK-PACKET-TEMPLATE.md`](TASK-PACKET-TEMPLATE.md) states the rule precisely. That is the
  checkable half of the orchestrator's prohibition on accepting work because the worker
  reported success — and no more than that half: the guard never opens the report it resolves.

### Convention only

- **That the attacker does not repair what it reviews.** `adversarial-reviewer`'s frontmatter
  denies `Write`, `Edit`, and `NotebookEdit`, and `[확인 사실]` the denial resolves — the
  harness's subagent registry lists the type as having every tool *except* those three, which
  is more than `fcf4b8a` could say about the reasoning-effort keys. But **every tool includes
  `Bash`**, and `.claude/agents/adversarial-reviewer.md` hands it `Bash` and tells it to run
  things. `[측정]` On 2026-08-19 the reviewer of this change created a file under
  `docs/agent-workflow/` and modified `tests/environment/test_agent_packet_record.py` through
  `Bash`, then restored it. The denial removes the *likely* path to an accidental repair and
  raises its cost. It is a mitigation, not a write barrier. `[추론]` The 2026-08-18 reviewer
  had the stronger property this section used to claim — it worked from a **copy** — and that
  property belongs to the copy, not to `disallowedTools`.
- **That a packet exists at all.** Nothing detects work done without one.
- **That the attacker was independent of the worker.** One session can write the packet,
  write the code, and write the attack report while naming itself three roles, and no
  check in this repository would notice. `[추론]` This is the most expensive failure the
  model makes available, because a forged review is worse than no review: it leaves a
  record that reads as evidence.
- **That `Owner confirmation` in a Decision Packet names an answer the owner gave.**
- **That the planner did not implement.** Not expressible as a tool denial.
- Every field in a packet other than the ones the guard checks, and every field in a report.
  The guard never opens a report; it only tests that a path resolves.

`[결정]` This is recorded rather than smoothed over. A control that looks stronger than it
is, is worse than a recorded absence.

## When this flow is required

`[결정]` The full flow — a packet, a worker handoff, and an independent attack report —
is required for work that:

- produces or changes gate evidence, a Decision Packet, a contract under `contracts/`, or
  an item accepted in [`project-state.md`](../project-state.md) §4;
- implements a platform capability, guard, or limit **whose failure is silent** — anything
  whose test could pass while proving nothing;
- follows an owner answer, once that answer is recorded.

It is **not** required for:

- the local implementation choices [`project-state.md`](../project-state.md) §7 lists;
- a documentation correction that changes no accepted claim;
- work already governed by a convention document that carries its own scope, required
  evidence, and review checklist. The collector integration path is governed by
  [collector integration handoff](../conventions/collector-integration-handoff.md) — scope in
  §1 and §"Ownership boundary", evidence in §6, unresolved choices in §7, the checklist in §8 —
  and that document **is** that path's packet. A second packet over the same work duplicates
  authority, which the [project memory convention](../conventions/project-memory.md) forbids.

`[결정]` **Two rules bound that exemption, because as first written it was unsound**
([`REVIEW-TASK-001`](reviews/REVIEW-TASK-001.md) F5):

- **The exemption is from the packet, never from the attacker.** Nothing in the handoff guide
  requires independent falsification, so exempting a path from the packet must not exempt it
  from the attack report. `[추론]` The collector path is the *last* place to drop that: the
  three blocking findings this whole model is argued from came from an independent review of
  `27f712b`, which is collector work. An exemption that removed the attacker there would remove
  the control from the case that produced it.
- **"Required" wins when both lists fire.** Collector work that also changes a contract, or
  that adds the page-limit enforcement the 2026-08-18 review found missing, is required work.
  `[결정]` The overlap resolves upward, not by discretion — a threshold whose ambiguous cases
  are settled case by case is the "rule applied when convenient" this section warns about.

`[추론]` The threshold is load-bearing, not a convenience. Applied to everything, the flow
costs three documents for a typo and gets skipped — and a rule applied when convenient has
stopped being a rule. Applied to nothing, an unenforced limit ships and reads as enforced,
which is the defect the 2026-08-18 adversarial review found three of. The 2026-08-26 build
and 2026-08-27 verification boundary that [DP-011](../decisions/DP-011-p0b-product-and-delivery-scope.md)
fixes makes both errors more expensive, not less.

## Required artifacts

- [Task Packet Template](TASK-PACKET-TEMPLATE.md)
- [Attack Report Template](ATTACK-REPORT-TEMPLATE.md)
- [One-Line Prompts](PROMPTS.md)
- [Project Memory Convention](../conventions/project-memory.md)

Create active packets under `docs/agent-workflow/task-packets/`. **An attack report on
experiment work belongs beside that experiment**, not here — see
[`reviews/README.md`](reviews/README.md) for which reports go where and why. Do not create
an assignment until its dependencies and consequential decisions are recorded.

## Result states

- `PASS`: all packet acceptance criteria were tested and no blocking contradiction was found.
- `FAIL`: a reproducible defect, scope violation, or unmet criterion was found.
- `BLOCKED`: the result cannot be determined because a named dependency, permission,
  environment, or owner decision is missing.

Only the orchestrator closes a packet after reading the worker evidence and attacker report.

`[결정]` `BLOCKED` is a delivered result, not a failure to deliver. An agent that cannot
verify what it was asked to verify returns `BLOCKED`; it does not return a qualified pass.

## This flow ran once before these documents existed

`[추론]` `27f712b` and `c0a266d` are a worker result and an independent attack on it,
run on 2026-08-18 at 20:24 and 21:38 — hours *after* `b702c79` wrote these documents at
14:48 the same day, on a branch that had never seen them. The reviewer returned three blocking,
three major, three moderate, and one minor finding, and the report was committed beside the work as
[`ADVERSARIAL-REVIEW-2026-08-18.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md)
rather than summarized into it, and the follow-up commit repaired nothing — it corrected
only the claims that were false. The commits, the counts, and the timestamps are `[확인 사실]`;
the reviewer's independence is `[추론]`, resting on that report's own self-description
("an independent agent with no write access to the repository, **working from a copy**"). An
earlier revision of this paragraph asserted "a reviewer with no write access" as
`[확인 사실]` while §"What is enforced" said the opposite two screens above —
[`REVIEW-TASK-001-R2`](reviews/REVIEW-TASK-001-R2.md) F6. The copy is the half that carries
the property.

`[추론]` Two things follow. The back half of this model is existing practice getting a
name, so adopting it costs little. And the front half — a packet whose acceptance criteria
are written by someone who will not implement them — is the part that is genuinely new,
which is why that review's first blocking finding is the argument for it: an add-on fetching
12 times and emitting 600 items against `max_pages=2, max_records=3` succeeded, because those
limits are enforced nowhere. The session that wrote the acceptance criterion also wrote the code
that satisfied it.

`[추론]` The diagnosis of *how* that happened is the **author's**, not the reviewer's, and it is
an inference rather than a finding: *"the add-on cooperated" was read as "the platform
enforced". That is the exact reading the experiment was designed to avoid, made by the person
who designed it.* — [`EXP-003`](../../experiments/integrated-p0/EXP-003-capability-layer.md),
added by `c0a266d`. An earlier revision of this paragraph attributed that sentence to the
reviewer and altered one word of it;
[`REVIEW-TASK-001`](reviews/REVIEW-TASK-001.md) F6 found it and
[`REVIEW-TASK-001-R2`](reviews/REVIEW-TASK-001-R2.md) F2 found that only `DP-013` had been
corrected. The accurate version is the stronger one: an independent reviewer measured the gap,
and the author, reading the measurement, named the mechanism.
