# REVIEW-TASK-001-R2 — Attack report

- Packet: [TASK-001 — Adopt the isolated agent operating model on the current branch](../task-packets/TASK-001-agent-operating-model-adoption.md)
- Worker revision: `297fbee` on `agent/operating-model` (repairs), over `933bbae` (record) and `9707c8e` (the revision REVIEW-TASK-001 attacked)
- Attacker: subagent type `adversarial-reviewer`, second independent session, no `Write`/`Edit`/`NotebookEdit`
- Date: 2026-08-19
- Result: `FAIL`

`[측정]` Environment: this checkout at `297fbee`, working tree clean (`git status --short` empty) before the first probe and after the last. Python `.venv/bin/python`, CPython 3.13.7, macOS arm64 (Darwin 25.6.0). No network call was made. Every mutation was performed on a copy under `$TMPDIR` except the two named and restored in R2-F1's verification. No symlink was created inside the repository working tree; the one in-repository symlink used as evidence (`.venv/bin/python`) already existed.

This review does not redo REVIEW-TASK-001. It asks one question of each of its fifteen findings — repaired, reworded-only, honestly recorded as unrepaired, or silently open — and then attacks the repairs themselves.

## Reproduced worker evidence

| Claim | Command or procedure | Observed result | Evidence |
|---|---|---|---|
| Criterion 1 — `b702c79` is a merge parent | `git log -1 --format='%h parents=%p' b437013` | `b437013 parents=6d1e965 b702c79` | verified |
| Criterion 2 — one `DP-006`, one `DP-013` | `ls docs/decisions/` | `DP-006-p0a-platform-foundation.md`, `DP-013-agent-workflow-and-project-memory.md`; one of each | verified |
| Criterion 3 / F14 — the corrected verification command produces the stated output | `git grep -n 'CosmaSignal' -- docs AGENTS.md README.md ':!docs/agent-workflow'` | 8 hits, all in superseded `DP-002`, `docs/history/`, and `DP-013:154`'s account of the proposal — exactly the stated expectation, and no hits in the packet itself | verified; **F14 repaired** |
| Criterion 4 — every relative link resolves | resolved all `[..](..)` targets in all 24 changed `.md` files against each file's own directory | 142 targets checked, **0 broken** | verified |
| Criterion 4 — every backticked path a changed document *asserts exists* resolves | extracted every backticked `^[A-Za-z0-9_.\-/]+$` token from the 24 changed `.md` files; resolved against the git index, the repo root, the document's own directory, and basename | 45 unresolved, and every one is a nameable exclusion: branch names (`agent/operating-model`, `feat/agent-operating-model`, `p0a/platform-core`, `origin/sooho`), `/etc/hosts` (deliberately outside), quoted link-target strings inside REVIEW-TASK-001's own reproductions, and the two "such as" filenames F10 named | **met**, and the three F10 counterexamples are now covered by the criterion's own named exclusions |
| Criterion 5 — no convention described as a control | read the role table, `ATTACKER.md`, `PROMPTS.md`, `project-state.md:175`, `DP-013:52`, `p0-execution-plan.md:190`, `reviews/README.md` | every one of F1's six sites now states the mitigation and names what it does not cover | **met**, with one residual — see **R2-F7** |
| Criterion 6 — the threshold does all four things | read `README.md:88–129` against `docs/conventions/collector-integration-handoff.md` headings | all four present: required list (93–97), precedence rule (119–122), "exemption is from the packet, never from the attacker" (113–118), section citation (105–107) | **met** as written; the citation is imprecise and the precedence rule creates a conflict — see **R2-F3** |
| Criterion 7 — the seven named rejections, the duplicate rule, non-UTF-8, and the weakened control | `pytest tests/environment/test_agent_packet_record.py -q`; then `packet_problems` body replaced with `return []` in a copy | `29 passed`; weakened: `20 failed, 9 passed` — the 19 `REJECTED_CASES` plus `test_scanning_reports_a_non_utf8_file_and_keeps_going`. All 19 rejection cases go red | **met** as written |
| Criterion 8 — `tests/environment/` passes; `ruff` and `mypy` clean | `.venv/bin/python -m pytest tests/environment/ -q`; `ruff check`; `mypy` | `62 passed in 0.80s` (48 before; the guard went 15 → 29). `ruff check`: `All checks passed!`. `mypy`: `Success: no issues found in 1 source file` | verified — see the note below |
| `933bbae` repaired nothing | `git diff --stat 9707c8e 933bbae` on the guard | the only source change is the module docstring; `git diff 9707c8e 933bbae -- tests/` touches no executable line | verified |
| F2's own end-to-end scenario now fails | copied the guard, `TASK-PACKET-TEMPLATE.md` and `AGENTS.md` into `$TMPDIR/r2e2e`, planted the report's forged `TASK-002` linking `/etc/hosts`, ran the whole guard file | `2 failed, 27 passed`; `test_every_accepted_task_packet_carries_its_closing_evidence` **FAILED** and named the packet. Against the vulnerable code the same scenario was `15 passed` | verified |
| OQ-011's two rules are marked proposed *where they live* | read `docs/conventions/project-memory.md:39–43` and `docs/branching.md:91–95` | both carry a `[가설]` **Proposed, not accepted** block with a link to `OQ-011`, above the rule text; `branching.md`'s exception lost its `[확인 사실]` label | verified |
| `OQ-011` is registered | `docs/project-state.md:204`; `DP-013:9` `Related Open Questions` | both updated | verified |

`[측정]` One measurement against criterion 8 that is **not** a finding: `ruff format --check` on the guard reports `1 file would be reformatted` (the `Result:`-duplicate `problems.append(...)` call at lines 222–224 fits on one 100-column line). `[추론]` The project's documented lint loop is `ruff check` only — `.claude/agents/mechanical.md:54`, `.claude/agents/addon-author.md:52,87` and `docs/conventions/addon-authoring.md:298` all name `ruff check`, and no formatter invocation appears anywhere in the repository. Criterion 8's "`ruff` is clean" is met on the project's own reading. Recording the divergence rather than scoring it.

## Disposition of every REVIEW-TASK-001 finding

This is the criterion 9 audit. `repaired` means the defect is gone and I reproduced its absence; `honest-record` means it is stated as unrepaired with a reason; `partial` means part of the finding survives.

