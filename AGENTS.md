# Cosmai agent instructions

## Mission

Build evidence that allows the team to choose the architecture. Do not treat P0 as the production foundation.

## Where you are working

- Read `docs/areas/README.md` first. It names the five development areas, the one
  dependency rule that spans them, and which document governs each.
- Work inside one area at a time. A change that spans areas is usually two changes, and
  occasionally a sign that the boundary is wrong — which is evidence worth recording
  rather than routing around.
- Before writing an add-on, read `docs/conventions/addon-authoring.md`. An add-on
  imports `addon_api` and nothing else in this project; `tests/environment/test_addon_layer_direction.py`
  enforces that and will name the violation.

## Branch and merge

- Work on `<area>/<what>`, branched from `dev`. `docs/branching.md` has the whole rule.
- **Every merge is a merge commit: `git merge --no-ff`.** Never squash, never rebase a
  shared branch. Commit messages in this repository are part of the decision record, and
  squashing deletes them.
- `main` moves only at accepted gates and Decision Packets. Merges into it go through a
  pull request — a convention, not an enforced control; `docs/branching.md` says why.
- Commit or push only when asked.

## Decision boundary

- Read `docs/project-state.md` before making changes.
- Read `docs/p0-charter.md` before starting, scoping, or changing P0 implementation, instrumentation, or exit criteria.
- Read `docs/p0-execution-plan.md` before starting or changing P0-A or P0-B work.
- Read `docs/conventions/project-memory.md` before recording status, decisions, evidence, or handoff information.
- When working as an orchestrator, planner, worker, or attacker, read `docs/agent-workflow/README.md`, the assigned role document, and the assigned task packet before acting.
- Before handling external input or configuring a source, read `docs/conventions/data-handling.md` and `docs/conventions/p0-security.md`.
- Treat items marked `ACCEPTED_FOR_POC` or `CONTRACTED` as constraints.
- Do not silently resolve a consequential ambiguity. Create or update an Open Question, present the material options and tradeoffs to the project owner, and wait for an explicit answer before implementation. Evidence collection that was already authorized may continue; choosing the direction may not.
- Product goals, phase or scope, source and rights policy, model strategy, canonical schema, architecture boundaries, security or privacy policy, evaluation criteria, material budget, and release criteria are consequential directions.
- Record the owner's answer in a Decision Packet and update `docs/project-state.md` before treating it as a constraint. A conversation or model memory is not an accepted decision record.
- Local names, helper structure, and equivalent internal algorithms remain implementation choices.
- A failed test may indicate an implementation, specification, assumption, evaluation, or goal failure. Classify it before patching repeatedly.

## Agent operating model

- The orchestrator owns user questions, role assignment, decision-boundary enforcement, and final acceptance.
- The planner produces one bounded task packet and one-line execution prompts. The planner does not implement product code.
- The worker changes only files allowed by one task packet and records the requested verification. The worker does not broaden scope.
- The attacker independently tries to falsify the result and records reproducible `PASS`, `FAIL`, or `BLOCKED` evidence. The attacker does not repair the implementation being reviewed.
- Work flows `owner decision → planner packet → worker result → attacker review → orchestrator acceptance or rework`.
- Role contracts, templates, and handoff rules are defined in `docs/agent-workflow/`.
- Spawn the subagent type where one exists — `adversarial-reviewer` for the attacker, `mechanical` or `addon-author` for the worker. A constraint in `.claude/agents/` frontmatter is loaded before the role can forget it; a pasted prompt is not.
- The full flow is required by threshold, not by default. `docs/agent-workflow/README.md` names the work that needs a packet and an independent report, and the work that does not.
- Return `BLOCKED` rather than a qualified pass when you cannot verify what you were asked to verify. Missing access and missing evidence are not a pass.
- `docs/agent-workflow/README.md` records which of these rules the harness enforces and which are convention. Do not describe a convention as a control.

## P0 boundary

