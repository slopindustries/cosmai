# TASK-001 — Adopt the isolated agent operating model on the current branch

- Status: `REWORK`
- Phase: P0-B
- Planner: none — see "How this packet came to exist" below
- Worker: main session, 2026-08-19
- Attacker: `adversarial-reviewer`
- Orchestrator: main session. `ORCHESTRATOR.md` says the role is the session that spawns the others; an earlier revision of this line named the project owner, which collapses the one action the role is defined by — REVIEW-TASK-001 F8
- Created: 2026-08-19
- Updated: 2026-08-19, after three independent reviews, all `FAIL`. Reviewing stopped here by owner decision; this packet is not accepted.

## How this packet came to exist

`[확인 사실]` **This packet was written after the work, not before it.** The owner assigned
the merge directly; no planner produced acceptance criteria in advance, and the worker and
the person recording this are the same session.

`[결정]` It is written anyway, and written as what it is. `docs/agent-workflow/README.md`
says work that changes an item accepted in `project-state.md` §4 requires the full flow, and
this work changes one. Recording the packet honestly is worth more than either pretending
the front half ran or leaving the first application of the model undocumented — which is the
gap `DP-013` lists as the proposal's own self-exemption. The planning separation did not
happen, and is recorded as not having happened.

`[확인 사실]` An earlier revision of this paragraph said "the independent attack below is real"
while the `Attack report:` field was still empty — an intention written in the present tense,
which is the first item on the list of things this project punishes. The attack has since run
and returned `FAIL`; [`REVIEW-TASK-001`](../reviews/REVIEW-TASK-001.md) F15 is the finding
against that sentence.

## Objective

Bring `b702c79` — the agent operating model held in isolation by `docs/branching.md` — onto
`6d1e965` as `agent/operating-model`, resolving the conflicts and the number collision, and
adapt it so that every claim it makes about this project is true of this project.

## Authority and dependencies

- Project State: [0.7, P0-B](../../project-state.md)
- Accepted decisions: [DP-013](../../decisions/DP-013-agent-workflow-and-project-memory.md),
  and [DP-011](../../decisions/DP-011-p0b-product-and-delivery-scope.md) for the delivery
  boundary the threshold is calibrated against
- Contracts: none
- Open Questions: [OQ-011](../../open-questions/OQ-011-agent-memory-and-area-boundary.md) — two rules this work wrote without asking, both marked proposed in place
- Owner decisions required: **two**, and they are `OQ-011` R1 and R2. An earlier revision said
  `none`; [`REVIEW-TASK-001-R2`](../reviews/REVIEW-TASK-001-R2.md) §"Scope and decision-boundary
  review" found that inconsistent with the packet's own dependencies. The merge and the
  adaptation were instructed on 2026-08-19; the two rules were not.
- Required evidence or environment: the checkout's virtualenv; `.venv/bin/python -m pytest`

## Scope

### Included

- `--no-ff` merge of `b702c79`, preserving it as a merge parent
- conflict resolution in `docs/project-state.md` and `docs/decisions/README.md`
- renumbering the incoming Decision Packet off the number `DP-006` already holds
- adapting the merged documents to the current project name, phase, roles, and enforcement
- one repository guard making the checkable part of the model executable

### Excluded

- any change to `main`, or a pull request toward it
- any change to `.claude/agents/` definitions
- automation beyond the single guard
- any product, platform, domain, or add-on code

### Allowed files

- `AGENTS.md`, `README.md`
- `docs/agent-workflow/**`
- `docs/conventions/project-memory.md`
- `docs/decisions/DP-013-agent-workflow-and-project-memory.md`, `docs/decisions/README.md`
- `docs/decisions/DP-TEMPLATE.md`, `docs/open-questions/OQ-TEMPLATE.md`, `docs/open-questions/README.md`
- `docs/project-state.md`, `docs/branching.md`
- `tests/environment/test_agent_packet_record.py`
- added 2026-08-19 during rework, on REVIEW-TASK-001 F7 and F4: `docs/p0-execution-plan.md`,
  `docs/open-questions/OQ-011-agent-memory-and-area-boundary.md`; and
  `docs/decisions/DP-014-agent-memory-scope-and-area-exception.md`, which `65191d8` created
  **without** extending this list — [`REVIEW-TASK-001-R3`](../reviews/REVIEW-TASK-001-R3.md) F6.
  The allowed-file list is the only scope control a reviewer can check mechanically, and it
  stops being checkable the first time a file is added silently. `[확인 사실]` The first was
  missing because this list was fitted to the diff rather than written before it — the concrete
  cost of the planner separation this packet records as not having happened.

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- everything under `experiments/`, `contracts/`, and `.claude/`