| # | Original severity | Disposition | Basis |
|---|---|---|---|
| F1 | Blocking | **honest-record**, correctly | All six sites corrected and the corrected wording is *true*, not vaguer. I re-verified the underlying capability myself. `297fbee`'s message states plainly that the fact does not change and names the real fix (review from a worktree or copy) as out of scope. Two residuals: **R2-F6**, **R2-F7** |
| F2 | Blocking | **repaired** | Containment now holds against absolute paths, `..` escapes, directories, symlink escape, dangling symlinks, symlink loops, `//`-prefixed paths, backslashes, percent-encoded `..`, `~`, query strings, empty targets, and a macOS case-variant. Residuals: **R2-F4**, **R2-F8**, **R2-F10** |
| F3 | Major | **partial — the finding as stated is still reproducible** | The three named bypasses (H, I, J) are closed. The finding's own title — "an earlier line silently overrides the `## Review` block" — is reproducible in a new form. **R2-F1**, Blocking |
| F4 | Major | **repaired**, with a small new gap | Nine items → fourteen; items 10–14 match what F4 named. **R2-F9** is what `297fbee` itself added without listing |
| F5 | Major | **repaired, and it created a conflict** | Both unsoundness halves are fixed in `README.md`; the fix now contradicts `DP-013` D6 and `ORCHESTRATOR.md`. **R2-F3** |
| F6 | Major | **partial — repaired in `DP-013`, standing verbatim in `README.md`** | **R2-F2**, Major. This is the criterion 9 trigger |
| F7 | Moderate | **repaired** | All three stale rows and the pre-existing "without write access" row corrected in `docs/p0-execution-plan.md:190–191`; the two delivery sentences retained with a stated reason at 197–201; the contract-reconciliation half answered in the row itself |
| F8 | Moderate | **repaired** | `TASK-001:8` now reads `Orchestrator: main session`, with the collapse F8 identified stated in the same line |
| F9 | Moderate | **repaired as prescribed** | `Owner confirmation` now carries the scope inline: "the adapted text below was NOT reviewed clause by clause; §Decision's seven rules, the consequential boundary, and the threshold are in force on that instruction and nothing narrower." F9 offered exactly this as its first-order fix |
| F10 | Moderate | **repaired** | Criterion 4 rewritten with the exclusion class named and required to be nameable; criterion 5 now met (see the evidence table). The rewrite is what F10 itself asked for — it said the criterion, not the work, was defective |
| F11 | Moderate | **repaired** | Criteria 6 and 7 rewritten. Both are now falsifiable and both are met; I confirmed criterion 7's `return []` clause by measurement |
| F12 | Moderate→Minor | **repaired, with a new instance of the same shape** | The four `../README.md` cases now anchor on `TASK-PACKET-TEMPLATE.md`; a minimal tree without `docs/agent-workflow/README.md` gives `29 passed`. **R2-F5** is the new dependency and the wrong count |
| F13 | Minor | **partial** | Non-UTF-8 and subdirectory are repaired and each has its own named test. A different exception raised inside `packet_problems` still aborts the scan. **R2-F4** |
| F14 | Minor | **repaired** | Command corrected with `':!docs/agent-workflow'`; I ran it and its output matches the stated expectation exactly |
| F15 | Minor | **repaired** | The sentence is gone; `TASK-001:25–29` replaces it with a `[확인 사실]` recording that the earlier revision said it while the field was empty |

**No finding is silently open.** All fifteen are addressed somewhere in `933bbae` or `297fbee`. Three (F3, F6, F13) are presented as closed while part of the defect survives.

## Adversarial cases

| Case | Failure class | Expected constraint | Observed result | Severity | Reproduction |
|---|---|---|---|---|---|
| R2-F1 — an **indented** `## Review` block is invisible to the guard; top-level decoys are the only matches | `implementation` | F3 repaired: "an earlier decoy `- Status:`, `- Result:`, or `- Attack report:` line silently overrode the real one under `## Review`. Fixed…" | forged `TASK-003` whose `## Review` says `Attack report: none` and `Result: FAIL`, with `PASS` decoys below: **the real directory scan passes green** | **Blocking** | below |
| R2-F2 — F6's misattributed, altered quote still stands in `docs/agent-workflow/README.md:169–171` | `evaluation` | F6 named `README.md:143–147` as one of three sites; criterion 9 forbids closing a finding while the claim it contradicts survives | `DP-013` corrected; `README.md` unchanged, still attributing the author's `[추론]` to "the review's first blocking finding" and still misquoting one word | **Major** | below |
| R2-F3 — the F5 repair now contradicts `DP-013` D6 and `ORCHESTRATOR.md:36` | `specification` | `AGENTS.md`: "Treat items marked `ACCEPTED_FOR_POC` as constraints"; `README.md:7` names `DP-013` its governing decision | `README.md:121` says the overlap resolves "not by discretion"; `DP-013:86` and `ORCHESTRATOR.md:36` both still say "deciding which applies is the orchestrator's call" | Moderate | below |
| R2-F4 — a link target that makes `Path.resolve()` raise aborts the whole scan | `implementation` | criterion 7 / F13: "reports a non-UTF-8 file by name and keeps scanning rather than aborting" | `OSError: [Errno 63] File name too long` propagates out of `scan_task_packets`; a later defective packet is never examined | Moderate | below |
| R2-F5 — the F2 repair introduced a new undisclosed on-disk dependency, and the docstring's count is wrong three ways | `implementation` | module docstring: the inline cases anchor on `TASK_PACKET_TEMPLATE` "rather than inventing a new dependency" | one case depends on `docs/agent-workflow/reviews/` existing; docstring says "two", commit message says "four", actual is seven | Minor | below |
| R2-F6 — the same 2026-08-18 property is `[확인 사실]` at `README.md:159` and `[추론]` at `README.md:71` | `evaluation` | `AGENTS.md`: labels identify a claim's role; split a sentence that mixes roles | one file, one property, two labels | Minor | below |
| R2-F7 — `reviews/README.md:24–26` still gives the tool denial as the *cause* of the transcription convention | `assumption` | F1: the denial is not a write barrier — and the next paragraph of the same file says so | "`adversarial-reviewer` is denied `Write` and `Edit`, **so** it returns the report body", labelled `[확인 사실]` | Minor | below |
| R2-F8 — any existing file inside the repository passes as the independent review, including `.git/config` | `specification` | template: the target "lies inside this repository, is a file rather than a directory, and exists" | `.git/config`, `.git/HEAD`, `.gitignore` all accepted with 0 problems. The claim is now literally true; the bar is what is weak | Minor | below |
| R2-F9 — `297fbee` added rules `DP-013`'s fourteen-item list does not carry, and item 14's own description is stale | `specification` | `DP-013`: "Every deviation from it is listed here so the owner can reverse any of them" | the two threshold-bounding rules are not listed; item 14 still says `branching.md` "gained a `[확인 사실]` exception" when `297fbee` relabelled it `[가설]` | Minor | below |
| R2-F10 — `_linked_report_target` takes the first markdown link in the field | `implementation` | the field names *the* attack report | `[placeholder](../TASK-PACKET-TEMPLATE.md) — the real one is [here](https://example.com/none)` → 0 problems | Minor | below |

---

# Findings in full

## R2-F1 — The `## Review` block can still be silently overridden. Indent it. **Blocking.**

