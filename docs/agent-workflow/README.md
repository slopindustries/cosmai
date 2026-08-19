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
| [Attacker](ATTACKER.md) | independent falsification and reproducible review result | fix the reviewed implementation or inspect private evaluation material | `.claude/agents/adversarial-reviewer.md` — `disallowedTools` makes "never repairs" structural |

Spawn the subagent type rather than pasting a prompt where one exists. A constraint in
frontmatter is loaded before the role can forget it; [`PROMPTS.md`](PROMPTS.md) has the
one-liners for the cases with no agent definition.

## What is enforced and what is convention

**Reading these mixed together is how a protocol comes to be believed rather than
checked**, so they are written separately — the same split, for the same reason, that
[branching](../branching.md) uses.

### Enforced by the harness or the test suite

- `[확인 사실]` `adversarial-reviewer` cannot write, edit, or modify a notebook. Its
  frontmatter denies those tools, so *the attacker does not repair what it reviews* holds
  even for an attacker that never opened [`ATTACKER.md`](ATTACKER.md). Verified 2026-08-19
  by the harness's own subagent registry, which lists this type as having every tool
  *except* those three — a resolved denial rather than a key that was accepted and ignored,
  which is what `fcf4b8a` found the reasoning-effort keys to be.
- `[확인 사실]` `tests/environment/test_agent_packet_record.py` fails the suite when a
  packet claims `ACCEPTED` without a linked attack report and a `PASS` result. That is the
  checkable half of the orchestrator's prohibition on accepting work because the worker
  reported success.

### Convention only

- **That a packet exists at all.** Nothing detects work done without one.
- **That the attacker was independent of the worker.** One session can write the packet,
  write the code, and write the attack report while naming itself three roles, and no
  check in this repository would notice. `[추론]` This is the most expensive failure the
  model makes available, because a forged review is worse than no review: it leaves a
  record that reads as evidence.
- **That `Owner confirmation` in a Decision Packet names an answer the owner gave.**
- **That the planner did not implement.** Not expressible as a tool denial.
- Every field value in a packet or report other than the four the guard checks.

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
- work already governed by a convention document carrying its own scope, evidence, and
  review checklist. The collector integration path is governed by
  [collector integration handoff](../conventions/collector-integration-handoff.md) §6–§8,
  which **is** that path's packet. A second packet over the same work duplicates
  authority, which the [project memory convention](../conventions/project-memory.md)
  forbids.

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

`[확인 사실]` `27f712b` and `c0a266d` are a worker result and an independent attack on it,
run on 2026-08-18 at 20:24 and 21:38 — hours *after* `b702c79` wrote these documents at
14:48 the same day, on a branch that had never seen them. A reviewer with no write access
returned three blocking, three major, three moderate, and one minor finding, the report was
committed beside the work as
[`ADVERSARIAL-REVIEW-2026-08-18.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md)
rather than summarized into it, and the follow-up commit repaired nothing — it corrected
only the claims that were false.

`[추론]` Two things follow. The back half of this model is existing practice getting a
name, so adopting it costs little. And the front half — a packet whose acceptance criteria
are written by someone who will not implement them — is the part that is genuinely new,
which is why the review's first blocking finding is the argument for it: *"the add-on
cooperated" was read as "the platform enforced" — the exact reading the experiment was
designed to prevent, made by the person who designed it.*
