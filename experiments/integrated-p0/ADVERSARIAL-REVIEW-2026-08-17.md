# Adversarial review of the P0-A Completion Gate

- Reviewed document: [PLATFORM-CORE-GATE-2026-08-17.md](PLATFORM-CORE-GATE-2026-08-17.md), first draft at commit `f4b7ae7`
- Review date: 2026-08-17
- Brief: refute every `PASS` claim. Lean toward refutation when uncertain. Do not accept a claim because it looks reasonable.
- Method: execution, not reading — including deliberately sabotaging controls to check they fire, planting boundary violations, and building a throwaway worktree at the revision the gate named.

## Why this exists

The implementer and the gate author are the same party, so the gate had no independent axis. This review is that axis. It is committed beside the gate rather than summarised into it, because a review whose findings survive only as the conclusions its subject chose to adopt is not evidence of anything.

## Outcome

The review found **three blocking defects, eleven material findings, and five minor ones.** Every blocking defect was in the record rather than in the platform. Its recommendation was `CONDITIONAL GO` with three conditions before signature; the gate now records `CONDITIONAL GO` with criterion 6 as its condition, the other two having been discharged.

Its closing judgement, quoted because it is the part a future reader most needs:

> **No — not as written, though my objections are almost entirely about the record rather than the platform.** The engineering underneath is unusually well controlled: the two load-bearing controls (the OPS-001 database seal, the SEC-004 ordinary-marker detection) both survived deliberate sabotage, the concurrency suite did not flake in 10 full repetitions, the deferred-domain boundary held under an adversarial sweep that went well past the guard's vocabulary, and EXP-001 is in several places *more* honest than the gate it supports. […] But the question a signature answers is "is this record something a reviewer can independently verify", and right now it is not.

## Blocking findings, and what was done

### F1 — No single revision satisfied the gate's own re-run block

At the reviewed revision `uv run mypy .` reported an error the gate commit itself had introduced (`payload["control"]` is typed `object`), so the gate's "clean, strict" claim was false at the revision it named. The test count came from a different tree again: 509 at `HEAD`, 508 at `60807cb`.

**Resolved.** The error is fixed, every command in the re-run block was re-run at one revision, and the block records `507 passed, 2 skipped`.

### F2 — The evidence directory named a revision that could not have produced its contents

`git ls-tree 60807cb -- …/evidence/` listed only `2026-08-17-5b26d47`, and the tests that write the artifacts did not exist at `60807cb`. This was **the second time in two commits** the directory had been misnamed — the first correction had been committed with a message explaining why the old name misled. The review found the structural cause: `evidence_directory()` picked `sorted(...)[-1]`, bound to nothing, so a future short sha sorting lower would have written into the wrong directory silently.

**Resolved, by removing the mechanism rather than the symptom.** A test that writes during a run cannot name the revision that produced its output, because the name is only knowable afterwards. Capture is now opt-in (`--capture-evidence=DIR`), the directory is named after the run, and the artifacts land in a commit that changes no code — so the claim is checkable with `git diff` instead of asserted.

### F3 — Three of four recorded hashes failed the directory's own verification instruction

The `README.md` said "Verify with `shasum -a 256 -c`"; doing so reported three `FAILED`. The cause was the same design: the scenarios rewrote the artifacts on every run. A reviewer following the instruction concluded the evidence had been tampered with.

**Resolved.** An ordinary run no longer writes there, and the hashes verify.

## Material findings, and their disposition

