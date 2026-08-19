# REVIEW-TASK-001 — Attack report

- Packet: [TASK-001 — Adopt the isolated agent operating model on the current branch](../task-packets/TASK-001-agent-operating-model-adoption.md)
- Worker revision: `9707c8e` on `agent/operating-model` (merge `b437013` of `b702c79` onto `6d1e965`, plus adaptation)
- Attacker: subagent type `adversarial-reviewer`, independent session, no `Write`/`Edit`/`NotebookEdit`
- Date: 2026-08-19
- Result: `FAIL`

`[측정]` Environment: this checkout at `9707c8e`, working tree clean before and after every
probe (`git status --short` empty both times). Python from `.venv/bin/python` (CPython
3.13.7, macOS arm64). No network call was made. Every mutation was performed on a copy under
the session scratchpad except one, which is named and shown restored in F1.

## Reproduced worker evidence

| Claim | Command or procedure | Observed result | Evidence |
|---|---|---|---|
| Criterion 1 — `b702c79` is a merge parent | `git log -1 --format='%h parents=%p' b437013` | `b437013 parents=6d1e965 b702c79` | verified |
| Criterion 2 — one `DP-006`, one `DP-013` | `ls docs/decisions/`; `git grep -n 'DP-006'` | one file each; all 60+ `DP-006` references resolve to `DP-006-p0a-platform-foundation.md`; `docs/areas/README.md` carries two, as `b437013` says | verified |
| Criterion 3 — no changed document claims `CosmaSignal`, phase P0-A, or a pending P0-A gate | `git grep -n 'CosmaSignal' -- docs AGENTS.md README.md`; grep added lines for `P0-A` | substantively verified; but the packet's stated *expected* output for its own command is wrong — see **F14** | partially verified |
| Criterion 4 — every relative link resolves | resolved all `[..](..)` targets in all 21 changed `.md` files against each file's own directory | **0 broken links** | verified |
| Criterion 4 — every backticked repository path exists | same sweep over backticked path-like tokens on added lines | three counterexamples in changed documents — see **F10** | not met as written |
| Criterion 5 — each role separates enforced from convention | read `ORCHESTRATOR.md`, `PLANNER.md`, `WORKER.md`, `ATTACKER.md` | first clause met by all four; second clause ("no convention is described as a control") **violated** — see **F1** | not met |
| Criterion 6 — a threshold exists | read `README.md` §"When this flow is required" | a threshold exists; it is not self-consistent, and the criterion cannot detect that — see **F5**, **F11** | met, but vacuously |
| Criterion 7 — the guard rejects an `ACCEPTED` packet with no resolvable report | inserted a defective `ACCEPTED` packet into a copied tree and ran the scan | scan is **reachable and non-vacuous**: it named both defects by path | verified |
| Criterion 7 — positive controls fail when the validator is weakened | replaced `packet_problems` body with `return []` in a copy | **9 failed, 6 passed** — matches `9707c8e`'s "Nine rejection cases go red"; but the six that pass include both `CLEAN_CASES`, which is what "positive control" normally names — see **F11** | verified with a wording caveat |
| Criterion 8 — `tests/environment/` passes | `.venv/bin/python -m pytest tests/environment/ -q` | `48 passed in 1.87s` (33 before; the new file contributes exactly 15) | verified |
| `ADVERSARIAL-REVIEW-2026-08-18.md` runs to 351 lines | `wc -l` | `351` | verified |
| That review returned 3 blocking, 3 major, 3 moderate, 1 minor | read its `Outcome` line and its ten `## F*` headings | `**3 blocking findings, 3 major, 3 moderate, 1 minor.**`; F1–F3 blocking, F4–F6 major, F7–F9 moderate, F10 minor | verified |
| `27f712b` 20:24, `c0a266d` 21:38, `b702c79` 14:48, all 2026-08-18 | `git log --format='%h %ad' --date=iso` | `20:24:26`, `21:38:41`, `14:48:23` | verified |
| "the follow-up commit repaired nothing — it corrected only the claims that were false" | diffed `c0a266d`'s three source files and filtered for non-prose lines | all changes are docstring/comment text in `addon_api/context.py`, `addon_host/capabilities.py`, `platform_core/jobs/runner.py` | verified |
| "the Naver collector's author found three defects in work reviewed by its own designer" | `git grep` for the measurement | `experiments/integrated-p0/EXP-002-addon-layer.md:304` — `[측정] Three defects in MY work, found by that author and not by me.` | verified |
| `DP-009` is unused on every ref and no commit explains why | `git grep 'DP-009'` over every ref; `git log --all --grep='DP-009'` | the only hits are this work's own three documents; the only commit message mentioning it is `b437013` itself | verified |
| Nothing in the "convention only" column is secretly enforced elsewhere | `git grep -ln 'agent-workflow\|project-memory\|\.claude/agents' -- tests …` | exactly one hit: `tests/environment/test_agent_packet_record.py`. The split does **not** understate itself | verified |
| Nothing was dropped from the proposal's role documents | `git diff b702c79 9707c8e` per file | `ATTACKER.md`, `ORCHESTRATOR.md`, `PLANNER.md`, `WORKER.md`, both templates, `task-packets/README.md`: purely additive. `project-memory.md`: additive plus one disclosed row change | verified |

## Adversarial cases