**Claimed.** The guard's module docstring, lines 25–32: "**F3:** every field lookup took the first matching line anywhere in the document, with no regard for how many there were or where, so an earlier decoy `- Status:`, `- Result:`, or `- Attack report:` line silently overrode the real one under `## Review`. **Fixed** by rejecting any field that has more than one matching line, wherever they fall." `TASK-PACKET-TEMPLATE.md:12–16` states it as a property of the file. `297fbee`'s message: "**Rejecting any duplicate `Status`, `Attack report`, or `Result` line, at any position, closes both directions and parses no heading boundaries.**"

**Why it is not enough.** The duplicate rule only fires when the regex sees two matches. `_field_values` compiles `rf"^-[ \t]*{field}:[ \t]*(.*)$"` with `re.MULTILINE`. The `-` is anchored at column 0. A markdown list item indented by two spaces is still a list item, and `*` is still a bullet — neither matches. So a packet with the real fields indented (or bulleted with `*`) and decoys at column 0 presents the guard with **exactly one match per field**, which is what the rule requires.

`297fbee`'s message argues the repair explicitly declines to parse heading boundaries. That decision is defensible on its own terms and I am not disputing it. The consequence is that the repair does not cover a case where there is no duplicate to reject, and nothing records that.

**Measured.** `[측정]` Against the guard at `297fbee`, `sys.path.insert(0, "tests/environment")`:

```python
# real fields indented two spaces; decoys at column 0
t = ("- Status: `ACCEPTED`\n\n## Review\n\n"
     "  - Attack report: none, reviewed by eye\n"
     "  - Result: `FAIL`\n"
     "  - Orchestrator disposition: accepted anyway\n\n"
     "<!-- machine-readable duplicates for the guard -->\n"
     "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n"
     "- Result: `PASS`\n")
packet_problems(t, "probe")            # -> []
_field_values(t, "Result")             # -> ['`PASS`']   (the FAIL line is invisible)
_field_values(t, "Attack report")      # -> ['[r](../TASK-PACKET-TEMPLATE.md)']
```

The `*`-bullet variant behaves identically:

```python
t2 = ("- Status: `ACCEPTED`\n\n## Review\n\n"
      "* Attack report: never ran\n* Result: `FAIL`\n\n"
      "- Attack report: [r](../TASK-PACKET-TEMPLATE.md)\n- Result: `PASS`\n")
packet_problems(t2, "probe")           # -> []
```

**End to end, through the real guard file**, exactly as REVIEW-TASK-001 F2 did it:

```sh
S="$TMPDIR/r2e2e"
mkdir -p "$S/tests/environment" "$S/docs/agent-workflow/task-packets"
cp tests/environment/test_agent_packet_record.py "$S/tests/environment/"
cp docs/agent-workflow/TASK-PACKET-TEMPLATE.md "$S/docs/agent-workflow/"
cp AGENTS.md "$S/AGENTS.md"
cat > "$S/docs/agent-workflow/task-packets/TASK-003-forged.md" <<'MD'
# TASK-003 — Accepted on a review that returned FAIL

- Status: `ACCEPTED`
- Planner: same session
- Worker: same session
- Attacker: same session

## Review

The reviewer's verdict, recorded for the record:

  - Attack report: none. No independent review was run; I read it myself.
  - Result: `FAIL`
  - Orchestrator disposition: accepted anyway, over the reviewer's objection.

Machine-readable summary:

- Attack report: [review](../TASK-PACKET-TEMPLATE.md)
- Result: `PASS`
MD
.venv/bin/python -m pytest "$S/tests/environment/test_agent_packet_record.py" -q
```

`[측정]` `test_every_accepted_task_packet_carries_its_closing_evidence` **passes.** (The run reports `1 failed, 28 passed`; the one failure is `accepted-report-links-to-a-directory`, which is R2-F5 and is caused by the scratch tree lacking `docs/agent-workflow/reviews/`, not by the forged packet. Recreate that directory and the run is `29 passed`.)

**Why this matters more than the shape suggests.** The packet under review is `REWORK` precisely because `ACCEPTED` on a `FAIL` report "would be the acceptance control failing in its first use". The guard exists to make that failure mechanically impossible. A forged packet that says `Result: FAIL` and `Attack report: none` **in the section a human reads**, and `PASS` plus a resolvable link in a section a human skims past, passes. The one enforced item in the model's enforced column does not hold against a two-space indent.

`[추론]` There is a second-order effect worth naming. The duplicate rule *does* fire on a packet that quotes an example of its own format inside a fenced code block — I measured `['probe: 2 `Result:` lines found; exactly one is required']` for a well-formed packet with a ```` ```md ```` block containing `- Result: \`PASS\``. An author who hits that rejection has one obvious way out: indent or re-bullet one of the two lines. The rejection path and the bypass path are the same edit.

**Failure class:** `implementation`.

**Consequence for the packet.** Criterion 7 as written is *met* — it names the three original bypasses and they are closed. Criterion 9 is not: F3's finding, as F3 states it, is still reproducible, and no document records that the repair leaves this open.

## R2-F2 — F6's misattributed quote was fixed in `DP-013` and left standing in `README.md`. **Major.**

**Claimed.** `933bbae`'s message, under `DP-013`: "the sentence quoted as 'the reviewer's own words' under `[확인 사실]` is the author's `[추론]` from `EXP-003`, added by `c0a266d`, with one word changed." `DP-013:43–50` now carries the corrected version — attributed to `EXP-003`/`c0a266d`, labelled `[추론]`, with "avoid" restored.

REVIEW-TASK-001 F6 named **three** sites: "`DP-013:38–42` … `README.md:143–147` repeats it. So does `PLANNER.md:43–47`, in paraphrase."

**Why it is not repaired.** `docs/agent-workflow/README.md:169–171`, at `297fbee`, verbatim:

> which is why **the review's first blocking finding** is the argument for it: *"the add-on cooperated" was read as "the platform enforced" — the exact reading the experiment was designed to **prevent**, made by the person who designed it.*

Both defects F6 identified are untouched here:

1. **Attribution.** It is introduced as "the review's first blocking finding". `[측정]` `git grep -n 'add-on cooperated' -- docs experiments` returns four hits: `REVIEW-TASK-001.md:387` (the review quoting the true source), `REVIEW-TASK-001.md:394-395` (its reproduction commands), `DP-013:44` (corrected), and `EXP-003-capability-layer.md:233`. The sentence appears **nowhere** in `ADVERSARIAL-REVIEW-2026-08-18.md`. Its source is `EXP-003-capability-layer.md:231–234`, labelled `[추론]`, added by `c0a266d` — the author's own commit about the author's own error.
2. **Text.** `[측정]` `git grep -n 'designed to prevent\|designed to avoid'` returns `README.md:171` as the *only* occurrence of "designed to prevent" in the repository. Every real source says "avoid". The string inside those quotation marks exists in exactly one place: the sentence that claims to be quoting.

