# REVIEW-GATE-M0 — Attack report

- Target: **M0 / P1 Entry Gate preparation**, branch `p1/entry-gate` at `f0e0e49`, range `dev..HEAD` (15 files, 1888 insertions, 3 deletions)
- Reviewed artifacts: [`P1-ENTRY-GATE-2026-08-21.md`](../../architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md), DP-029…DP-034, [`security-recommendations.md`](../../conventions/security-recommendations.md), [`roadmap-candidates.md`](../../roadmap-candidates.md), [`P1-RECONSTRUCTION-PLAN.md`](../../architecture-synthesis/P1-RECONSTRUCTION-PLAN.md), [`project-state.md`](../../project-state.md), the two forward-link edits, `DP-026`, `OQ-004`
- Attacker: subagent type `adversarial-reviewer`, no `Write`/`Edit`/`NotebookEdit`; one delegated sub-review of the charter annex, every finding of which was re-verified before adoption. Transcribed verbatim by the orchestrator; the attacker cannot write files.
- Date: 2026-08-21
- Result: **`FAIL`** — 6 blocking, 13 minor
- Disposition: every blocking finding was repaired inside M0 after this report; the repair commits and the re-attack report are linked from the gate record.

`[측정]` Environment: this checkout at `f0e0e49`, working tree clean over the reviewed paths (`git status --short -- docs contracts experiments tests` empty before the first probe and after the last). `.venv/bin/python`, Linux WSL2 6.18.33.2. No file inside the repository was created, modified, or deleted at any point by the attacker. No network call was made. The only writes were under `$TMPDIR`.

The prior this review started from is the project's own recorded one: *prose claiming a control no test verifies*. It is confirmed. Every blocking finding is a sentence that reads stronger than the artifact directly beneath it — a `PASS` over its own annex, a plan asserting a requirement satisfied that three sibling documents say is not, a redaction claim resting on a function that filters headers.

## Reproduced evidence

| Claim | Command or procedure | Observed result | Verdict |
|---|---|---|---|
| `tests/environment` passes, 81 tests | `.venv/bin/python -m pytest tests/environment -q` | `81 passed in 0.21s` | **verified** |
| Every relative link in every changed file resolves | resolved all 271 relative markdown targets across the 15 files in `git diff --name-only dev..HEAD` | 0 broken | **verified** |
| The gate's `PoC Contract 0.1` row is accurate | read `POC-CONTRACT-0.1.md` §4 (104–117), §5:137, §8:183–206, header:7,11 | `Related Decision Packet` list ends at DP-024; `Last updated: 2026-08-19T+09:00`; §5 still states "**Determinism is required.**"; §8 still states "Four operator actions… collect, seal, normalize, read"; §4 states no ordering or tie-break rule | **verified — the strongest row in the document** |
| Gate row 5's OQ-006 / `JOB-007` numbers | `B4-SCENARIO-COVERAGE.md:64-65`; `OQ-006:44-64`; grep for the named correlation test | "0 failures in 30 runs"; 1/3/1 under contention; F16 present, test exists at `test_job_failure_paths.py:231`; OQ-006:64 says verbatim "carried before the P1 Entry Gate" | **verified** |
| The 12 charter criteria are quoted, not paraphrased | diff of `p0-charter.md:135-146` against the annex Criterion column | byte-identical after stripping `- ` and the trailing period | **verified** |
| The two named staleness corrections are real | `architecture-synthesis-v0.1.md:356`; `B4-SCENARIO-COVERAGE.md:4,124`; `architecture-synthesis-v0.1.md:60-65` | all three literally true as stated | **verified** |
| Bare-filename evidence citations exist | `find . -name 'ADVERSARIAL-REVIEW-2026-08-20*'` | both cited reports exist; `F-B`/`F-D`/`F-F` present in SNAPSHOT-R2, `F2` in OBF-REAL-DATA | **verified** |
| Line-number citations resolve | `store.py:632`, `domain-view.tsx:133,147,227`, `0002_domain.sql:139-216` | all four land on what they claim | **verified** |
| OQ inventory matches `project-state.md` §6 | `grep -m1 '^- Status:'` over all 14 `OQ-*.md` | files read OPEN: 001, 003, 005, 006, 007, 008, **009**, 010, 013, 015. The OQ-009 divergence is disclosed twice by the gate (lines 48, 52). No OQ is dropped | **verified — handled honestly** |
| Gate isolation checks 1 and 3 | `P0-ARTIFACT-DISPOSITION.md:38-48` | no implementation row is `PROMOTE`; the ARCHIVE_REFERENCE_ONLY list matches item for item | **verified** |
| DP-034 D2's four invariants match `secret-setup.md` | `secret-setup.md:15-18` | paraphrase accurate; the interpretive step is flagged in D2's own text | **verified — honest** |

