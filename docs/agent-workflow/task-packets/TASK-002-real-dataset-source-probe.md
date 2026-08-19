# TASK-002 — Profile a real dataset source and record whether it passes its hard checks

- Status: `READY`
- Phase: P0-B, B1 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `general-purpose`, model `opus`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

One `SRC-003` source capability profile that states, from measurement rather than from the
provider's marketing, whether **Open Beauty Facts** passes every hard check the execution
plan sets for a dataset — and, if it does not, whether the KHISS cosmetics-industry CSV
does.

`[확인 사실]` Why this is reopened: `p0-charter.md`'s first P0-B exit criterion is *"One
REST source and **one dataset** complete the end-to-end flow."* The REST half is real. The
dataset half is [`SRC-002`](../../../experiments/source-probes/SRC-002-local-jsonl.md), a
file this project writes for itself, recorded as a deliberate substitution. The gate cannot
read a self-authored file as a dataset source.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §4, §5 — the dataset half of hypothesis 3 is self-authored and says so
- Accepted decisions: [DP-022](../../decisions/DP-022-structural-fixtures.md) (how a capture becomes publishable evidence), [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md) (P0 closes against the charter)
- Contracts: [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §Provenance and security
- Open Questions: [OQ-001](../../open-questions/OQ-001-source-capability.md) — this is its open half
- Owner decisions required: `none` — the owner chose Open Beauty Facts first and KHISS second on 2026-08-20; selecting between them on the measured result is this packet's output, not a new direction
- Required evidence or environment: network access for the provider's own documentation and a bounded sample. No credential is needed by either candidate.

## Scope

### Included

- `experiments/source-probes/SRC-003-open-beauty-facts.md`, following the structure of
  [`SRC-001`](../../../experiments/source-probes/SRC-001-naver-api-hub.md).
- Every hard check the execution plan's B1 candidate table sets for this candidate: **ODbL
  obligations including what licensing the *output* carries**, Korean sunscreen and toner
  coverage, ingredient completeness, stable row identity, and manageable fixture extraction.
- A recorded `GO` or `NO-GO` **per check**, with the measurement behind it.
- If Open Beauty Facts is `NO-GO`: a second profile for the KHISS candidate under
  `SRC-004-…`, with the same treatment, and an explicit statement of which check OBF failed.
- The retrieval procedure and the digest of whatever sample was actually measured.

### Excluded

- Writing any add-on. The importer is a separate packet.
- Downloading or committing the full export. A bounded sample is what this measures.
- Choosing the source. This packet **measures**; the orchestrator and owner select.
- Any change under `experiments/integrated-p0/`.

### Allowed files

- `experiments/source-probes/SRC-003-open-beauty-facts.md`
- `experiments/source-probes/SRC-004-khiss-cosmetics-statistics.md` (only if OBF is `NO-GO`)
- `experiments/source-probes/SOURCE-SELECTION-MATRIX.md` — append rows only

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- anything under `experiments/integrated-p0/`, `contracts/`, `docs/decisions/`
- any dataset payload. Store hashes and retrieval instructions, per `AGENTS.md`.

## Acceptance criteria

1. Every hard check in the execution plan's B1 row for this candidate has a `GO` / `NO-GO`
   and a measurement, not a restatement of the provider's claim.
2. The ODbL finding states what the licence requires of **derived output**, not only of
   redistribution, and cites the licence text.
3. Korean sunscreen and toner coverage is a **count from a real sample**, with the query or
   filter that produced it written down so it can be re-run.
4. Row identity is tested against change, not asserted: two captures, or one capture and the
   provider's stated identity guarantee with its own citation.
5. No payload is committed. The profile carries provider, capture time, licence basis,
   sample digest, and a retrieval procedure — the shape
   [`evidence/naver-real-data/README.md`](../../../experiments/integrated-p0/evidence/naver-real-data/README.md) uses.
6. Every claim carries an evidence label per [`evidence-labels.md`](../../conventions/evidence-labels.md).
   A `[확인 사실]` that is really a `[추론]` is a defect.
7. `NO-GO` on any check is a legitimate and complete result. Do not soften a failed check to
   produce a usable source.

## Verification

```sh
# Every command in the profile's retrieval procedure must run as written.
# The sample digest must reproduce from the recorded procedure:
sha256sum <the sample file the profile names>

# Coverage counts must re-run from the recorded filter.
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- Stop and report if the licence position is genuinely ambiguous. An ambiguous rights basis
  is a `BLOCKED`, never a `GO` with a caveat.

## Worker handoff

- Changed files:
- Commands and results:
- Evidence locations:
- Limitations and remaining risks:
- Newly discovered questions or blockers:

## Review

- Attack report: not yet written
- Result: `BLOCKED`
- Orchestrator disposition: pending worker completion