## Acceptance criteria

1. `b702c79` is a parent of the merge commit, so the original proposal remains readable.
2. No two Decision Packets claim the same number, and `DP-006` still resolves to the P0-A
   platform foundation packet everywhere it is referenced by number.
3. No document changed by this work uses `CosmaSignal` as the project's live name, claims
   phase P0-A, or claims the P0-A Completion Gate is still ahead. The name survives on
   purpose in superseded `DP-002`, in `docs/history/`, and in `DP-013`'s account of what the
   proposal said — `DP-007` left history untouched deliberately.
4. Every relative link in every changed document resolves. Every backticked repository path
   that a changed document **asserts exists** resolves — a path named inside a prohibition
   (`apps/`) or introduced by "such as" is excluded, and any exclusion must be nameable.
5. Each role states which part of its prohibition the harness enforces and which part is
   convention, and no convention is described as a control. A denial of some tools is not a
   denial of the capability those tools provide, and must not be written as one.
6. The threshold does all four of: names which work requires the full flow; names a precedence
   rule for work that fires both lists; states whether an exemption from the packet also exempts
   the independent attack report; and cites its exemption document by the sections that actually
   carry scope, evidence, and a checklist.
7. `tests/environment/test_agent_packet_record.py` rejects, with a named case each, an
   `ACCEPTED` packet whose attack report is: absent, prose without a link, a URL, a relative
   path that does not exist, an absolute path outside the repository, a `..` escape out of the
   repository, and a directory. It rejects a duplicate `Status`, `Attack report`, or `Result`
   line at any position, which is what closes the three override bypasses. It reports a
   non-UTF-8 file by name and keeps scanning rather than aborting. Every one of those rejection
   cases goes red when `packet_problems` is weakened to `return []`.
8. `.venv/bin/python -m pytest tests/environment/ -q` passes, and `ruff` and `mypy` are clean on
   the guard.
9. Every finding in [`REVIEW-TASK-001`](../reviews/REVIEW-TASK-001.md) is either repaired or
   recorded with the reason it was not, and no finding is closed by rewording the claim it
   contradicts unless the reworded claim is true.

`[확인 사실]` Criteria 4, 6, and 7 were rewritten on 2026-08-19. As first written, criterion 6
was satisfied by the existence of any threshold, criterion 4 failed on a prohibition and two
illustrative filenames, and criterion 7 called the guard's rejection cases "positive controls".
[`REVIEW-TASK-001`](../reviews/REVIEW-TASK-001.md) F10 and F11 are the findings.
`[추론]` They are the F1 defect of `ADVERSARIAL-REVIEW-2026-08-18.md` one level up — a criterion
satisfied by the shape of the thing rather than by the property — and they are what happens when
the session that writes the criteria is the session that satisfies them, which is the condition
this packet already admits.

## Verification