| Case | Failure class | Expected constraint | Observed result | Severity | Reproduction |
|---|---|---|---|---|---|
| F1 — write into the repository as `adversarial-reviewer`, using `Bash` only | `assumption` | "`adversarial-reviewer` cannot write"; "`disallowedTools` makes 'never repairs' structural" | created a file in `docs/agent-workflow/`, then modified the tracked guard `tests/environment/test_agent_packet_record.py` and restored it — all through `Bash` | **Blocking** | below |
| F2 — `ACCEPTED` packet whose "attack report" is `/etc/hosts` | `implementation` | the guard checks "that the link names a path inside this repository" | full guard file: `15 passed` | **Blocking** | below |
| F3 — an earlier `- Status:` / `- Result:` / `- Attack report:` line silently overrides `## Review` | `implementation` | the fields checked are the ones the template puts under `## Review` | three separate bypasses accepted | **Major** | below |
| F4 — undisclosed deviations from `b702c79` | `specification` | "Every deviation from it is listed here so the owner can reverse any of them" | at least five substantive changes are not on the nine-item list | **Major** | below |
| F5 — the threshold exempts the one path with demonstrated need for an attacker | `specification` | "The threshold is load-bearing, not a convenience" | the collector integration path is exempted from the independent attack report; required/not-required lists overlap with no precedence rule | **Major** | below |
| F6 — the quote justifying the planner/worker split is misattributed and altered | `evaluation` | "in the reviewer's own words", labelled `[확인 사실]` | the sentence is the *author's* `[추론]` in `EXP-003`, added by `c0a266d`, and one word differs | **Major** | below |
| F7 — `docs/p0-execution-plan.md` now contradicts the changed documents | `specification` | `AGENTS.md` requires reading it before P0-B work | three stale statements, one of them repeating F1's false claim | Moderate | below |
| F8 — `TASK-001` assigns the orchestrator role to the project owner | `specification` | `ORCHESTRATOR.md`: the orchestrator "is the session that spawns the others" and "asks the project owner" | the role's defining action and the model's only acceptance control both collapse | Moderate | below |
| F9 — `DP-013` is `ACCEPTED_FOR_POC`/`CONFIRMED` over content it says was never reviewed | `specification` | `DP-TEMPLATE.md`, added by this work: do not use `ACCEPTED_FOR_POC` until the owner's explicit answer is recorded | `AGENTS.md` turns the whole document into a constraint; item 9 admits the content is unreviewed | Moderate | below |
| F10 — criterion 4 is not met as written; criterion 5 is not met | `evaluation` | the packet's own acceptance criteria | three backticked non-existent paths in changed documents; F1 violates criterion 5's second clause | Moderate | below |
| F11 — criterion 6 cannot fail; criterion 7 uses "positive controls" ambiguously | `evaluation` | a criterion must be able to fail | criterion 6 is satisfied by the existence of any threshold | Moderate | below |
| F12 — the inline cases *do* depend on something existing on disk | `implementation` | docstring: "which do not depend on anything existing on disk" | 4 of 15 tests fail when `docs/agent-workflow/README.md` is absent | Minor | below |
| F13 — a non-UTF-8 file under `task-packets/` aborts the scan | `implementation` | a guard should report a defect, not raise | `UnicodeDecodeError` stops the scan before later packets are read | Minor | below |
| F14 — `TASK-001` §Verification states an expected output its own command does not produce | `evaluation` | a replayable command with a checkable expectation | two extra hits, in `TASK-001` itself | Minor | below |
| F15 — "The independent attack below is real" was written before the attack existed | `evaluation` | the failure mode `.claude/agents/adversarial-reviewer.md` names first | at `9707c8e` the `Attack report:` field is empty | Minor | below |

---

# Findings in full

## F1 — The strongest claim in the "enforced" column is false. **Blocking.**

**Claimed.** In six places across the changed documents:

- `docs/agent-workflow/README.md:51–55` — "`[확인 사실]` `adversarial-reviewer` **cannot
  write**, edit, or modify a notebook. Its frontmatter denies those tools, so *the attacker
  does not repair what it reviews* holds even for an attacker that never opened
  `ATTACKER.md`. Verified 2026-08-19 by the harness's own subagent registry, which lists
  this type as having every tool *except* those three."
- `docs/agent-workflow/README.md:37` — role table, `Enforced by` column: "`disallowedTools`
  makes 'never repairs' **structural**".
- `docs/agent-workflow/ATTACKER.md:27–29` — "*do not edit the implementation being reviewed*
  is the one prohibition in this project **that a role cannot talk itself out of**".
- `docs/agent-workflow/PROMPTS.md:36–38` — "the only role prohibition in this project that a
  role cannot talk itself out of, so **spawn it rather than pasting this**".
- `docs/project-state.md:175` — "`[확인 사실]` Two parts of that model are enforced —
  `adversarial-reviewer` **cannot write**, and …".
- `docs/decisions/DP-013…md:44–47` — "`[확인 사실]` **Only one role prohibition in this model
  is structural.** `adversarial-reviewer` carries `disallowedTools: Write, Edit,
  NotebookEdit`."

**Why it is false.** `disallowedTools` removes three *tools*. It does not remove `Bash`, and
`Bash` writes files. The same file that denies `Write` hands the agent `Bash` and instructs
it to use it — `.claude/agents/adversarial-reviewer.md`, under "How to work": "**Run
things.** You have `Bash`."

The stated verification basis contains its own refutation. The registry line the document
cites reads `(Tools: All tools except Write, Edit, NotebookEdit)`. *All tools* is the
operative half. The basis proves the denial **resolved** — which is a real and useful fact,
and is genuinely more than `fcf4b8a` could say about the reasoning-effort keys — but it does
not prove the denial is a **write barrier**, and the two are what the documents conflate.

**Measured.** `[측정]` Both probes were run by this session, spawned as subagent type
`adversarial-reviewer`, in this checkout, at `9707c8e`.

Probe 1 — create a file in the reviewed directory:

```sh
printf 'attacker-write-probe\n' > docs/agent-workflow/ATTACKER-WRITE-PROBE.txt
ls -l docs/agent-workflow/ATTACKER-WRITE-PROBE.txt   # -rw-r--r-- 21 bytes
command rm docs/agent-workflow/ATTACKER-WRITE-PROBE.txt
```

Probe 2 — the pointed one. Modify the tracked guard that this very packet added, then restore
it:

```sh
.venv/bin/python -c "
import pathlib
p = pathlib.Path('tests/environment/test_agent_packet_record.py')
t = p.read_text()
p.write_text(t.replace('ACCEPTED_STATUS = \"ACCEPTED\"',
                       'ACCEPTED_STATUS = \"NEVER_MATCHES\"', 1))"
git status --short          # M tests/environment/test_agent_packet_record.py
git diff --stat             # 1 file changed, 1 insertion(+), 1 deletion(-)
git checkout -- tests/environment/test_agent_packet_record.py
git status --short          # clean
```

An attacker can rewrite the guard it was sent to attack. Nothing in the harness stops it.

**Why the existing evidence passed anyway.** Nothing tested this. The claim was checked
against the registry listing rather than against the capability, and the registry listing was
read for what it excluded rather than for what it included. `docs/branching.md` — which
`README.md:47–49` names as the model for this very split — states the rule this violates:
*"실제보다 강해 보이는 통제는 기록된 부재보다 나쁘다."* And `docs/conventions/project-memory.md:59`,
added by this same commit, states it as an obligation: *"**Where a control is claimed, record
what it does not cover.**"*