`PLANNER.md:43–47` needed no repair and got none — it paraphrases ("an acceptance criterion satisfied by the add-on's cooperation rather than by the platform, written and read by the same person"), does not use quotation marks, and is accurate about what the review's F1 measured. Correct as it stands.

**Reproduction.**

```sh
sed -n '166,172p' docs/agent-workflow/README.md
grep -n -A4 'add-on cooperated' experiments/integrated-p0/EXP-003-capability-layer.md
git grep -n 'designed to prevent' -- docs experiments   # README.md:171, and nothing else
```

**Why the existing evidence passed anyway.** `933bbae`'s message organises its corrections by *document*, and `DP-013`'s row is where F6 was filed. `README.md`'s row in the same list covers only F1's three items and the "four the guard checks" count. `[추론]` The finding was worked through as "which document did I file this under" rather than as "which locations did the review name", and F6 named three.

**Consequence for the packet.** Criterion 9: "Every finding … is either repaired or recorded with the reason it was not." F6 is neither, at this location. **Criterion 9 is not met.**

**Failure class:** `evaluation`.

## R2-F3 — The F5 repair contradicts `DP-013` D6 and `ORCHESTRATOR.md`, both unamended. **Moderate.**

**Claimed.** `README.md:119–122`, added by `297fbee`:

> - **"Required" wins when both lists fire.** … `[결정]` The overlap resolves **upward, not by discretion** — a threshold whose ambiguous cases are settled case by case is the "rule applied when convenient" this section warns about.

`297fbee`'s message states it the same way: "the overlap resolves upward rather than by the orchestrator's discretion".

**What still says the opposite.** Two documents, neither touched by `297fbee`:

- `docs/decisions/DP-013-agent-workflow-and-project-memory.md:84–86`, §Decision item 6, which is `ACCEPTED_FOR_POC` and which `AGENTS.md:35` requires be treated as a constraint: "**The full flow is required by threshold, not by default.** `docs/agent-workflow/README.md` names the work that requires a packet and an independent report, and the work that does not. **Deciding which applies is the orchestrator's call** and recording the call is part of it."
- `docs/agent-workflow/ORCHESTRATOR.md:34–37`, `[결정]`: "Not every change goes through a packet. `README.md` states which work requires the full flow and which does not; **deciding that is the orchestrator's call** and recording the call is part of it."

`README.md:7` names `DP-013` as its governing decision. REVIEW-TASK-001 F5's fourth point cited D6 *by name* as the document's answer to the overlap — "The document's answer is 'deciding which applies is the orchestrator's call' (`DP-013` D6)" — so the conflict was visible in the finding being repaired.

`[추론]` The repair is the right call on the merits and F5 argued for it. The defect is that a convention document now overrides an accepted Decision Packet's operative clause without amending it, and `DP-013`'s own §"What changed from the proposal" does not list the change. A later reader who follows `AGENTS.md` to the accepted packet gets the discretionary rule.

**Reproduction.**

```sh
sed -n '110,123p' docs/agent-workflow/README.md
sed -n '84,86p'  docs/decisions/DP-013-agent-workflow-and-project-memory.md
sed -n '34,37p'  docs/agent-workflow/ORCHESTRATOR.md
```

**Secondary, and smaller.** Criterion 6's fourth clause requires the exemption document be cited "by the sections that actually carry scope, evidence, and a checklist". `README.md:105–107` cites "scope in §1 and §'Ownership boundary', evidence in §6, unresolved choices in §7, the checklist in §8". `[측정]` §"Ownership boundary" is a five-row owner table — genuinely scope; §6 is "Minimum review evidence"; §8 is "Ready-for-review checklist". All three required properties are correctly cited, so **criterion 6 is met**. But §1 is "Fill this in before connecting a collector", a per-source intake table whose first two rows are `Source name` and `source_id` — configuration, not scope. Including it is imprecise rather than wrong, and I am recording it rather than scoring it.

**Failure class:** `specification`.

## R2-F4 — F13's abort is repaired for `UnicodeDecodeError` only; the F2 repair reintroduced it. **Moderate.**

**Claimed.** Criterion 7: the guard "reports a non-UTF-8 file by name and **keeps scanning rather than aborting**." The docstring (lines 65–71): `scan_task_packets` "does not let one file it cannot decode abort the rest of the scan."

**Why it is narrower than the failure class F13 named.** F13's finding was "a guard should report a defect, not raise". The repair wraps exactly one call in exactly one `except UnicodeDecodeError`. `_report_target_problem`, added by the F2 repair *after* F13 was written, calls `(TASK_PACKETS_DIR / path_part).resolve()` unguarded, and `Path.resolve()` raises on inputs a link target can carry.

**Measured.** `[측정]`

```python
packet_problems(P("a\x00b"), "probe")     # ValueError: lstat: embedded null character in path
packet_problems(P("x"*5000), "probe")     # OSError: [Errno 63] File name too long
```

And through the real scan, reproducing F13's original shape — a poison packet sorting before a defective one:

```sh
S="$TMPDIR/r2abort"
mkdir -p "$S/tests/environment" "$S/docs/agent-workflow/task-packets" "$S/docs/agent-workflow/reviews"
cp tests/environment/test_agent_packet_record.py "$S/tests/environment/"
cp docs/agent-workflow/TASK-PACKET-TEMPLATE.md "$S/docs/agent-workflow/"
cp AGENTS.md "$S/AGENTS.md"
LONG=$(python3 -c "print('x'*5000)")
printf -- '- Status: `ACCEPTED`\n\n## Review\n\n- Attack report: [r](../%s)\n- Result: `PASS`\n' "$LONG" \
  > "$S/docs/agent-workflow/task-packets/TASK-100-poison.md"
printf -- '- Status: `ACCEPTED`\n\n## Review\n\n- Attack report:\n- Result: `FAIL`\n' \
  > "$S/docs/agent-workflow/task-packets/TASK-900-defective.md"
.venv/bin/python -m pytest "$S/tests/environment/test_agent_packet_record.py" -q
```

`[측정]` `scan_task_packets` raises `OSError: [Errno 63]` at `pathlib/_local.py:515`. `TASK-900-defective` — which sorts after the poison file and carries an empty report and a `FAIL` result — is **never examined**. The suite does go red, so this is not a silent pass; the harm is the same one F13 named: the scan stops short and the reported defect is the wrong one.

`[추론]` Criterion 7's letter is met — it names non-UTF-8 specifically, and non-UTF-8 is handled with its own test. I am not scoring this against criterion 7. It is scored against criterion 9, as F13's failure class surviving in the code written to close F2.

**Failure class:** `implementation`.

## R2-F5 — The F12 repair introduced one new on-disk dependency, and three different counts describe it. **Minor.**