`[확인 사실]` The "all 48 links verified" claim named in the review brief **appears nowhere in the branch**; the gate record contains 39 relative links. The property was tested rather than the claim, and it holds at the path level. It does **not** hold at the section level — see F3 and F7.

## Findings

| # | Case | Failure class | Severity |
|---|---|---|---|
| F1 | The `PASS` row asserts all 12 criteria met, over an annex showing one partially met, one waived, one unmet | evaluation | **BLOCKING** |
| F2 | The plan this gate accepts states `SEC-006` **is satisfied**; the gate, DP-034 and `SR-005` all state it is not | specification | **BLOCKING** |
| F3 | One of the six unresolved blockers is silently dropped, and the section is cited to the wrong file | evaluation | **BLOCKING** |
| F4 | DP-033 D2 reverses the Raw-payload refusal by calling the payload "already-redacted"; nothing redacts a payload body | goal | **BLOCKING** |
| F5 | Gate row 9 credits `test_operator_loop.py` with "real normalized rows"; its docstring says the transport is a stub | evaluation | **BLOCKING** |
| F6 | DP-030 lands in no milestone; isolation check 2's claim is false for M3 and M7 | specification | **BLOCKING** |
| F7 | All nine spec-section citations in both registers point at nonexistent or unrelated sections | evaluation | MINOR |
| F8 | `SR-004` inverts the one sentence DP-023 wrote to prevent that misreading | evaluation | MINOR |
| F9 | DP-034's `[측정]` grep cannot match anything for any input | evaluation | MINOR |
| F10 | `RC-005`/`RC-006` present invented strings as `[확인 사실]` quotations | evaluation | MINOR |
| F11 | Gate row 8 "Met / None named" against a defect the register calls unfalsifiable, over an empty lineage | evaluation | MINOR |
| F12 | Row 10 cites a file with zero SEC tests, and drops three requirement-level gaps its source records | evaluation | MINOR |
| F13 | DP-032 claims to **close** an evidence gap it produces no evidence for, and adds a credential class with no recorded gap | specification | MINOR |
| F14 | "Reviewed P0 revision" and the proposed `p0-archive` tag name a P1-decision commit on an unmerged branch | evaluation | MINOR |
| F15 | DP-030 D1 attributes a rationale to `plan.md` that is not in it; `plan.md` is untracked and cited inconsistently | specification | MINOR |
| F16 | Row 6's Evidence column credits tests with an assertion they do not make | evaluation | MINOR |
| F17 | DP-033 D5's headline contradicts its own body and the spec | specification | MINOR |
| F18 | DP-034 cites "DP-018 D6" for a design that is DP-008 D6 | implementation | MINOR |
| F19 | The staleness sweep is incomplete and one uncorrected row is quoted as if current | evaluation | MINOR |

---

### F1 — BLOCKING. The `PASS` summary contradicts its own annex twenty lines below

**File**: `docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md:18`

**Claimed**: Status `PASS`; *"Every one of the 12 charter criteria is met, but four are met only with a limitation…"*

**Evidence shows**: the annex's own Status column (lines 35–46) reads: row 4 — `**Partially met.**`; row 10 — `**Met for SEC-001…004 as scenarios; SEC-006 waived, not passed.**`; row 12 — `**Pending this gate.**`, whose Limitation states *"Until the owner sets an Outcome in the Decision block below, **it remains unmet**"*. `docs/p0-charter.md:133` reads *"P0 may end only when all of the following are true."* Three of the twelve are not asserted true by the annex itself. The count "four" also matches nothing: the exact status `**Met, with a limitation.**` appears **3** times (rows 1, 5, 9); rows carrying any qualification total **7** (1, 4, 5, 7, 9, 10, 12).