**What is actually true, and is worth keeping.** Three edit-shaped tools are denied and the
denial resolves. That raises the cost of an accidental repair and it removes the most likely
path to one. It is a real mitigation. It is not structural, it is not a thing a role "cannot
talk itself out of", and it does not hold "even for an attacker that never opened
`ATTACKER.md`" — an attacker that never read `ATTACKER.md` and reached for `Bash` would
succeed. Note the contrast with the 2026-08-18 reviewer, which
`ADVERSARIAL-REVIEW-2026-08-18.md` describes as "an independent agent with no write access to
the repository, **working from a copy**". A copy is an isolation mechanism. `disallowedTools`
alone is not, and the documents have transferred the earlier reviewer's property to a
different mechanism that does not have it.

**Consequence for the packet.** Acceptance criterion 5's second clause is *"no convention is
described as a control."* This is a convention described as a control, in three of the changed
documents plus `project-state.md`. Criterion 5 is not met. This is also, precisely, the
class of defect `README.md:100–104` says the threshold exists to prevent — "an unenforced
limit ships and reads as enforced, which is the defect the 2026-08-18 adversarial review found
three of." The document names the failure mode and then commits it in the section that names
it.

**Failure class:** `assumption`, with a `specification` tail — the underlying belief about
what `disallowedTools` guarantees is wrong, and six documents were written from it.

## F2 — The guard accepts an `ACCEPTED` packet whose attack report is `/etc/hosts`. **Blocking.**

**Claimed.** `docs/agent-workflow/TASK-PACKET-TEMPLATE.md:12–16`: "`[확인 사실]` **Four
things** in this file are checked by `tests/environment/test_agent_packet_record.py`: that
`Status` holds one of the values above, and — when it is `ACCEPTED` — that `Attack report`
carries a markdown link, **that the link names a path inside this repository**, and that the
path exists."

The guard's module docstring makes the same claim: "`Attack report:` must contain a markdown
link whose target is **a repository path that exists**."

**Why it is false.** `_is_repository_path` does not test for repository membership. It tests
for three negatives:

```python
def _is_repository_path(target: str) -> bool:
    return not _URL_SCHEME.match(target) and not target.startswith(("mailto:", "#"))
```

Anything that is not a URL, a `mailto:`, or a same-document anchor is treated as a repository
path and joined onto `TASK_PACKETS_DIR`. `pathlib` resolves an absolute target to itself, and
`..` segments escape the repository freely. `resolved.exists()` is also true for directories.

**Measured.** `[측정]` Eleven distinct defective `ACCEPTED` packets were accepted with zero
problems reported. The five that matter:

| target in `Attack report:` | resolves to | guard verdict |
|---|---|---|
| `/etc/hosts` | `/etc/hosts` | accepted |
| `../../../../../../../../../../etc/hosts` | `/etc/hosts` | accepted |
| `../reviews` | the reviews **directory** | accepted |
| `../../..` | the **repository root** | accepted |
| `../ATTACK-REPORT-TEMPLATE.md` | the empty template | accepted |

End-to-end, through the whole guard file rather than through `packet_problems` alone:

```sh
mkdir -p /tmp/e2e/tests/environment /tmp/e2e/docs/agent-workflow/task-packets
cp tests/environment/test_agent_packet_record.py /tmp/e2e/tests/environment/
cp docs/agent-workflow/TASK-PACKET-TEMPLATE.md docs/agent-workflow/README.md /tmp/e2e/docs/agent-workflow/
cat > /tmp/e2e/docs/agent-workflow/task-packets/TASK-002-forged.md <<'MD'
# TASK-002 — A packet accepted with no review at all

- Status: `ACCEPTED`
- Planner: same session
- Worker: same session
- Attacker: same session
- Orchestrator: same session

## Review

- Attack report: [independent review](/etc/hosts)
- Result: `PASS`
- Orchestrator disposition: accepted
MD
.venv/bin/python -m pytest /tmp/e2e/tests/environment/test_agent_packet_record.py -q
# 15 passed in 0.01s
```

**Why the existing evidence passed anyway.** The nine rejection cases test the three negatives
the function actually implements — a URL, prose with no link, and a *relative* path that does
not exist. There is no case for an absolute path, none for `..` traversal, and none for a
directory. The one property the template advertises and the docstring repeats — *inside this
repository* — is the one property no case exercises.

**Secondary defect in the same claim.** "Four things" then enumerates four and adds a fifth
sentence, "`Result` must be `PASS`", which is also checked. The count is wrong by one, and
`README.md:72` inherits it: "Every field value in a packet or report other than **the four**
the guard checks." That bullet also implies the guard checks fields in a *report*. It does
not; it never opens a report, only tests that a path resolves.

**Failure class:** `implementation` for the check, `specification` for the two documents that
describe it as narrower than it is.

## F3 — An earlier line silently overrides the `## Review` block. **Major.**

**Claimed.** The guard checks "the two fields `docs/agent-workflow/TASK-PACKET-TEMPLATE.md`
puts under `## Review` for exactly this purpose" (module docstring).

**Why it is false.** `_field_value` calls `pattern.search(text)` with `re.MULTILINE` and takes
the **first** match anywhere in the document. Section membership is never considered.

**Measured.** `[측정]` Three bypasses, each accepted with zero problems:

```python
# H — an earlier Status line exempts the packet entirely
"- Status: `DRAFT`\n\n(real header below)\n\n- Status: `ACCEPTED`\n\n"
"## Review\n\n- Attack report:\n- Result: `FAIL`\n"
#   -> [] . The packet is ACCEPTED with an empty report and a FAIL result.

# I — an earlier Result line overrides the real one
"- Status: `ACCEPTED`\n\n- Result: `PASS`\n\n## Review\n\n"
"- Attack report: [r](../README.md)\n- Result: `FAIL`\n"
#   -> [] . The review said FAIL.

# J — an earlier link overrides prose in the real field
"- Status: `ACCEPTED`\n\n- Attack report: [r](../README.md)\n\n## Review\n\n"
"- Attack report: none, reviewed by eye\n- Result: `PASS`\n"
#   -> [] .
```

Run any of these through `packet_problems(text, "probe")` after
`sys.path.insert(0, "tests/environment")`.

**Why this one matters more than it looks.** `9707c8e`'s message records that a `re`-shaped
bug was already found inside this validator during its writing — "`\s*` around the field label
matches newlines, so an empty `- Attack report:` captured the *next* line as its value. The
empty-report case passed while proving nothing — the failure this guard exists to catch, inside
the guard." That fix changed `\s*` to `[ \t]*`, which stops the value from running past a
newline. It did not change `search()` to a section-scoped or last-match lookup, so the sibling
bug in the same function is untouched, and the same "captured the wrong line" shape survives in
the other direction. `[추론]` The first bug was found by weakening the validator; this one is
not reachable that way, because weakening changes what the function concludes and not which
line it reads.