**Claimed.** Module docstring, lines 55–63: "**Two** of those inline cases resolve a link against `TASK_PACKET_TEMPLATE` rather than **inventing a new dependency**: that file is already load-bearing for this module … instead of turning two unrelated cases red for a reason that has nothing to do with the validator — which is what happened, per REVIEW-TASK-001.md **F12**." `297fbee`'s message says "the **four** cases that needed a real file on disk now anchor on `TASK-PACKET-TEMPLATE.md`".

**Measured.** `[측정]` Link targets across `REJECTED_CASES` and `CLEAN_CASES` at `297fbee`:

| target | count | on-disk dependency |
|---|---|---|
| `../TASK-PACKET-TEMPLATE.md` (incl. one `#objective` variant) | **7** | already load-bearing — as claimed |
| `../../../AGENTS.md` | 1 | **new**, disclosed in an inline comment at lines 485–489, not in the docstring |
| `../reviews` | 1 | **new, undisclosed anywhere** |
| `../reviews/REVIEW-TASK-DOES-NOT-EXIST.md` | 1 | negative — requires absence, safe |
| `/etc/hosts`, ten-level `..`, `../../..` | 3 | rejected at containment before any stat |

So: the docstring says two, the commit message says four, the count is seven, and there are two new dependencies rather than none.

**The `../reviews` one is F12's exact shape.** `accepted-report-links-to-a-directory` asserts the message `is a directory, not a file`. `[측정]` In a tree without `docs/agent-workflow/reviews/`, that case fails with `AssertionError: assert 'is a directory, not a file' in "packet: Attack report links to '../reviews', but …/reviews does not exist"` — a case turning red, and naming the wrong defect, for a reason with nothing to do with the validator. That is F12's sentence, applied to a case F12 did not cover because it did not exist yet.

`[확인 사실]` Both `docs/agent-workflow/reviews/README.md` and `REVIEW-TASK-001.md` are tracked, so the directory exists in every checkout today. This is a latent dependency and a wrong docstring, not a live breakage — hence Minor. The fix is one character: `../reviews/` → any directory the module already resolves, or `TASK_PACKETS_DIR` itself.

**Reproduction.** The `$TMPDIR/r2e2e` tree in R2-F1, without `mkdir docs/agent-workflow/reviews`: `1 failed, 28 passed`, the failure being this case. Add the directory: `29 passed`.

**Failure class:** `implementation`.

## R2-F6 — One property, two evidence labels, in one file. **Minor.**

`docs/agent-workflow/README.md:157–160`, under `[확인 사실]`:

> `[확인 사실]` `27f712b` and `c0a266d` are a worker result and an independent attack on it … **A reviewer with no write access** returned three blocking, three major, three moderate, and one minor finding …

`docs/agent-workflow/README.md:71–73`, ninety lines earlier, under `[추론]`:

> `[추론]` The 2026-08-18 reviewer **had the stronger property this section used to claim — it worked from a copy** — and that property belongs to the copy, not to `disallowedTools`.

`DP-013:35` carries the `[확인 사실]` version too: "a reviewer with no write access attacked the work, returned ten findings".

`[확인 사실]` The sole basis for either is `experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md:5–6`, a self-description: "an independent agent with no write access to the repository, working from a copy." `[추론]` That is precisely the kind of claim F1 refuted for the *current* reviewer — a stated tool property taken as a capability property. The `[추론]` label at line 71 is the correct one for it; the `[확인 사실]` at line 159 is not, and the two sit in the same file. `AGENTS.md` §"Evidence and contracts": the labels identify a claim's role, and a sentence mixing roles should be split.

The `[확인 사실]` version also drops "working from a copy" — the half that would make the property true, and the half `README.md:71–73` says is doing all the work.

I did not attempt to verify whether the 2026-08-18 reviewer actually worked from a copy; that session is not reproducible from this checkout. **Unverified, not disputed.**

**Reproduction.** `sed -n '71,73p;157,160p' docs/agent-workflow/README.md` and `sed -n '5,6p' experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md`.

**Failure class:** `evaluation`.

## R2-F7 — `reviews/README.md` still gives the tool denial as the cause, then refutes it two lines later. **Minor.**

`docs/agent-workflow/reviews/README.md:24–26`:

> `[확인 사실]` The attacker does not commit its own report. `adversarial-reviewer` **is denied `Write` and `Edit`, so** it returns the report body and **the session under review commits it.**

`docs/agent-workflow/reviews/README.md:30–33`, the next paragraph:

> `[추론]` The leak is real rather than theoretical, because the denial is not a write barrier — `REVIEW-TASK-001` F1 measured an attacker writing through `Bash`. So **nothing prevents an attacker from filing its own report either.** The reason to keep the transcription convention is not that the attacker cannot write; it is that a report and its repair should not arrive in the same hand.

The second paragraph is exactly right and is the F1 repair. The first paragraph, one sentence earlier and labelled `[확인 사실]`, still asserts the causal chain the second denies: *denied Write, **so** it returns the body*. It does not return the body because it is denied `Write`; it returns the body because the convention says to. The correction is present; the sentence it corrects was left in place above it.

`[추론]` This is the surviving-sentence pattern in its mildest form. It is Minor because the refutation is two lines below and any reader reaching the second paragraph is corrected. It is worth reporting because criterion 5's second clause — "no convention is described as a control" — is what this sentence does, in a file that is not a role document and therefore was not swept when criterion 5 was checked.

**Reproduction.** `sed -n '22,34p' docs/agent-workflow/reviews/README.md`.

**Failure class:** `assumption`.

## R2-F8 — Containment now holds, and "inside the repository" is a low bar. **Minor.**

This is the residual after F2 is repaired, stated so the owner can decide whether it matters, not a claim that anything is false.

`[측정]` What the repaired check accepts as the independent review of an `ACCEPTED` packet:

| target | verdict |
|---|---|
| `../../../.git/config` | **accepted, 0 problems** |
| `../../../.git/HEAD` | **accepted, 0 problems** |
| `../../../.gitignore` | **accepted, 0 problems** |
| `../../../AGENTS.md ` (trailing space) | accepted — `.strip()` |
| `../../../AGENTS.md#anchor` | accepted — fragment stripped, as designed |

The template's claim is now literally accurate: the target lies inside the repository, is a file, and exists. Nothing is overstated. `[추론]` What it buys is narrower than "the packet carries its closing evidence": it proves a path resolves, and the docstring and `README.md:59` both say so in as many words ("the guard never opens the report it resolves"). A stricter bar is available at no cost — requiring the target to be under `docs/agent-workflow/reviews/` or to match `*REVIEW*` / `*ADVERSARIAL-REVIEW*`, which `reviews/README.md` already establishes as the two homes — but choosing it is a decision, not a repair, and I am not calling the current state a defect.

