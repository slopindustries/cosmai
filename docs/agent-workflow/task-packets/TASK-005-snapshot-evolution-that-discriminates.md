# TASK-005 — Make the snapshot evolution experiment discriminate, which TASK-003's did not

- Status: `READY`
- Phase: P0-B, B4 reopened for the P1 Entry Gate
- Planner: orchestrator session, 2026-08-20
- Worker: `mechanical`, model `opus`
- Attacker: `adversarial-reviewer`
- Orchestrator: this session
- Created: 2026-08-20
- Updated: 2026-08-20

## Objective

An evolution of the Raw store that **breaks the design a snapshot was chosen over**, and
leaves the sealed snapshot intact — so that passing the scenario means something a
re-query-at-read-time implementation could not also pass.

`[확인 사실]` [TASK-003](TASK-003-snapshot-survives-raw-store-evolution.md) is `REWORK`. Its
attack report,
[`ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md`](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-20-SNAPSHOT.md),
returned `FAIL` on three findings this packet closes. The hypothesis was **not** refuted;
the measurement of it was.

`[측정]` F2, the one that matters: the attacker replaced `READ_SNAPSHOT_ITEMS` with a
read-time re-query of `raw_item` — the queried design `0003_normalized_result.sql` names as
the alternative — and **every test of `TestASealedSnapshotSurvivesRawStoreEvolution` passed
anyway.** The reason is structural: `addon_api.results.SnapshotItem` carries exactly
`item_key`, `payload`, `content_type`, so an *added column* cannot reach a normalizer under
either design. The experiment measured an evolution no design is sensitive to.

## Authority and dependencies

- Project State: [`project-state.md`](../../project-state.md) §5, hypothesis 4
- Accepted decisions: [DP-019](../../decisions/DP-019-normalized-schema-0-1-and-results.md) D5, [DP-026](../../decisions/DP-026-p0-closure-scope-and-collector-topology.md)
- Contracts: [`PoC Contract 0.1`](../../../contracts/experimental/POC-CONTRACT-0.1.md) §4
- Open Questions: [OQ-004](../../open-questions/OQ-004-snapshot-boundary.md)
- Owner decisions required: `none` — the owner chose "rework into a discriminating experiment" on 2026-08-20
- Required evidence or environment: the local PostgreSQL cluster. **Connect with `psql -h "$COSMA_DB_HOST"`** — this machine also runs a system PostgreSQL on `/run/postgresql`, and an unqualified `psql` reaches that one and fails with `role "user1" does not exist`.

## Scope

### Included

- Keep `0005_raw_item_payload_digest.sql` and the existing scenario. They are correct as far
  as they go and the ordering held under independent attack. This packet **adds
  discrimination**, it does not start over.
- A second evolution that touches an axis a normalizer actually receives — `item_key`,
  `payload`, or `content_type` — or that removes Raw rows a snapshot named. Candidates the
  worker should weigh and choose between, recording why:
  - a migration that rewrites `raw_item.payload` for existing rows (a re-encoding, a
    normalization of stored bytes);
  - a migration or data change that **deletes** `raw_item` rows a sealed snapshot named;
  - a change to what `raw_item` rows exist for a source, so the queried design would return
    a different set.
- **The discrimination test itself.** Prove, as a permanent test, that the queried design
  fails where the sealed design passes. The attacker did this by hand by swapping
  `READ_SNAPSHOT_ITEMS`; make it a fixture-level alternative implementation the test can
  drive, so the discrimination is measured on every run rather than once by an attacker.
- **F1** — correct control 2's recorded output. Following its own docstring produces
  `3 failed, 6 passed`, not the recorded `2 failed, 7 passed`; the unrecorded third failure
  is `test_each_member_still_matches_the_digest_it_was_sealed_with`, forced by the digests
  the docstring itself prints. Record what the file actually produces.
- **F3** — make the physical-rewrite claim a measurement. `stored` → `virtual` leaves all
  nine tests green, and `VIRTUAL` is PostgreSQL 18's default, so the claim currently rests on
  one word nothing checks. Assert `relfilenode` moves, or drop the claim.

### Excluded

- Any change to how a snapshot is sealed or read. If the discriminating evolution **refutes**
  the hypothesis, stop and report the refutation. Do not repair `store.py` to make a test
  pass.
- F4 — that reversing member order in `addon_host/capabilities.py::_NormalizeRun.execute` is
  caught by nothing. Real, and outside this packet. It is recorded for the gate separately.
- `addon_api`, `addon_host`, the add-ons, `platform_core/`.

### Allowed files

- `experiments/integrated-p0/domain/migrations/0005_raw_item_payload_digest.sql`
- `experiments/integrated-p0/domain/migrations/0006_*.sql` (new, if the chosen evolution needs one)
- `experiments/integrated-p0/tests/test_snapshot_survives_migration.py`

### Forbidden files and material

- private evaluation inputs, answers, and scoring code
- credentials, cookies, private datasets, and raw conversations
- `docs/project-state.md`, `docs/architecture-synthesis/**`, `contracts/**`,
  `experiments/integrated-p0/domain/store.py`

## Acceptance criteria

1. **A permanent test shows the queried design failing where the sealed design passes.** An
   alternative read implementation is driven by the test itself. If both designs pass every
   evolution the suite exercises, the experiment still does not discriminate and this packet
   is not met.
2. The sealed snapshot still verifies and still replays byte-identical members across the
   new evolution — or the refutation is reported with evidence.
3. Control 2's docstring records the output the file actually produces, verified by running
   it. `[결정]` Evidence named for a revision that cannot have produced it is the defect
   class this repository has already recorded; a corrected record is worth more than a
   flattering one.
4. The `stored` claim is asserted against `pg_class.relfilenode`, or removed. A claim no test
   holds does not go to a gate.
5. The whole suite does not regress from **1291 passed, 14 skipped**.
6. State plainly what remains unmeasured. TASK-003's handoff did this well; keep that.

## Verification

```sh
./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider \
  experiments/integrated-p0/tests/test_snapshot_survives_migration.py

./scripts/with-database.sh .venv/bin/python -m pytest -q -p no:cacheprovider
```

## Stopping conditions

- Stop if an unanswered consequential direction affects the implementation.
- Stop if an accepted decision or contract conflicts with this packet.
- Stop if required permission, environment, or safe test data is unavailable.
- **Stop and report if no evolution this repository can legitimately perform discriminates
  between the two designs.** That is itself an answer to the charter's fifth Architecture
  Question, and a more interesting one than a green test.

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