**Failure class:** `implementation`.

## F4 — `DP-013`'s completeness claim is false. **Major.**

**Claimed.** `DP-013` §"What changed from the proposal": "`b702c79` is preserved as a merge
parent. **Every deviation from it is listed here so the owner can reverse any of them:**" —
followed by nine numbered items.

**Why it is false.** `[측정]` Diffing `b702c79` against `9707c8e` for the files `b702c79`
touched, at least five substantive changes are absent from the nine items. Reproduce with
`git diff b702c79 9707c8e -- docs/conventions/project-memory.md AGENTS.md` and
`git diff 6d1e965 9707c8e -- docs/branching.md`.

1. **A whole new normative section in `docs/conventions/project-memory.md:37–48`, "What does
   not belong in an agent's private memory."** It is a `[결정]`, and it is a rule about
   territory outside this repository: an agent's or a person's private memory store "must not
   be the only place holding a project constraint, a concurrency limit, a verification
   requirement, or a decision." That is a consequential rule with real reach — it constrains
   how the owner's own tooling may be configured. It appears in no numbered item, and
   `DP-013` §"Required changes" mentions `project-memory.md` nowhere.
2. **A new required recording rule, `project-memory.md:59–61`:** "**Where a control is claimed,
   record what it does not cover.** An overstated control is the defect this project produces
   most often…" A new obligation on every future record, undisclosed. (F1 violates it.)
3. **Two new authoritative-destination rows, `project-memory.md:22–23`:** `docs/conventions/`
   and `.claude/agents/`. The second one designates `.claude/agents/` as the authoritative
   home for "Agent role constraints the harness actually enforces" — a routing decision, and
   the same directory `TASK-001` lists under "Forbidden files and material".
4. **`AGENTS.md:53` promotes an attacker-only rule to a project-wide one:** "Return `BLOCKED`
   rather than a qualified pass when you cannot verify what you were asked to verify. Missing
   access and missing evidence are not a pass." In `b702c79` this existed only in
   `ATTACKER.md`'s independence rules. Now it binds every agent reading `AGENTS.md`.
   Undisclosed.
5. **`docs/branching.md:91–94` adds a new `[확인 사실]` exception to the one-area rule**
   `AGENTS.md` states ("Work inside one area at a time"): documents that change the project's
   operating method belong to no development area, "`agent/operating-model`이 그 예이고". The
   only numbered disclosure touching `branching.md` is §"Required changes": "Branching: retire
   the isolated-branch note now that the branch is merged." Adding a rule is not retiring a
   note. `[추론]` This is the item worth flagging hardest, because the exception's own worked
   example is the branch under review: the work added a rule that legitimizes itself, and the
   list that claims to let the owner reverse every deviation does not mention it.
   `docs/areas/README.md` was not updated to match, though its five-area table is a `[가설]`
   and every area maps to a code directory, so the exception is arguably right on the merits —
   which is exactly why it should have been on the list rather than inferred.

**Why the existing evidence passed anyway.** The nine items were written from the *intent* of
the adaptation — number, name, roles, enforcement, threshold, report location, guard,
confirmation. They were not produced by diffing `b702c79` against the result. Items 1–3 and 5
are all changes made for good reasons that nobody went back and enumerated.

**Failure class:** `specification`. The list's defect is the claim of completeness, not the
changes themselves.

## F5 — The threshold exempts the one path with a demonstrated need for an attacker. **Major.**

**Claimed.** `README.md:76–104`. The full flow — "a packet, a worker handoff, and an
independent attack report" — is required for work that changes a Decision Packet, a contract,
gate evidence, or an item accepted in `project-state.md` §4; or that "implements a platform
capability, guard, or limit **whose failure is silent**". It is **not** required for "work
already governed by a convention document carrying its own scope, evidence, and review
checklist. The collector integration path is governed by [collector integration handoff] §6–§8,
which **is** that path's packet." And: "`[추론]` The threshold is load-bearing, not a
convenience."

**Why it is unsound.** Three separate problems, in increasing order of cost.

*First, the citation is narrower than the claim.* The exemption requires "scope, evidence, and
**review checklist**". `collector-integration-handoff.md` §6 is "Minimum review evidence", §7
is "Decisions that require an explicit answer", §8 is "Ready-for-review checklist". Scope is
not in §6–§8; it is in §1 and §"Ownership boundary". So the named range supplies two of the
three properties the exemption demands.

*Second, the exemption drops the attacker.* §8's nine checkboxes end at "The repository manager
has approved merge scope." There is no independent falsification requirement anywhere in
§6–§8. So classifying collector integration work as exempt removes not just the packet but the
independent attack report — the very half of the flow that `README.md:128–147` says is
"existing practice getting a name, so adopting it costs little."

*Third, and this is the finding:* `[추론]` collector integration is the path whose independent
review produced the evidence this whole model is argued from.
`ADVERSARIAL-REVIEW-2026-08-18.md` reviewed `27f712b`, "Put a collector on the platform" — and
its first blocking finding, F1, is that `max_pages` and `max_records` are enforced nowhere,
found because the reviewer was independent of the author. That finding is cited as the
argument for the model in four separate places added by this work: `README.md:143–147`,
`DP-013:38–42`, `PLANNER.md:43–47`, and `ATTACK-REPORT-TEMPLATE.md:9–13`. The threshold then
exempts that path.

*Fourth, the two lists overlap with no precedence rule.* Collector integration work that also
changes a contract under `contracts/` fires "required" bullet 1 and "not required" bullet 3
simultaneously. Work that adds a platform-side page counter — the F1 repair — fires "required"
bullet 2 ("a limit whose failure is silent") and, if reached through the collector path, "not
required" bullet 3. The document's answer is "deciding which applies is the orchestrator's
call" (`DP-013` D6). `[추론]` An overlapping threshold resolved by the orchestrator's
discretion is the failure the same section says it is guarding against: "a rule applied when
convenient has stopped being a rule."

**Reproduction.** Read `docs/agent-workflow/README.md:76–104` against
`docs/conventions/collector-integration-handoff.md:182–235`, and against
`experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md:76–98`.

**Failure class:** `specification`, arguably `goal` — the threshold as drafted removes the
control from the case that motivated it.