**Reproduction.** With `sys.path.insert(0, "tests/environment")`, run `packet_problems` over `"- Status: \`ACCEPTED\`\n\n## Review\n\n- Attack report: [r](../../../.git/config)\n- Result: \`PASS\`\n"`.

**Failure class:** `specification`, at the level of what the control is worth rather than what it claims.

## R2-F9 — Small gaps in the fourteen-item completeness claim. **Minor.**

**Claimed.** `DP-013` §"What changed from the proposal": "Every deviation from it is listed here so the owner can reverse any of them", now fourteen items, with a `[확인 사실]` noting that items 10–14 were missing when the list first claimed completeness.

**Verified.** `[측정]` I diffed `b702c79` against `297fbee` for every file `b702c79` touched (`git diff --name-status b702c79^ b702c79` gives the nineteen). Items 10–14 correspond one-for-one to what F4 found. `docs/decisions/DP-TEMPLATE.md`, `docs/open-questions/OQ-TEMPLATE.md`, `docs/open-questions/README.md`, and `docs/agent-workflow/task-packets/README.md` are **byte-identical** to `b702c79`. The list is substantially complete.

What is not on it:

1. **The two threshold-bounding rules** `297fbee` added at `README.md:110–122` — "the exemption is from the packet, never from the attacker" and "'Required' wins when both lists fire". These are new `[결정]` rules relative to `b702c79`, the second contradicts `DP-013` D6 (R2-F3), and neither appears in §"What changed from the proposal" or §"Required changes". Item 6 discloses that *a threshold* was added, which arguably covers them; the D6 conflict is what makes the omission matter.
2. **Item 14's description is now stale.** It reads "`branching.md` gained a **`[확인 사실]`** exception to the one-area rule". `297fbee` relabelled that exception `[가설]` **Proposed, not accepted** in the course of opening `OQ-011`. Item 14 describes the state at `933bbae`, not at `297fbee`.
3. **Three of the four `AGENTS.md` bullets added by the adaptation.** Item 13 lists the `BLOCKED` promotion. Its three siblings in the same hunk — "Spawn the subagent type where one exists", "The full flow is required by threshold, not by default", and "Do not describe a convention as a control" — are not listed. `[추론]` Each echoes a disclosed item (4, 6, 5 respectively), so listing them would be near-redundant; I report it only because item 13 set the precedent that an `AGENTS.md` promotion is itself a listable deviation.
4. `WORKER.md`'s new §"Writing a packet for `addon-author` is different" is a planning instruction rather than an enforcement statement, and item 4 covers only the enforcement half.

**Reproduction.** `git diff b702c79 297fbee -- AGENTS.md docs/agent-workflow/ORCHESTRATOR.md docs/agent-workflow/WORKER.md docs/agent-workflow/PLANNER.md docs/agent-workflow/ATTACK-REPORT-TEMPLATE.md`, read against `DP-013:150–190`.

**Failure class:** `specification`.

## R2-F10 — The first link in the field wins. **Minor.**

`_linked_report_target` uses `_MARKDOWN_LINK.search(report)` and returns the first match. `[측정]`

```python
t = ("- Status: `ACCEPTED`\n\n## Review\n\n"
     "- Attack report: [placeholder](../TASK-PACKET-TEMPLATE.md) — the real one is "
     "[here](https://example.com/none)\n- Result: `PASS`\n")
packet_problems(t, "probe")   # -> []
```

Smaller than R2-F1 and in the same family: the guard reads one token out of a field whose human-readable content says something else. Recorded for completeness.

**Failure class:** `implementation`.

---

## What I could not break

Stated plainly, because these are results too, and because the repairs under review are substantial.