| # | Finding | Disposition |
|---|---|---|
| F4 | `ENVIRONMENT.md` recorded `472 passed` and 45 source files — an S3-era measurement never re-measured, contradicting the gate a reviewer had just been pointed away from | Re-measured at the reviewed revision, with the superseded values named as superseded |
| F5 | `ENVIRONMENT.md` said both that the artifacts are written by the tests **and** that they came from an uncommitted throwaway collector | The second is gone; the condition it described is gone |
| F6 | Criterion 1's "so all four contended" was an unlabelled inference: the distribution is printed, not asserted and not captured, and "near-uniform around 50" misrepresents EXP-001's own `33`–`57` range | Cell rewritten as `[추론]`, with the real range and the fact that no assertion enforces contention |
| F7 | Criterion 6's log channel has no positive detection control — the platform never writes a payload into an event, so searching a log asserts what was not attempted | Disclosed in the cell, separately from the screenshot gap |
| F8 | Criterion 6 was `PASS` on a criterion that names screenshots, with the gate inviting the reviewer to downgrade it — declining a judgement the gate exists to make | Re-judged `CONDITIONAL`; the gate now recommends `CONDITIONAL GO` |
| F9 | Criterion 9's provenance was circular — the gate cited EXP-001, EXP-001 cited the gate, and neither was checked against DP-005 §Excluded, which named six missing behaviors | Reconciled against DP-005 item by item, including the one that bounds P0-A's own `OPS`/`SEC` claims |
| F10 | The guard covers identifiers, not string literals: `sql.Identifier("observation")` and a `"raw_response"` API-key constant passed, while one real identifier failed immediately | Gate's enforcement claim narrowed; recorded as limitation 8 |
| F11 | The gate dropped EXP-001's limitation that `tests/conftest.py` imports experiment code, so the root test session stops guarding when P0 is disposed of — the one limitation touching disposability | Added as limitation 7 |
| F12 | Two scenario `Result` counts were stale, and the gate silently disagreed with one | Resolved by the capture redesign: the capture tests now skip, so `ops_003` is 8 and `sec_004` is 59 again, matching both documents |
| F13 | `OPS-003` — the correlation evidence, a named charter requirement — appeared in neither criteria table, leaving a DP-005 bullet unlinked | Row added |
| F14 | The `JOB-008` safe-retry conflict was resolved by editing the scenario in place, with no Decision Packet, while the test code still says one is required | **Open.** Recorded in the gate's failure classification as an open action rather than closed |
| F15 | Several scenario bullets are unasserted or asserted a layer below what the scenario names — `JOB-003` has no metrics assertion; `JOB-004`'s "readable from the API" is checked through the store; `JOB-008` case A's "operator safe retry" calls `request_retry` directly; `SEC-002`'s "routable host address" is parametrised with two wildcards and two names | **Open.** The load-bearing behavior is tested in each case, so no criterion changes; the Evidence column implies fuller case-table coverage than exists |

Minor findings F16–F20 (a miscount of the not-claimed list, evidence-label usage that mixes roles in one sentence, a stale "not here yet" entry, a version recorded as a pointer rather than a number, and orphaned bytecode) are corrected where they were text and recorded here where they were not.

## What the review attacked and could not break

This half matters as much as the findings, because it is the part that says which claims are load-bearing.

- **`OPS-001`'s database seal is real.** The reviewer confirmed `platform_core/db/connection.py` calls `psycopg.connect`, so the patched name is the actual door; confirmed all fourteen cases take the sealed fixture rather than the raw probe; broke `_refuse_connection` to return instead of raise and watched the control test fail with `DID NOT RAISE`; and looked for a bypass through the live connection held open in the fixture generator, finding it genuinely unreachable.
- **`SEC-004`'s detection control is real in both directions.** Forcing over-redaction by adding `note` to the redacted key set produced seven failures, including the control itself.
- **No flakiness.** Eight consecutive runs of the concurrency and correlation set, two full-suite runs under `-n 4`, three further `JOB-007` case-A batches. Zero failures, zero reruns. The gate's `-n 4` timing reproduced.
- **Every per-scenario count the gate cites was correct** at the revision measured.
- **The deferred-domain boundary held under a sweep well past the guard's vocabulary** — the reviewer searched the dashboard's TypeScript, every API response key and query parameter as string literals, the SQL, and synonyms the guard does not name (`dataset`, `feed`, `harvest`, `crawl`, `provenance`, `upstream`, `vendor`, `fetcher`, `adapter`), and checked that no provider protocol exists under another name via `Protocol`/`ABC`/`abstractmethod`. No substantiated violation.
- **Criterion 6's metrics coverage is better than the gate claimed** — two assertions plus a structural restriction on labels.
- **"Maintained from the first commit" is true** — `git show 4b1753c` carries all nine inventory items.
- **The sandbox admission is honest** — `.claude/settings.json` still carries `allowedDomains: ["*"]`, exactly as disclosed.

## Tree state after review

`git status --short` empty; evidence hashes byte-identical to the pre-review baseline; no worktrees, no stashes, no residue. Every experimental mutation was reverted and the revert confirmed.
