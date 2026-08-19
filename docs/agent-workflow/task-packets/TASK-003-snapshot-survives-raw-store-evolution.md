# TASK-003 — Prove, or refute, that a sealed snapshot survives Raw-store evolution

- Status: `READY`
- Phase: P0-B, B4 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`, model `opus`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

A migration that really changes the Raw store after a snapshot is sealed, and a scenario
that says whether the snapshot still replays the same normalizer input — with a control
proving the scenario would have failed had it not.

`[확인 사실]` `p0-charter.md`'s fifth Architecture Question is *"Does the sealed snapshot
protect reproducibility from Raw-store evolution?"* `project-state.md` §5 already records
the answer as half-measured: *"Tampering is detected and named. **Raw-store evolution was
never exercised** — no migration changed the Raw tables after a snapshot was sealed — so the
half the hypothesis is actually about has no evidence."* The gate cannot answer this
question from what exists.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §5, hypothesis 4
- Accepted decisions: [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md) D5 (what a snapshot selects), [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
- Contracts: [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §4 — a normalizer receives a sealed snapshot verified before it sees a byte
- Open Questions: [OQ-004](../../open-questions/OQ-004-snapshot-boundary.md)
- Owner decisions required: `none`
- Required evidence or environment: the local PostgreSQL cluster via `scripts/with-database.sh`

## Scope

### Included

- One migration under `experiments/integrated-p0/domain/migrations/` that makes a **real**
  change to a Raw table — a column added, a column widened, or a constraint changed — chosen
  so that a naive snapshot implementation would break and this one is claimed not to.
- A scenario test: seal a snapshot, apply the migration, then verify the snapshot still
  verifies **and** that reading it yields byte-identical normalizer input.
- **A control that fails.** The scenario must be shown to be capable of failing: a mutation,
  a deliberately broken variant, or a second assertion over a case where the property does
  not hold. State in the test what was observed failing and how.
- The migration must be idempotent, like its siblings — `test_migrations.py` already asserts
  that applying the shipped migration twice is safe.

### Excluded

- Any change to `addon_api`, `addon_host`, or the add-ons.
- Any change to how a snapshot is sealed, unless the scenario refutes the hypothesis — in
  which case **stop and report the refutation**, do not repair it.
- Anything under `docs/` except the worker handoff in this packet.

### Allowed files

- `experiments/integrated-p0/domain/migrations/0005_*.sql`
- `experiments/integrated-p0/tests/test_snapshot_survives_migration.py` (new)
- `experiments/integrated-p0/domain/store.py` — **only** if the scenario refutes the claim,
  and only after stopping and reporting

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- `docs/project-state.md`, `docs/architecture-synthesis/**`, `contracts/**` — a worker does
  not write the claim its own work is the evidence for

## Acceptance criteria

1. The migration changes a Raw table in a way a reader can see is not cosmetic. Say in the
   migration's own comment why this change is the one that tests the hypothesis.
2. Sealing happens **before** the migration and verification **after**. A test that migrates
   first proves nothing about evolution.
3. The scenario asserts both halves: the manifest still verifies, **and** the bytes a
   normalizer would read are identical to what was sealed. Verification alone is weaker than
   the hypothesis.
4. The control is real and its failure was **observed**, not asserted to be possible. Record
   the failure output in the test's docstring, as this repository's other scenarios do.
5. `test_migrations.py`'s idempotency guard passes for the new migration.
6. If the hypothesis is refuted, the packet result is a **refutation with evidence**, not a
   repair. That is a complete and valuable outcome.

## Verification

```sh
./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py \
  experiments/integrated-p0/tests/test_migrations.py

# Then the whole suite, which must not regress from 1282 passed / 14 skipped:
./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop and report if the hypothesis is refuted.** Do not change how snapshots are sealed
  in order to make the scenario pass.

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