`[추론]` This is the one row an owner reads first, and it is the only place in the document that flattens the annex into a single word. The annex is honest; its summary is not.

### F2 — BLOCKING. The accepted plan says `SEC-006` is satisfied; every sibling document says it is not

**File**: `docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md:57`

**Claimed**: *"**0.3** — `SEC-006` **is satisfied**, but not by narrowing the agent sandbox."*

**Evidence shows** three documents on this same branch stating the opposite, one of them the gate that accepts this plan: gate line 21 (*"DP-034 D3 **does not satisfy** `SEC-006`… the two are different claims and should not be conflated"*), gate annex row 10 (*"`SEC-006` **waived, not passed**"*), `DP-034:184` (claims only the Phase 0.3 second-branch clause), `security-recommendations.md:32` (`SR-005` unimplemented). The plan's own Phase 0 row (line 35) is two-branched; closing the row by the second branch closes the row; it does not satisfy `SEC-006`. Line 57 conflates them.

`[추론]` A P1 implementer reading the accepted plan concludes `SEC-006` is handled.

### F3 — BLOCKING. One of the six carried blockers is absent from the blocker inventory, and the section is cited to a file that does not contain it

**File**: `docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md:24`

**(a)** The row cites *"[`p0-charter.md`](../p0-charter.md) §Unresolved blockers carried to the P1 Entry Gate"* — `p0-charter.md` has no such section; it lives at `architecture-synthesis-v0.1.md:371`. The link resolves at path level, to the wrong document.

**(b)** Item 4 of the real section — *"Rate limiting, deep pagination, redirects, drift, and the `200`-with-an-error-body case — all **unobserved against a real source**"* — is carried **nowhere** in the gate: grep returns 0 for each of `rate limit`, `pagination`, `drift`, `error body`, `redirect`, `DNS`. Items 1, 2, 3, 5, 6 are each carried somewhere; item 4 alone is dropped. Independently recorded at `B4-SCENARIO-COVERAGE.md:35` and `P1-INHERITED-DEFECTS.md` §8.

`[추론]` The gate question asks whether P0-B can reconstruct P1 *"without silently carrying an unresolved blocker."* This is one, silently carried.

### F4 — BLOCKING. DP-033 D2 reverses a refusal by calling the payload "already-redacted". Nothing redacts a payload body

**File**: `docs/decisions/DP-033-p1-operator-surface.md:130-134` (Evidence) and `:145-155` (D2)

**Claimed**: *"`strip_protected_headers` removes them from `raw_envelope` before it is ever persisted. A Raw payload page therefore renders content that has already passed through that stripping step"*; D2: *"…only makes the **already-redacted**, already-persisted payload readable."*

**Evidence shows** the named function (`domain/outbound.py:698`) operates on headers and only headers; its single production call site (`domain/transport.py:269`) passes response headers. It never receives a body. The contract's other redaction control is key-name-first (`platform_core/obs/redaction.py:127`) — arbitrary external text in a payload body has no sensitive key to match; the module's own docstring says the operator-visible summary *"is expected to name a failure class, not to quote a payload"*. `raw_summary`'s docstring — quoted by DP-033 itself — states: *"A page of Raw bodies on an operator screen is **a page of unreviewed external text**"*. D2 rebuts the docstring's second clause and drops the first without answering it. DP-033's H2 falsification condition inherits the same narrowing (protected-header values would never be in a body).

`[추론]` `project-memory.md:62` — *"An overstated control is the defect this project produces most often."* This is that defect, in the packet that reverses a refusal originally written to prevent it. Repair needs a decision, not only an edit: a body-level control, or an explicit recorded statement that a Raw payload page shows unreviewed external text and that the local-operator boundary is the only control.

### F5 — BLOCKING. Row 9 credits a stub-transport test with "real normalized rows"

**File**: `docs/architecture-synthesis/P1-ENTRY-GATE-2026-08-21.md:43`

**Claimed**: Evidence *"`OPS-001`, `OPS-002`, `SEC-004` scenarios; `test_operator_loop.py` **over real normalized rows**."*

**Evidence shows** — `test_operator_loop.py:15-20`, module docstring: *"**The transport is a stub, and the credential is a fixture.** … **this one would pass against a source that does not exist**."* The rows are the run's own stub-produced responses. The "real normalized rows" observation is a separate, test-free line at `B4-SCENARIO-COVERAGE.md:101`.