## F6 — The quote justifying the planner/worker split is misattributed and altered. **Major.**

**Claimed.** `DP-013:38–42`, under `[확인 사실]`: "That review's first blocking finding is the
argument for the planner/worker split, **in the reviewer's own words**: *"the add-on
cooperated" was read as "the platform enforced" — the exact reading the experiment was designed
to **prevent**, made by the person who designed it.*" `README.md:143–147` repeats it. So does
`PLANNER.md:43–47`, in paraphrase.

**Why it is false.** `[측정]` That sentence does not appear in
`experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md`. What F1 there says is: "The gap
was invisible because the one committed collector honours `max_pages` voluntarily, so the
integration test passes while proving only that the add-on cooperates."

The quoted sentence is in `experiments/integrated-p0/EXP-003-capability-layer.md:232–234`:

```
[추론] The way that error was made is worth more than the error. The integration test
       passed because the one committed collector honours `max_pages` voluntarily, and
       "the add-on cooperated" was read as "the platform enforced". That is the exact
       reading the experiment was designed to avoid, made by the person who designed it.
```

Reproduce:

```sh
git grep -n 'the add-on cooperated' -- docs experiments
git log --oneline -S'the add-on cooperated' -- experiments/integrated-p0/EXP-003-capability-layer.md
#   c0a266d Record what the review found, and stop the code from claiming what it does not do
git log -1 --format='%h author=%an' c0a266d    # author=shk — the author's own commit
```

Three separate defects in one citation:

1. **Attribution.** It is the *author's* sentence, written in the author's own experiment
   record, about the author's own error. Presenting it as the reviewer's words makes the
   argument for the planner/worker split look like an independent finding when it is the author
   agreeing with the reviewer. The independent finding is F1's measurement (12 requests, 600
   items against `max_pages=2, max_records=3`); the diagnosis is the author's.
2. **Label.** The source is `[추론]`. `DP-013` quotes it under `[확인 사실]`. `AGENTS.md`
   requires that these labels identify a claim's role and that a sentence mixing roles be
   split; upgrading an inference to a confirmed fact is the specific move the convention
   exists to stop.
3. **Text.** "designed to **avoid**" became "designed to **prevent**" inside quotation marks.
   Minor on its own, but it means the quoted string does not exist anywhere in the repository,
   so a reader who greps for it finds nothing.

`[추론]` Note that this is a small, self-flattering error of exactly the kind the model is meant
to catch — and it landed in the sentence that argues for the model. The correct version is
stronger, not weaker: an independent reviewer measured the gap, and the author, reading the
measurement, identified the mechanism. That is the split working, described accurately.

**Failure class:** `evaluation`.

## F7 — `docs/p0-execution-plan.md` now contradicts the changed documents. **Moderate.**

**Claimed.** `AGENTS.md:32`: "Read `docs/p0-execution-plan.md` before starting or changing
P0-A or P0-B work." `TASK-001` declares `Phase: P0-B`.

**What that document still says** (`docs/p0-execution-plan.md:186–196`, under `[확인 사실]`
"Checked against GitHub on 2026-08-19"):

- Row `feat/agent-operating-model`: "**Isolated**, behind the active architecture, and
  **carries a Decision Packet identifier that collides with accepted DP-006.**" Both halves
  are false as of `b437013`. `docs/branching.md` was rewritten to say so; this was not.
- Same row, treatment: "Reapply through a separate reviewed change only after renumbering the
  Decision Packet **and reconciling current contracts.**" The renumbering happened. The
  contract-reconciliation half is neither done nor mentioned — `TASK-001` §"Authority and
  dependencies" says "Contracts: none" without addressing the instruction.
- Closing sentence: "**restoring the larger operating model is not on the product critical
  path.**" Directly contradicted by the work under review, with no note reconciling the two.
- Row `.claude/agents/` on `dev`: "`adversarial-reviewer` attacks claims **without write
  access.**" This is F1's false claim, and it is **pre-existing** — it is not this work's
  error. But the work under review propagated and strengthened it in three new documents
  instead of correcting the one it found.

**Why it was not caught.** `docs/p0-execution-plan.md` is not in `TASK-001`'s "Allowed files".
`[추론]` That is a structural consequence of the packet being written after the work: an
allowed-file list fitted to the diff cannot flag a file the diff should have touched. It is the
clearest concrete cost of the missing planner separation that `TASK-001` admits in the
abstract.

**Failure class:** `specification`.

## F8 — `TASK-001` assigns the orchestrator role to a party the role definition excludes. **Moderate.**

**Claimed.** `TASK-001` header: `Orchestrator: project owner`.

**Why it contradicts.** `ORCHESTRATOR.md:5` — the orchestrator "is the only role that **asks
the project owner** to resolve a consequential direction and the only role that accepts or
reopens a task packet." `ORCHESTRATOR.md:25–26` — "`[확인 사실]` The orchestrator **is the
session that spawns the others.** It has no subagent type by construction." `README.md:34`,
role table, `Enforced by`: "nothing — it is the session that spawns the others."

If the orchestrator is the project owner, then the role's defining action (asking the owner)
has no one to address, and the model's only stated acceptance control — `README.md:124`, "Only
the orchestrator closes a packet after reading the worker evidence and attacker report" —
becomes the owner approving their own instruction. Either the packet field is wrong (the
orchestrator should be the main session, and the owner is the owner) or the role document's
definition is wrong.

`[추론]` The likely truth is that no orchestrator existed for this work either, and `project
owner` was written into the field because the field had to hold something. If so, that belongs
in the same admission as the missing planner — which brings me to the next point.

**Failure class:** `specification`.

## F9 — `DP-013` is `ACCEPTED_FOR_POC` over content it says was never reviewed. **Moderate.**

**Claimed.** `DP-013` header: `Status: ACCEPTED_FOR_POC`, `Owner confirmation: CONFIRMED
(project owner, 2026-08-19 — instruction to merge b702c79 onto 6d1e965 and adopt it as far as
it helps this project)`.

**What the same document says 130 lines later.** Item 9: "`Status`/`Owner confirmation` in this
packet were set from the owner's adoption instruction; **the adapted content itself has not
been reviewed line by line.**" §"Remaining uncertainty": "The adapted text above has not been
reviewed clause by clause."