- **F1's correction is true, not vaguer.** I verified the capability myself as the same agent type rather than taking any document's word for it. `[측정]` At `297fbee`, working tree clean before and after: `printf 'r2-write-probe\n' > docs/agent-workflow/R2-WRITE-PROBE.txt` created a 15-byte tracked-directory file (removed with `command rm`, absence confirmed); then a Python one-liner through `Bash` rewrote `ACCEPTED_STATUS` in `tests/environment/test_agent_packet_record.py`, `git status --short` showed `M`, `git diff --stat` showed `1 file changed, 1 insertion(+), 1 deletion(-)`, and `git checkout --` restored it to clean. The fact stands. Every one of F1's six sites now says something true about it: the role table calls it "a mitigation, **not** a barrier; `Bash` remains"; `README.md:63–73` states the denial, states that it resolves, states that every tool includes `Bash`, and cites the measurement; `ATTACKER.md:33` opens "**It is not a write barrier**"; `PROMPTS.md:38` the same; `project-state.md:175` reduced "two parts enforced" to one and says what the earlier line claimed; `DP-013:52` says "**No** role prohibition in this model is structural"; `p0-execution-plan.md:190` corrects the pre-existing row it inherited. `297fbee`'s message declines to claim a fix and names the real one — reviewing from a worktree or a copy — as a change to how reviews are run and not this packet's to make. That is the honest disposition, and I looked for a document that still leans on the old reading and found two mild ones (R2-F6, R2-F7) and nothing load-bearing.
- **F2's containment holds against everything I threw at it.** Absolute paths, a ten-level `..` escape, `//etc/hosts`, `/etc/../etc/hosts`, backslash separators, `%2e%2e` percent-encoding, `~`, a query string, an empty and a whitespace-only target, and a macOS case-variant of the repository directory (`.../lymeric/CosmAI-...`, which the case-insensitive filesystem would open and `is_relative_to` correctly refuses) — all rejected, each with a message naming the reason.
- **Symlinks, which the repair description does not mention, are covered by construction.** `Path.resolve()` follows them, and containment is tested on the resolved path, so a symlink inside the repository pointing out is caught. `[측정]` Demonstrated on an in-repository symlink that already exists rather than one I created: `.venv/bin/python` is a symlink to `/Users/shk/.local/share/uv/python/…/bin/python3.13`, and `[r](../../../.venv/bin/python)` is rejected as "not a repository path". In an isolated `$TMPDIR` tree I also built a symlink to `/etc/hosts` (rejected, "not a repository path"), a dangling symlink to `/nonexistent/nope.md` (rejected, "not a repository path"), a two-node symlink **loop** (rejected, "does not exist" — `resolve()` does not raise on a loop in non-strict mode), and a symlink to `../../../AGENTS.md` staying inside the tree (correctly accepted).
- **`is_relative_to` is applied to a fully resolved path, and `REPO_ROOT` is resolved too.** `REPO_ROOT = Path(__file__).resolve().parents[2]`, so there is no symlinked-checkout mismatch. `[측정]` I confirmed this incidentally: in `$TMPDIR`, `REPO_ROOT` came out as `/private/tmp/claude-501/…`, correctly resolving macOS's `/tmp` → `/private/tmp` symlink on both sides of the comparison.
- **The order of the three checks is right.** Containment is tested before existence, so an escape is reported as an escape rather than being masked by a missing file. `297fbee`'s message claims this and it is what the code does.
- **F2's own end-to-end scenario is genuinely closed.** The forged `TASK-002` linking `/etc/hosts` now fails the real directory scan by name, where against `9707c8e` it was `15 passed`. I ran it rather than trusting the commit message.
- **Criterion 7's weakened-validator clause reproduces exactly.** `20 failed, 9 passed` under `return []` — the 19 `REJECTED_CASES` plus the non-UTF-8 scan test, which also routes through `packet_problems`. Every rejection case goes red, which is what the criterion now says (the F11 ambiguity about "positive controls" is gone).
- **F12's original defect is repaired.** Every scratch tree I built omitted `docs/agent-workflow/README.md`; the guard gives `29 passed` regardless.
- **F13's two named cases are repaired and each has its own test.** `test_scanning_reports_a_non_utf8_file_and_keeps_going` names the file and confirms the later packet was still read; `test_scanning_reports_a_subdirectory_instead_of_silently_skipping_it` makes a subdirectory a reported defect rather than a silent skip or a silent recursion.
- **`_unquoted` cannot be partially stripped into an accidental match.** Three regression cases hold it, and I could not construct a value that survives a partial strip into a `STATUS_VALUES` or `PASS` match.
- **The criteria rewrite is a real improvement, not a loosening.** Criterion 6 went from "a threshold exists" — satisfiable by any prose — to four separately checkable properties, three of which the previous revision would have failed. Criterion 4 went from an unsatisfiable universal to a bounded one with the exclusion class named and required to be nameable, which is what F10 asked for. Criterion 7 went from "positive controls" to an enumerated list of seven target rejections plus a stated weakening procedure. I looked for a criterion that had been widened to fit the work and did not find one.
- **`OQ-011`'s two rules are marked proposed where they live, not only in the Open Question.** `project-memory.md:39–43` and `branching.md:91–95` each carry a `[가설]` **Proposed, not accepted** block above the rule, with a link to `OQ-011` and a statement of the recommendation. `branching.md`'s exception also *lost* its `[확인 사실]` label in the process. `OQ-011` is registered in `project-state.md:204` and in `DP-013`'s `Related Open Questions`. I looked for a third consequential rule in `git diff 933bbae 297fbee` that slipped in without the same treatment; the closest candidates are the two threshold-bounding rules, which are recorded in R2-F3 and R2-F9 rather than as a missing `[가설]` — they refine an already-accepted threshold rather than reaching new territory the way R1 and R2 do.
- **F7's repair is thorough.** All three stale statements in `docs/p0-execution-plan.md` are corrected with the correction visible (`[확인 사실]` markers naming what the earlier revision said), the "reconciling current contracts" instruction is answered inside the row, and the two delivery sentences are kept with a stated reason rather than deleted — which is the right call, since they are still true.
- **Citation spot-checks held.** The 351-line figure, the 3/3/3/1 counts, the three timestamps, `b437013 parents=6d1e965 b702c79`, the single `DP-006`, and the `EXP-003` source of the F6 quote all check out. The one inaccurate citation in this branch is the one R2-F2 reports, and it is the same one REVIEW-TASK-001 found.
- **Allowed-file compliance is clean.** Every path in `git diff --name-only 9707c8e 297fbee` falls inside `TASK-001`'s allowed list, including the two added during rework (`docs/p0-execution-plan.md`, `docs/open-questions/OQ-011-…`), and the addition is disclosed at `TASK-001:74–77` with the reason. Nothing under `experiments/`, `contracts/`, or `.claude/` was touched.

## Scope and decision-boundary review

- **Allowed-file compliance:** clean. 25 paths changed across `933bbae` and `297fbee`, all inside the packet's allowed list; no forbidden path touched. The two files added to the list during rework are the two REVIEW-TASK-001 said were missing.
- **Accepted-decision compliance:** one problem. `README.md:119–122` overrides `DP-013` D6, an `ACCEPTED_FOR_POC` clause `AGENTS.md:35` requires be treated as a constraint, without amending it (R2-F3). Otherwise: `DP-005`/`DP-011` phase boundaries respected, `DP-007`'s deliberate preservation of the old name in history respected, `DP-006` untouched, no contract under `contracts/` changed. `DP-TEMPLATE.md`'s rule about `ACCEPTED_FOR_POC` is now satisfied by `DP-013`'s scoped `Owner confirmation` (F9 repaired).
- **Unanswered consequential direction:** `TASK-001:45` still records "Owner decisions required: `none`". Two of the three items REVIEW-TASK-001 raised against that are now `OQ-011` R1 and R2, and both rules are marked proposed in place — a genuine repair. The third, `DP-013`'s seven operating rules being in force on a confirmation that does not cover them, is now disclosed in the `Owner confirmation` field itself rather than resolved. `[추론]` The `none` on line 45 is now inconsistent with the packet's own `Authority and dependencies` block, which links `OQ-011` nowhere; `OQ-011` is reachable from `DP-013` and `project-state.md` but not from the packet that produced it.
- **Prohibited material exposure:** none found. The diff is documentation plus one test file. No credential, token, cookie, transcript, dataset, or private evaluation material appears. My probes wrote only to `$TMPDIR`, apart from the two named, restored writes in "What I could not break". No symlink was created inside the repository working tree.

## Conclusion

**`FAIL`**, on one blocking finding and one major one, with criterion 9 unmet.

The repairs are real. I want that stated first and without hedging, because the bulk of this report is what held. F2 was the finding most likely to have been closed by rewording, and it was not: I attacked the new containment check with symlinks, dangling symlinks, symlink loops, absolute paths, `..` escapes, `//`-prefixes, backslashes, percent-encoding, `~`, query strings, empty targets, and a macOS case-variant, ran the report's own forged packet end to end through the real guard file, and the check held every time. F1 was the finding most likely to have been closed by vagueness, and it was not: all six sites say something true, the underlying capability is recorded as unchanged, and `297fbee` names the fix it is *not* making rather than implying one. The criteria rewrite made criteria 4, 6, and 7 falsifiable without widening them to fit the work. Thirteen of fifteen findings are properly disposed of.

Two are not, and the pattern in both is the same one criterion 9 was written to catch — a finding worked through in the document where it was filed rather than in every location it named.

**R2-F1** is the blocking one. F3's repair closes the three bypasses the review demonstrated and leaves the finding's own title reproducible: an earlier line still silently overrides the `## Review` block, if the `## Review` block is indented two spaces. I built a forged `TASK-003` whose review section says `Attack report: none. No independent review was run` and `Result: FAIL`, with `PASS` and a resolvable link in a "machine-readable summary" below it, and the real directory scan passed green. The duplicate rule cannot fire because there is no duplicate — `^-` is anchored at column 0 and an indented list item is not a match. The repair's reasoning for refusing to parse heading boundaries is sound; what is missing is any record that this is what refusing costs. This matters more than its shape because the packet is `REWORK` on the argument that `ACCEPTED` over a `FAIL` report would be the acceptance control failing in its first use — and this is exactly that record, passing.