`[추론]` The test's author wrote the exact sentence that falsifies the gate's citation, in the file the gate cites.

### F6 — BLOCKING. Normalization has no milestone, and isolation check 2's claim is false for two of seven rows

**Files**: `docs/architecture-synthesis/P1-RECONSTRUCTION-PLAN.md:75-81`; gate `:69`

**(a)** Isolation check 2 claims the M1–M7 table *"names a contract section or Decision Packet for each milestone"* — false for M3 (module names only) and M7 (neither). **(b)** Five of the six new packets land in a milestone row; **DP-030 lands in none.** **(c)** No milestone row contains a normalizer, while the spec requires three rebuilt (`spec:199-201`) and `DP-030:216` assigns its central contract requirement to *"M4's normalizer add-ons"*. M4's row enumerates *"five add-ons"* that are collectors plus one importer; its arithmetic is also internally inconsistent (five *or six*).

`[추론]` DP-030 D2 is the contract-level repair for the defect register's *"most consequential row"*. It has no milestone, no add-on, and no acceptance test. M4, read literally, builds five collectors and no normalizer.

---

### Minor findings (full detail preserved from the attack)

**F7** — Both registers' spec citations reused capability-map item numbers as spec section numbers: nine of nine wrong; two (`SR-003`→§2.6, `RC-001`→§5.3) resolve to real sections about unrelated subjects. The 능력 지도 half of each citation is correct; the added spec half cannot be followed. Correct targets: §2.1–§2.7 table rows.

**F8** — `security-recommendations.md:74` says "다섯 개의 결함이 하루 사이" under `[확인 사실]` attributed to DP-023; DP-023:94-96 wrote, precisely to prevent that misreading: five total, **four** in one day. Four sibling documents say it correctly.

**F9** — `DP-034:120`: the recorded command `grep -rln secret\|credential …` is inert (BRE literal `secret|credential`, matches nothing; exit 1 on the actual tree). The conclusion is independently true (`grep -rlnE` shows only a comment and no credential-accepting route), but the recorded absence-evidence command proves nothing.

**F10** — `roadmap-candidates.md:72-73,81-85`: three `[확인 사실]` quotations are invented — DP-030 D4 quoted in Korean including "(Task 9)" (source is English, contains neither), DP-012 and DP-031 D4 quoted in Korean with elision marks (sources are English; strings absent). `RC-001`, `RC-007`, `SR-005` quote correctly, so the register knows how.

**F11** — Gate row 8 "Met / None named": the cited "no UPDATE path" is the same property `P1-INHERITED-DEFECTS.md:78-79` (F3) records as making the coexistence assertion **unfalsifiable**, and the charter criterion's "same Raw lineage" half is exercised over an **empty** lineage (`test_normalized_results.py:57-66` — "An empty one is enough here").

**F12** — Gate row 10 cites `test_ops.py` (zero `test_sec_*` functions; the real SEC scenario tests live elsewhere; only the `test_dashboard.py::test_sec_004_*` citation is right), and drops `p0-security.md:124-127`'s record that requirement-ids `SEC-002/003/004` have **no acceptance scenario at all** — after the gate itself warns at line 23 that citing one numbering against the other "misreports coverage."

**F13** — `DP-032:8` claims to **close** DP-006 D2's recorded *evidence* gap while its own Reversibility says nothing is implemented and no server was reachable — a decision is not evidence; `project-state.md:198-200` repeats the claim. And D4's `COSMA_DB_*` family sits outside `secret-setup.md:55`'s `COSMA_SRC_*` naming rule with a pool-lifetime tension against invariant 2, with no invariant analysis, no Affected-contracts entry, and no forward link — the standard its sibling DP-034 applied one commit earlier.

**F14** — Gate header revision `9547f3b` and the proposed `p0-archive` tag point at a P1-decision commit on an unmerged branch. The P0 *tree* is identical (`git diff --stat dev 9547f3b -- experiments/ contracts/ tests/` empty) but the tag label would resolve to a tree containing the six packets whose acceptance the gate is deciding.