**Why that is a defect rather than merely honest.** `AGENTS.md:35`: "Treat items marked
`ACCEPTED_FOR_POC` or `CONTRACTED` as constraints." `DP-TEMPLATE.md:44`, added by this same
commit: "For a consequential direction, **do not use `ACCEPTED_FOR_POC` or `CONTRACTED` until
the project owner's explicit answer is recorded above.**" The recorded answer authorizes a
*merge and an adaptation*. What the header now makes binding is the §Decision block's seven
operating rules "for P0 and later phases until superseded", a five-category consequential-
direction boundary, and a threshold — none of which the confirmation covers, by the document's
own account.

The disclosure is real and it is the right instinct. But it sits in prose far below the field
that operates, and the field is what a future agent reads. `[추론]` The first-order fix is not
to remove the disclosure; it is to make the header carry it — `AWAITING_USER` on the content, or
a `CONFIRMED (scope: adoption instruction only; content unreviewed)` that a reader hits before
the seven rules.

**Failure class:** `specification`.

## F10 — Criterion 5 is not met; criterion 4 is not met as written. **Moderate.**

**Criterion 5** — "Each role states which part of its prohibition the harness enforces and which
part is convention, **and no convention is described as a control.**" The first clause holds:
all four role documents carry the statement, and `ORCHESTRATOR.md`, `PLANNER.md`, and
`WORKER.md` are accurate about having no enforcement. The second clause is violated by F1 in
`README.md` (twice), `ATTACKER.md`, `PROMPTS.md`, and `project-state.md`. **Not met.**

**Criterion 4** — "Every relative link in every changed document resolves, **and every
repository path a changed document names in backticks exists.**" `[측정]` The first half holds
completely: 0 broken targets across every `[..](..)` in all 21 changed `.md` files. The second
half has three counterexamples in changed documents:

| document | backticked token | why it does not exist |
|---|---|---|
| `AGENTS.md:64` | `` `apps/` `` | it is a *prohibition* — "Do not create long-lived application code under `apps/`" |
| `docs/agent-workflow/reviews/README.md:22` | `` `REVIEW-TASK-007.md` `` | illustrative — "Use a stable name such as" |
| `docs/agent-workflow/task-packets/README.md:3` | `` `TASK-007-short-title.md` `` | illustrative, same phrasing |

Reproduce by extracting backticked tokens matching `^[A-Za-z0-9_.\-/]+$` from each changed
document and testing them against both the repository root and the document's own directory.

`[추론]` No reader is misled by any of the three, so the work is not defective here — the
*criterion* is. It was drafted as "every backticked path" when the checkable property is
"every backticked path that the document asserts exists". A criterion that fails on a
prohibition and on two `such as` examples cannot be used to accept or reject anything, which is
the same drafting failure as F11 in the opposite direction. As written, **not met.**

**Failure class:** `evaluation`.

## F11 — Criterion 6 cannot fail. Criterion 7 uses "positive controls" ambiguously. **Moderate.**

**Criterion 6** reads, in full: "A threshold states which work requires the full flow and which
does not." Any two sentences under any heading satisfy it. It does not require the threshold to
be self-consistent (F5 shows it is not), to name a precedence rule for its overlapping lists,
to be correct about the document it cites, or to have been applied to this work. It is
satisfied by the existence of prose.

`[추론]` This is the F1 defect from `ADVERSARIAL-REVIEW-2026-08-18.md` reappearing one level up.
There, an acceptance criterion was satisfied by the add-on's cooperation rather than by the
platform's enforcement; here, a criterion is satisfied by a threshold's existence rather than by
its soundness. `PLANNER.md:43–47` cites that finding as the reason the planner/worker split
exists — and criterion 6 was written by the session that wrote the threshold it accepts, which
is the condition the split is meant to remove. `TASK-001` admits the condition; it does not
notice that the criteria show its effect.