- Put disposable integrated implementation under `experiments/integrated-p0/`.
- Put source-specific probes under `experiments/source-probes/`.
- Follow `DP-005`: P0-A implements and verifies only source- and normalization-independent platform behavior.
- During P0-A, do not explore or select REST or dataset sources and do not create acquisition, Raw, snapshot, or normalization contracts, ports, fixtures, test doubles, persistence, UI behavior, or implementations.
- P0-A synthetic handlers may test generic execution and failure behavior, but they must not imitate a collector, dataset importer, Raw payload, snapshot producer, or normalizer.
- Start all source exploration, source selection, acquisition, Raw, snapshot, and normalization work in P0-B only after the P0-A Completion Gate is accepted and linked from the integrated experiment record.
- Do not create long-lived application code under `apps/` until the P0-B P1 Entry Gate accepts `PoC Contract 0.1`, artifact disposition, and the P1 reconstruction plan.
- P0 code must not become a runtime or package dependency of P1.
- P0 may be direct and source-specific when that is the minimum way to test a hypothesis. Avoid abstractions that do not reduce a named uncertainty.

## Evidence and contracts

- Use the following evidence labels when a claim's role could be ambiguous:
  - `[확인 사실]`: 신뢰할 수 있는 출처나 직접 확인한 artifact로 독립적으로 검증할 수 있는 상태.
  - `[측정]`: 명시된 입력, 환경, 절차, 도구를 통해 이번 작업에서 얻은 관찰값.
  - `[추론]`: 확인 사실이나 측정으로부터 도출했지만 원자료에 직접 적혀 있지는 않은 해석.
  - `[가설]`: 아직 충분히 검증되지 않았으며 반증 조건과 실험이 필요한 주장.
  - `[결정]`: 증명된 사실이 아니라 특정 범위와 시점에서 채택하기로 한 선택.
- These labels identify a claim's role, not a confidence ranking. Split a sentence if it mixes roles.
- Read `docs/conventions/evidence-labels.md` for boundary cases, required metadata, and project examples.
- Record source URL/provider, capture time, license or usage basis, sample hash, environment, and relevant versions.
- Store unstable contracts only under `contracts/experimental/`.
- Promote a contract only through a Decision Packet and version it.
- In P0-B, preserve provenance and lossless Raw payloads; do not present normalized output as source truth.

## History documents

- `docs/history/` is curated background for humans and is not an active requirement or instruction source.
- Do not load all history by default. Read a history document only when a current decision needs its earlier rationale.
- If history conflicts with `docs/project-state.md`, an accepted Decision Packet, or a versioned contract, follow the active document.
- Do not create or store raw chat transcripts or session snapshots anywhere inside the repository working tree, whether tracked, untracked, or ignored.
- If raw conversation retention becomes necessary, define a separate private archive outside the repository before retaining it. No in-repository path is reserved or approved for local-only transcript storage.

## Data and secrets

- Never commit API keys, tokens, cookies, credentials, private datasets, or unredacted personal data.
- Keep secrets outside code, job payloads, Raw headers, fixtures, logs, and screenshots.
- In P0-B, persist only a `credential_ref`; resolve the credential at the worker boundary from an approved local secret source outside the repository working tree.
- Follow the `public`, `local`, and `private` data classes in `docs/conventions/data-handling.md`. Redistribution permission and agent-processing permission are separate decisions.
- Commit only small fixtures whose redistribution basis is recorded. Otherwise store hashes and retrieval instructions.
- Treat imported datasets as untrusted Raw input regardless of their claimed normalization level.
- In P0-B, operator input selects a registered `source_id`; it must not turn an arbitrary URL into an outbound request.

## Validation

- Every experiment must name its hypothesis, falsification condition, evidence, and exit condition.
- Start each experiment from `experiments/EXPERIMENT-TEMPLATE.md`; add experiment-specific fields without removing its required sections.
- Prefer replayable commands and deterministic fixtures.
- P0-A must exercise generic retries, duplicates, interruption, and parallel claims. P0-B adds partial acquisition, source, Raw, snapshot, and normalization failures.
- Dashboard observability is experimental instrumentation, not deferred visual polish.