**F15** — `DP-030:120-123` attributes the LLM/ML rationale to *"the owner (`plan.md` §3.1)"*; `plan.md` §3.1 reads only "결정적 정규화: 불가능. 단지 정규화 당시의 메타데이터 정보로 보조하도록." — the rationale is the design draft's. The owner's actual word "불가능" contradicts P0's own measurement (deterministic normalization measured in strong form), and DP-030 never records the mismatch. Cross-cutting: `plan.md` is untracked and not gitignored; DP-033/034 disclose that, DP-030/031/032 do not; `roadmap-candidates.md:102` makes `plan.md` a required provenance field; the capability-map scratchpad file it points to no longer exists (content survives in spec §2).

**F16** — Gate row 6's Evidence credits `test_normalizer_capability.py` with "all leave Raw untouched"; the file asserts only on `normalized_result` and error summaries — zero assertions against `raw_item`/`raw_envelope`. `B4:74`: *"That is structural, not a test outcome."* The row's own Limitation column already carries the correction; the same error is upstream at `architecture-synthesis-v0.1.md:130-131` under a `[측정]` label.

**F17** — `DP-033:186-192` D5's headline (*"normalization does not [run on a schedule]"*) contradicts its own body and the spec (*"수동 시작 유지 + 선택적 스케줄"*); `project-state.md:196` follows the headline.

**F18** — `DP-034:196` cites "DP-018 D6" for the write-only-editing design that is **DP-008 D6** (DP-034 itself quotes it correctly at line 104).

**F19** — Gate claims exactly *"two document-staleness corrections"*; at least three more rows of `architecture-synthesis-v0.1.md` are stale by the same 2026-08-20 work (`:362` replay "unproved" vs `:149` "exercised and it discriminates"; `:276` "self-authored"; `:277` "evolution never exercised"), and gate line 19 misquotes Part 2's rule-baseline row (`:279` says "**Not tested.** No quality baseline was built" — itself stale, quoted as current).

## What the attack could not falsify

`[측정]` Attacked and held: the 81-test environment suite; path-level link resolution (271 targets, 0 broken); the verbatim charter criteria; the `PoC Contract 0.1` row (the branch's most rigorous claim — all four `[측정]` sub-claims check out); the OQ inventory and its honest OQ-009 disclosure; gate row 5's OQ-006/JOB-007 numbers; DP-034 D2's flagged interpretation; isolation checks 1 and 3 against the disposition register; every bare-filename and line-number citation in the six DPs; `RC-001`/`RC-007`/`SR-005` quotations; `SR-003`'s SQL line-range citation. DP-031's "0.1.0 is the owner's error" claim could not be falsified; the tension (plan.md:70's `0.1.0` sits in the yt-scrapper bullet; tubedepth's live version string is `0.1.0`) is recorded without filing.

## Named verification gaps

Per `AGENTS.md`, these are `BLOCKED`, not passes: (1) the live adapter targets — sandbox loopback isolation refuses both; DP-031's Known limitations disclose this; (2) `~/.config/cosmai/env` — sandbox-denied by policy; no claim depends on it; (3) the owner's 2026-08-21 session — six packets cite it; the spec records its answers; the attacker cannot go behind them; (4) test behaviour under mutation — F5, F11, F16 are from reading assertions; the break-the-implementation experiment those rows' evidence never records is exactly what was not run.

## Verdict

**`FAIL`.** Blocking: **F1, F2, F3, F4, F5, F6.**

`[추론]` The pattern across all six is one shape. The branch's analytical work is unusually strong — the `PoC Contract 0.1` row, the OQ-009 disclosure, DP-034 D2's invariant scoping and the annex's per-row limitations. The failures are all at the **compression seams**: a careful table summarised into one word (F1), a two-branch condition closed by one branch and reported as both (F2), an inventory compiled with one item fallen out (F3), a header-level control carried to a body-level exposure by the word "therefore" (F4), two sources fused into one citation (F5), a milestone table with one packet left off (F6).

Failure classification: **evaluation** F1, F3, F5; **specification** F2, F6; **goal** F4. None is an implementation failure — no code is on this branch.

P0-B work package to reopen: **none.** Every blocking finding is repairable inside M0. F4 additionally needs a decision: a body-level control for the data-browser screen, or an explicit recorded statement that a Raw payload page shows unreviewed external text and that the local-operator boundary is the only control.