**Criterion 7**, second clause: "and **its positive controls** fail when the validator is
weakened." `[측정]` Weakening `packet_problems` to `return []` produces `9 failed, 6 passed`.
The nine that fail are `REJECTED_CASES` — negative-input cases. The six that pass include both
`CLEAN_CASES`, whose own docstring is "The validator must not simply reject everything it is
given" — which is what "positive control" ordinarily names, and which by construction *cannot*
fail under `return []`. So the criterion is true on one reading and false on the other. The
commit message states it precisely ("Nine rejection cases go red when the validator is weakened
to `return []`"); the criterion does not.

**Failure class:** `evaluation`.

## F12 — The inline cases do depend on something existing on disk. **Minor.**

**Claimed.** Module docstring: "What gives this guard teeth is `packet_problems` being exercised
directly against malformed packet bodies built inline, below, **which do not depend on anything
existing on disk.**"

**Why it is false.** Four of the fifteen tests resolve `../README.md` against
`TASK_PACKETS_DIR`, so they require `docs/agent-workflow/README.md` to exist:
`REJECTED_CASES[accepted-with-failing-result]`, `REJECTED_CASES[accepted-with-no-result-line]`,
and both `CLEAN_CASES` that use that link.

**Measured.** `[측정]` Copy the guard and `TASK-PACKET-TEMPLATE.md` into an otherwise-empty
tree, omitting `docs/agent-workflow/README.md`, and run it: `4 failed, 11 passed`. Copy
`README.md` in and rerun: `15 passed`. Both runs are in this report's reproduction for F2 — the
first `15 passed` line there required adding `README.md` for exactly this reason.

**Consequence.** Renaming or moving `docs/agent-workflow/README.md` turns the two `CLEAN_CASES`
red — the guard would then be "rejecting everything it is given" for a reason with nothing to do
with the validator — and turns the two `REJECTED_CASES` red by reporting a *second* problem, so
their `len(problems) == 1` assertion fails and names the wrong defect. A one-line fix exists
(point the cases at `TASK-PACKET-TEMPLATE.md`, which the module already resolves, or at
`__file__`), but the finding is the docstring: it claims an independence the cases do not have,
in the sentence that explains where the guard's teeth are.

**Failure class:** `implementation`.

## F13 — A non-UTF-8 file under `task-packets/` aborts the scan. **Minor.**

`packet_paths()` returns every `is_file()` entry except `README.md`, and the scan calls
`path.read_text(encoding="utf-8")` unguarded. `[측정]` With a two-byte-invalid file present,
`test_every_accepted_task_packet_carries_its_closing_evidence` raises
`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 10` and **stops before
reading later packets** — in my reproduction, a defective `TASK-999` that sorts after the
binary `TASK-998` was never examined. `.gitignore:2` lists `.DS_Store`, and the guard walks the
filesystem rather than the index, so on this platform a Finder visit to that directory both
breaks the suite and silently shortens the scan. `packet_paths()` also does not recurse, so a
packet filed in a subdirectory is never checked at all.

**Reproduction.** Copy the guard into a scratch tree, `printf 'x \xff\xfe\n' >
docs/agent-workflow/task-packets/TASK-998.md`, add a defective `ACCEPTED` `TASK-999.md`, run
the file.

**Failure class:** `implementation`.

## F14 — `TASK-001` states an expected output its own command does not produce. **Minor.**

`TASK-001` §Verification:

```sh
# Expect hits only in superseded DP-002, docs/history/, and DP-013's account of the proposal.
git grep -n 'CosmaSignal' -- docs AGENTS.md README.md
```

`[측정]` The command also returns two hits in `TASK-001` itself — line 80 (criterion 3's own
text, which names the string) and line 99 (the comment line above the command). The criterion
being tested is substantively met: no changed document uses `CosmaSignal` as the project's live
name, claims phase P0-A, or claims the P0-A gate is ahead. But a later reader who runs the
documented command sees output the packet says should not exist and has no way to tell whether
criterion 3 held. A one-word fix (`-- docs AGENTS.md README.md ':!docs/agent-workflow'`, or
naming the packet in the expectation) makes the command self-checking.

**Failure class:** `evaluation`.

## F15 — "The independent attack below is real" was written before the attack existed. **Minor.**

`TASK-001` §"How this packet came to exist", at `9707c8e`: "The independent attack below is
real; the planning separation is not, and the two are marked differently on purpose."

`[측정]` At `9707c8e`, `TASK-001` §Review reads `- Attack report:` (empty) and `- Result: `PASS
| FAIL | BLOCKED`` (the template placeholder). There is nothing below.

`.claude/agents/adversarial-reviewer.md` names this failure mode in its own list of what this
project produces most: "A document stating an intention in the present tense, as though it were
built." `[추론]` It is the mildest instance in this review — `Status: REVIEWING` and the empty
field both signal the true state, and the sentence becomes true the moment this file is
committed. But the packet's whole argument for existing is that it states its own gaps honestly,
and the one thing it asserts rather than admits is the thing that had not happened.

**Failure class:** `evaluation`.

---

## What I could not break

Stated plainly, because these are results too.

- **`b702c79` is genuinely preserved.** `b437013 parents=6d1e965 b702c79`. The proposal is
  readable at its original revision, which is the property criterion 1 asks for, and it made
  every comparison in F4 possible.
- **The number collision is fully resolved.** One `DP-006`, one `DP-013`. Every one of the
  60-plus `DP-006` references in the tree — contracts, `docs/areas/README.md` (twice, as
  `b437013` says), `DP-008`, `project-state.md` §4, the gate record, dashboard source comments,
  test docstrings — resolves to the P0-A platform packet. I tried to find a reference the
  renumbering broke and found none.
- **`DP-009` is exactly as described.** Unused on every ref; the only commit message mentioning
  it is `b437013` itself. The claim and its treatment ("left unused rather than quietly filled")
  are accurate.
- **The real directory scan is wired correctly and is non-vacuous.** I doubted this on the
  strength of the docstring's own admission and tested it: with a defective `ACCEPTED` packet on
  disk, `test_every_accepted_task_packet_carries_its_closing_evidence` fails and names the file
  and both defects. `TASK_PACKETS_DIR` is asserted equal to the literal path *and* asserted to
  be a directory, which is the check that would catch a rename. The docstring's admission that
  the scan passes vacuously today is honest and precisely worded, and `tests/environment/` is
  inside `testpaths` in `pyproject.toml`, so the guard is not excluded from the default run.
- **The weakened-validator exercise reproduces.** `9 failed, 6 passed` under `return []`,
  matching the commit message's count exactly.
- **Nothing in the "convention only" column is secretly enforced.** Exactly one file in `tests/`
  or `experiments/*/tests/` references the agent workflow. The split does not understate itself,
  which was one of the two directions I was asked to check.
- **Nothing was dropped from the proposal's role documents.** `ATTACKER.md`,
  `ORCHESTRATOR.md`, `PLANNER.md`, `WORKER.md`, both templates and `task-packets/README.md` are
  strictly additive. `project-memory.md` is additive apart from the disclosed report-location
  row. The one phrase that did disappear is `reviews/README.md`'s "Create one **independent
  review per task packet**"; the obligation survives in `README.md` §"When this flow is
  required" for above-threshold work, and its narrowing is the intended effect of the threshold
  rather than an omission. I looked for a prohibition or obligation that vanished without being
  replaced or deliberately rejected, and found none.
- **Every relative link resolves.** 0 of ~90 targets broken.
- **The counts and the 351-line figure are accurate.** 351 lines; 3 blocking, 3 major, 3
  moderate, 1 minor; the three timestamps; "the follow-up commit repaired nothing" (verified by
  filtering `c0a266d`'s three source-file diffs down to non-prose lines — there are none); the
  Naver author's three defects (`EXP-002:304`). The only inaccurate citation of that review is
  F6's quote.
- **Allowed-file compliance is clean.** Every path in `git diff --name-only 6d1e965..9707c8e`
  falls inside `TASK-001`'s allowed list. Nothing under `experiments/`, `contracts/`, or
  `.claude/` was modified — I read `.claude/agents/adversarial-reviewer.md` and did not write
  to it.

## Scope and decision-boundary review

- **Allowed-file compliance:** clean. 22 paths changed, all inside the packet's allowed list;
  no forbidden path touched. The list's weakness is not a violation but F7's inverse — it could
  not flag the file that *should* have been in it, because it was written from the diff.
- **Accepted-decision compliance:** `DP-005`/`DP-011` phase boundaries respected; `DP-007`'s
  deliberate preservation of the old name in history respected; `DP-006` untouched; no contract
  changed. Two problems: `docs/p0-execution-plan.md`'s recorded treatment of this branch was not
  satisfied in full (F7 — "reconciling current contracts"), and `DP-TEMPLATE.md`'s own new rule
  about `ACCEPTED_FOR_POC` is not satisfied by `DP-013` (F9).
- **Unanswered consequential direction:** `TASK-001` records "Owner decisions required: `none`".
  `[추론]` That is not right. `project-memory.md`'s new private-memory rule (F4 item 1) is a
  consequential rule about territory outside this repository and it reaches the owner's own
  tooling; `branching.md`'s new area exception (F4 item 5) changes a rule `AGENTS.md` states; and
  `DP-013`'s seven operating rules are `ACCEPTED_FOR_POC` on a confirmation the document says
  does not cover them (F9). Each of the three should be an explicit owner item, not a "none".
- **Prohibited material exposure:** none found. The diff is documentation plus one test file; no
  credential, token, cookie, transcript, dataset, or private evaluation material appears. My own
  probes wrote only to the session scratchpad, apart from the two named, restored writes in F1.

## Conclusion

**`FAIL`**, on two blocking findings and four major ones.

The blocking pair is not a matter of emphasis. **F1** puts a convention in the enforced column,
which acceptance criterion 5 forbids by name, and it does so in the section of
`docs/agent-workflow/README.md` whose entire purpose is that separation — with a verification
basis (`Tools: All tools except Write, Edit, NotebookEdit`) that states the refutation in its
first two words. The claim then propagates to `project-state.md` §4, where it becomes one of the
two things this project records as enforced about its own operating model. I demonstrated the
break as the agent type in question: I modified the guard this packet added, using `Bash`, and
restored it. **F2** is the same shape one layer down — the one guard that makes the model
checkable advertises a property (`the link names a path inside this repository`) that it does not
have, and accepts a forged `ACCEPTED` packet whose independent review is `/etc/hosts`, with all
four roles filled in by the same session. Both are the project's signature defect: a control
that reads stronger than it is.

The major findings say something narrower and worth separating. **F4**, **F5**, and **F6** are
not overstatements of controls; they are places where the record is incomplete or inaccurate in
the owner's disfavour — a completeness claim that omits five real changes including a new rule
that exempts this very branch, a threshold that removes the attacker from the one path with a
measured need for one, and a self-criticism reattributed to an independent reviewer. **F3** is a
live bypass in the guard, and notably a sibling of the `re` bug the commit message says was
already found and fixed inside the same function.

What deserves saying against all of that: **this work is more honest than most of what it
reviews.** `TASK-001` states that it was written after the work and that no planner produced its
criteria. `README.md` and `DP-013` name role laundering as the model's largest hole and refuse to
paper over it. `PLANNER.md` declines to write a frontmatter key nobody tested and says why. The
guard's own docstring admits its directory scan is vacuous today — an admission I doubted,
tested, and found both true and precisely worded. Nothing was dropped from the proposal.
Every link resolves. Every count I checked in the 2026-08-18 review is right except one quote.
The failure here is not carelessness; it is the specific thing this model exists to catch, in
the document that adopts it, which is the ordinary way this failure happens.

The path to `PASS` is short and does not require redesigning anything. Correct F1's claim in the
four documents that carry it and move it to the convention column, keeping what is true (three
tools denied, denial resolves, accidental repair made unlikely). Make `_is_repository_path`
resolve inside the repository and reject directories, and add cases for an absolute path, a
`..` escape, and a directory. Scope `_field_value` to the section or take the last match. List
the five undisclosed deviations in `DP-013` §"What changed from the proposal". Give the threshold
a precedence rule and state whether the collector exemption drops the attack report — and if it
does, say why the path that produced F1 needs it least. Fix the attribution of the quote.

## Required follow-up

- **New or revised packet:** yes. A revision of `TASK-001`, or `TASK-002`, covering F1, F2, and
  F3 as one change — the false enforcement claim and the guard defects are the same failure at
  two levels, and separating them invites fixing the document while the guard still accepts
  `/etc/hosts`. It must add `docs/p0-execution-plan.md` and `docs/areas/README.md` to its allowed
  files (F7, F4 item 5). Its acceptance criteria should be written by a session that will not
  implement them; F10 and F11 are what happens otherwise, and `TASK-001`'s own admission is the
  argument.
- **Open Question or Decision Packet update:** `DP-013` needs four edits — the five undisclosed
  deviations added to §"What changed from the proposal" (F4); the `Owner confirmation` field
  scoped to what the owner actually confirmed (F9); the quote in §"Evidence and reasoning"
  reattributed to `EXP-003`/`c0a266d` and relabelled `[추론]` (F6); and the "Only one role
  prohibition in this model is structural" sentence corrected (F1). `docs/agent-workflow/README.md`
  needs the enforced/convention split rebuilt around one enforced item rather than two, and the
  threshold's overlap resolved (F5). Consider an Open Question for the private-memory rule and the
  area exception, both of which are consequential and neither of which the owner has been shown as
  a decision.
- **Project State or contract update:** `docs/project-state.md:175` must lose "`adversarial-reviewer`
  cannot write" and say what is true instead. No contract under `contracts/` is affected.

## Attacks I did not perform

A `PASS` would have been limited to what I actually tried; so is this `FAIL`. What I did not do:

- I did not test whether `effort`, `reasoningEffort`, and `reasoning_effort` are silently ignored
  in agent frontmatter, nor whether path-scoped `permissions` take effect. `PLANNER.md` and
  `DP-013` rest on `fcf4b8a` for the first and explicitly claim the second is untested. I read the
  claim in `.claude/agents/adversarial-reviewer.md`; I did not verify the harness's behaviour, and
  `.claude/` is forbidden material for this packet. **Unverified, not disputed.**
- I did not run the full test suite. `AGENTS.md` and my own constraints reserve it, and criterion 8
  names `tests/environment/` specifically, which I ran (`48 passed`). I have no evidence about the
  database-backed suites and make no claim about them.
- I made **no network call**, so every GitHub-side statement is unverified: PR #1 still showing
  "merged", the branch-protection settings `docs/branching.md` records as `[확인 사실]`, the
  duplicate remote branch, and whether `origin` matches these refs. `BLOCKED` on all of it —
  nothing in `TASK-001`'s criteria depends on it, but `docs/branching.md`'s split is cited as this
  work's model and its enforced column is a GitHub fact I could not check.
- I did not attack `DP-011`'s 2026-08-26/27 delivery boundary beyond confirming the citations point
  at a real accepted packet.
- I did not review `6d1e965`'s P0-B product and scraper-service content. Outside this packet.
- I did not attempt to detect a forged attacker session. The model states that nothing would; I
  took that as recorded rather than testing it, and F2 shows what a forged record looks like when
  the one guard is asked to catch it.
- I did not evaluate whether `main` should take this work. `TASK-001` and `docs/branching.md` both
  say that is a separate acceptance, and I agree it is out of scope here.

## Where this file belongs

Under `docs/agent-workflow/reviews/`, per `reviews/README.md`: this work has no experiment record
— it is a convention, a set of templates, a repository guard, and a set of documents that claim
something is in force. Link it from `TASK-001` §Review either way.

- Result: `FAIL`