**R2-F2** is the criterion 9 trigger. F6 named three locations. `DP-013` was corrected — reattributed to `EXP-003`, relabelled `[추론]`, "avoid" restored, with the earlier error recorded. `docs/agent-workflow/README.md:169–171` is untouched: the author's own inference about the author's own error is still introduced as "the review's first blocking finding", and "designed to prevent" still appears inside quotation marks around a string that exists in exactly one place in this repository — that line. So the model's own README still argues for the planner/worker split by attributing the argument to an independent reviewer who did not make it. Criterion 9 says a finding must be repaired or recorded with the reason it was not. This one is presented as closed while the sentence it is about stands, in the more widely read of the two documents.

The moderate findings are narrower and none of them is a false claim. **R2-F3** is the F5 repair being right and leaving two documents saying the opposite, one of them an accepted Decision Packet clause the review had already cited by name. **R2-F4** is F13's failure class surviving in code the F2 repair wrote — `Path.resolve()` raising on a poison link target aborts the scan before later packets are read, which is F13's original reproduction with a different exception type.

`[추론]` What all four have in common is worth naming, because it is the same shape at a different altitude from F1. The repairs were organised by *defect* — here is F2, here is the code that fixes it — and the residue is at the seams: the location a finding named but was not filed under, the accepted packet a convention now overrides, the exception class a guard's new code introduces after the guard's old code was hardened against a sibling. That is not carelessness either; it is what happens when the session that reads the findings is the session that closes them, which is the condition `TASK-001` already admits twice and which a second independent review is the stated remedy for. This is that review, and it found two.

The path to `PASS` is short. Make `_field_values` match a list item at any indentation and with any of `-`, `*`, `+` — which strengthens the duplicate rule rather than replacing it, and turns R2-F1 into a duplicate rejection. Wrap `_report_target_problem`'s `resolve()` in `except (OSError, ValueError)` and report it as a defect. Correct `README.md:169–171` the way `DP-013:43–50` was corrected, or replace the quote with `PLANNER.md`'s accurate paraphrase. Amend `DP-013` D6 and `ORCHESTRATOR.md:36` to match `README.md:119–122`, and add the two bounding rules to §"What changed from the proposal". Point the `../reviews` case at a path the module already resolves and fix the docstring's count.

## Required follow-up

- **New or revised packet:** yes. A second rework of `TASK-001`, or `TASK-002`, covering R2-F1, R2-F2, R2-F3, and R2-F4. R2-F1 and R2-F4 belong in one change — both are the guard, both are a repair's blind spot, and separating them invites fixing the field scoping while a link target can still abort the scan. `[추론]` Its acceptance criteria should be written by a session that will not implement them. `TASK-001`'s own admission is the argument, and criteria 4, 6, and 7 having needed rewriting once is the evidence.
- **Open Question or Decision Packet update:** `DP-013` needs three edits — D6 reconciled with `README.md:119–122` or `README.md` reconciled with D6 (R2-F3); the two threshold-bounding rules added to §"What changed from the proposal"; item 14's `[확인 사실]` description updated to match the `[가설]` relabelling `297fbee` performed (R2-F9). `ORCHESTRATOR.md:36` needs the same reconciliation as D6. No new Open Question is required by this review: `OQ-011` correctly holds the two rules that needed one, and R2-F3's conflict is a reconciliation rather than an owner question — unless the owner's answer is that the orchestrator's discretion should win, in which case it is.
- **Project State or contract update:** none. `project-state.md:175` is accurate as it stands and `OQ-011` is registered at line 204. No contract under `contracts/` is affected — which `docs/p0-execution-plan.md:191` now says explicitly, answering the contract-reconciliation instruction REVIEW-TASK-001 F7 found unaddressed.

## Attacks I did not perform

A `PASS` would have been limited to what I actually tried; so is this `FAIL`. What I did not do:

- **I did not run the full test suite.** `AGENTS.md` and my own constraints reserve it for a task that holds the database. Criterion 8 names `tests/environment/` specifically, which I ran (`62 passed`). I have no evidence about the database-backed suites and make no claim about them.
- **I made no network call.** Every GitHub-side statement is unverified: whether `origin` matches these refs, the duplicate remote branch `docs/p0-execution-plan.md:191` still names, the branch-protection settings `docs/branching.md` records as `[확인 사실]`, and PR state. `BLOCKED` on all of it. Nothing in `TASK-001`'s nine criteria depends on it.
- **I did not verify that the 2026-08-18 reviewer worked from a copy**, or had no write access. That session is not reproducible from this checkout and its self-description is the only evidence. R2-F6 reports the label inconsistency, not a refutation. **Unverified, not disputed.**
- **I did not test whether `effort`, `reasoningEffort`, and `reasoning_effort` are silently ignored in agent frontmatter, nor whether path-scoped `permissions` take effect.** `PLANNER.md` and `DP-013` rest on `fcf4b8a` for the first and explicitly record the second as untested. `.claude/` is forbidden material for this packet; I read `.claude/agents/adversarial-reviewer.md` and wrote nothing there.
- **I did not attempt to detect a forged attacker session.** The model states plainly that nothing would, and R2-F1 shows what a forged record looks like when the one guard is asked to catch it — which is as close as this review gets to testing that claim.
- **I did not attack the guard's behaviour on a filesystem other than case-insensitive APFS.** The case-variant probe is a macOS result; a case-sensitive filesystem would reject the same input for a different reason, and I did not confirm that.
- **I did not evaluate whether `main` should take this work.** `TASK-001`, `DP-013` §"Remaining uncertainty", and `docs/branching.md` all say that is a separate acceptance. Out of scope here.
- **I did not review `6d1e965`'s P0-B product and scraper-service content, `DP-011`'s delivery boundary, or `DP-012`.** Outside this packet; I confirmed only that the citations point at real accepted packets.
- **I did not re-derive REVIEW-TASK-001's fifteen findings from scratch.** I took each as stated and asked only whether it is repaired. If one of them was itself wrong, this review would not catch it — the exception being F6, whose true source I re-verified against `EXP-003` because R2-F2 depends on it, and F1, whose capability I reproduced because I am the agent type it is about.

## Where this file belongs

Under `docs/agent-workflow/reviews/`, as `REVIEW-TASK-001-R2.md`, per `reviews/README.md`: this work still has no experiment record. Link it from `TASK-001` §Review beside `REVIEW-TASK-001`. `[추론]` Note that adding a second `- Attack report:` line to `TASK-001` would trip the guard's new duplicate rule — one line carrying two links, or one line naming the latest report, is what the guard now permits.

- Result: `FAIL`