```sh
# Replayable commands only; never include secret values.
git log --oneline --graph -3 agent/operating-model     # b702c79 present as a merge parent
# Expect hits only in superseded DP-002, docs/history/, and DP-013's account of the proposal.
# This packet and its review are excluded: criterion 3 names the string it tests for.
git grep -n 'CosmaSignal' -- docs AGENTS.md README.md ':!docs/agent-workflow'
ls docs/decisions/                                     # one DP-006, one DP-013
.venv/bin/python -m pytest tests/environment/ -q
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.

## Worker handoff

- Changed files: see the two commits on `agent/operating-model` above `6d1e965`.
- Commands and results: recorded in the commit messages and in the attack report below.
- Evidence locations: the merge commit message for the conflicts and the number collision;
  `DP-013` §"What changed from the proposal" for every deviation from `b702c79`.
- Limitations and remaining risks: the planner separation did not happen for this packet, as
  stated above. Role laundering remains unenforceable; `DP-013` records it as a risk rather
  than solving it. Whether path-scoped `permissions` work in agent frontmatter is untested,
  so no planner binding is claimed.
- Newly discovered questions or blockers: `DP-009` is unused on every ref with no recorded
  reason, and was left unused. Whether `main` takes this work is a separate acceptance.

## Review

- Attack report: [REVIEW-TASK-001-R3](../reviews/REVIEW-TASK-001-R3.md)
- Result: `FAIL`
- Orchestrator disposition: **not accepted, and reviewing stopped by owner decision on
  2026-08-19.**

  Three independent reviews, each attacking the repair of the one before it:
  [`REVIEW-TASK-001`](../reviews/REVIEW-TASK-001.md) — 2 blocking, 4 major, 5 moderate, 4 minor;
  [`REVIEW-TASK-001-R2`](../reviews/REVIEW-TASK-001-R2.md) — 1 blocking, 1 major, 2 moderate,
  6 minor; [`REVIEW-TASK-001-R3`](../reviews/REVIEW-TASK-001-R3.md) — 3 blocking, 2 major,
  2 moderate, 3 minor.

  `[확인 사실]` The `Attack report:` field above names only the latest, because the guard now
  requires **exactly one** markdown link there. An earlier revision carried all three on that
  line, with a note explaining that one line avoided the duplicate-*line* rule — which it did,
  while breaking the multi-*link* rule the same round added. It was dormant only because this
  packet is not `ACCEPTED`. The earlier reports are linked here instead, where prose belongs. Severity fell across rounds — R1's blocking findings were "the
  guard accepts `/etc/hosts` as an independent review"; R3's are a markdown-quotation bypass and
  two stale records.

  `[확인 사실]` **Criterion 9 failed all three rounds**, and R3 measured why in one sentence:
  *every round repaired what the previous report demonstrated and left what it characterised.*
  R2-F1 demonstrated an indent and a `*` bullet and characterised the class as "a form the
  pattern cannot see"; six more forms were open at R3. R2-F4 demonstrated one function and
  characterised the class; its sibling was untouched. R2-F6 named three sites and two were fixed.
  `[추론]` That is a property of the session closing the findings, not of the findings — which is
  the argument for the planner/worker separation this packet records as never having happened.

  **Repaired after R3:** the guard's field detection rewritten at the class level rather than per
  demonstrated form (R3-F1); `scan_task_packets`'s exception handling widened to match its
  sibling (R3-F7); message truncation applied on all branches (R3-F9); the first-link-wins
  behaviour R2-F10 left open twice; the three documents that stated the duplicate rule as a
  file-wide invariant it did not have; this disposition paragraph, which said "no second
  independent review has run" one line below the field linking it (R3-F2); `DP-014`'s two
  checklist entries marked **Done.** without being done (R3-F3); `DP-013`'s items 10 and 14 and
  its `[확인 사실]` label at line 34 (R3-F3, R3-F4); this allowed-file list (R3-F6).

  **Accepted and not repaired**, recorded here because criterion 9 asks for it and because two
  rounds left them nowhere:

  - **R2-F8** — any existing file inside the repository passes as the attack report, including
    `.git/config`. The guard proves a path resolves; it never opens the file, and both the
    docstring and `README.md` say so. Narrowing the bar to `reviews/` or a `*REVIEW*` name is a
    decision, not a repair, and no one has asked for it.
  - **R2-F9 sub-items 3 and 4** — three `AGENTS.md` bullets and one `WORKER.md` section absent
    from `DP-013`'s deviation list. Each echoes a disclosed item; listing them would be
    near-redundant. Recorded rather than added.
  - **R3-F5's three rules** — removed rather than repaired. The owner's instruction on
    2026-08-19 was to take all three out of force because their provenance could not be checked.
    [`DP-014`](../../decisions/DP-014-agent-memory-scope-and-area-exception.md) R1 records what
    that leaves: two operating constraints now bind nowhere, and a fact worth binding needs its
    own decision.

  `[결정]` This packet stays `REWORK`. No fourth review attacked the repairs above, so
  `ACCEPTED` would rest on the session that made them — which is the one thing the acceptance
  criteria exist to prevent. The branch is not merged to `dev`; that is a separate decision the
  owner has deferred.
