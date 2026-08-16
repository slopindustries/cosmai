# DP-001 — Disposable P0 and Clean P1 Reconstruction

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-16
- Owners: Project team
- Related Open Questions: all P0 architecture questions
- Affected contracts: future `PoC Contract 0.1`

## Decision question

Should the first integrated prototype become the continuously hardened product foundation, or should it be used as disposable architecture evidence before a clean reconstruction?

## Candidates

1. Build one prototype and incrementally harden it.
2. Run isolated disposable spikes, then immediately build a durable integrated prototype.
3. Build a disposable integrated P0, synthesize its evidence, then reconstruct P1.

## Evidence and reasoning

- `[확인 사실]` Actual REST providers and dataset characteristics have not yet been tested.
- `[확인 사실]` Final normalized semantics and the product decision contract remain open.
- `[추론]` Isolated probes alone may miss transaction, retry, coupling, snapshot, and operator-workflow failures that appear only after integration.
- `[추론]` Incrementally hardening the first integrated code would preserve accidental structures chosen before those failures are observed.

## Decision

`[결정]` Select Candidate 3.

P0 will be an integrated but explicitly disposable Architecture Discovery Prototype. Architecture Synthesis will promote evidence, fixtures, tests, and accepted versioned contracts—not P0 implementation modules. P1 will be reconstructed from `PoC Contract 0.1` and the promoted acceptance evidence.

## Rejected alternatives

- Candidate 1 assumes more architecture stability than the project currently has.
- Candidate 2 does not test enough cross-component behavior before the durable implementation begins.

## Tradeoffs and risks

- Benefit: exposes integrated failure behavior without binding P1 to accidental code structure.
- Cost: some functionality is implemented twice.
- Risk: P0 can become endless or be polished accidentally.
- Control: explicit Architecture Questions, default timebox, exit criteria, and no automatic code promotion.

## Remaining uncertainty

- Exact P0 component boundaries remain hypotheses.
- The amount of P0 code worth consulting during P1 review is not fixed, but it cannot become a runtime dependency.

## Required changes

- Keep P0 under `experiments/integrated-p0/`.
- Do not create P1 `apps/` until Architecture Synthesis accepts `PoC Contract 0.1`.
- Archive P0 in history after synthesis.
