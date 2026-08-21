# P0 Artifact Disposition Register

- Status: `DRAFT`
- Governing decisions: [DP-001](../decisions/DP-001-p0-lifecycle.md), [DP-005](../decisions/DP-005-two-part-pre-p1-execution.md)
- P0-B experiment: [EXP-003](../../experiments/integrated-p0/EXP-003-capability-layer.md)
- Reviewed code revision: working tree at 2026-08-19, parent `c0a266d`
- Review date and timezone: 2026-08-19, `Asia/Seoul`
- Reviewers: pending — this register is `DRAFT` until the P1 Entry Gate accepts it

## Purpose

Record what P1 receives, rebuilds, keeps only as historical reference, deletes after evidence capture, or carries forward as unresolved. No P0 implementation becomes a P1 runtime or package dependency through this register.

## Disposition values

- `PROMOTE`: accepted contract, scenario, eligible fixture, decision, or evidence artifact.
- `REBUILD_FROM_CONTRACT`: behavior required in P1 and reimplemented from an accepted contract.
- `ARCHIVE_REFERENCE_ONLY`: P0 artifact retained by Git tag or equivalent history but not imported or depended on by P1.
- `DELETE_AFTER_EVIDENCE_CAPTURE`: runtime or protected artifact deleted after required metadata, hashes, and summaries are recorded.
- `UNRESOLVED`: insufficient evidence; carry as an explicit P1 Open Question or blocker.

## Register

### Contracts and decisions

| Artifact | Identity or hash | Data class | Evidence used | Disposition | P1 contract or question | Retention/deletion owner | Rationale |
|---|---|---|---|---|---|---|---|
| `contracts/experimental/CONTRACT-JOB-0.1.md` | versioned document | `public` | JOB-001…008, OPS-001…004 | `PROMOTE` | `PoC Contract 0.1` job section | Project team | Executed end to end; every invariant has a test, and I5's one violation (B6) was found and fixed |
| [`CONTRACT-ADDON-1.3.md`](../../contracts/experimental/CONTRACT-ADDON-1.3.md) | versioned document; `addon_api` is the authority | `public` | `test_addon_api_contract.py`, three collectors, three normalizers, one importer | `PROMOTE` | `PoC Contract 0.1` add-on section | Project team | Written 2026-08-19 to close M5's gap. Promoting the *contract*, not the package — P1 may read this and may not import `addon_api`. |
| DP-008, DP-010, DP-018, DP-019, DP-020, DP-021, DP-022, DP-024 | accepted packets | `public` | linked per packet | `PROMOTE` | folded into `PoC Contract 0.1` | Project team | The project owner decided 2026-08-19 to fold B2's eight contract families into one contract rather than write eight interim documents |
| DP-023 — `SEC-006` waiver | accepted packet | `public` | — | `ARCHIVE_REFERENCE_ONLY` | expires at the P1 Entry Gate | Project team | A P0-only waiver. It must not appear in any P1 list of satisfied controls. |
| `Normalized Schema 0.2` | DP-019 + DP-021 | `public` | `test_normalized_results.py`, two normalizers over real data | `PROMOTE` | `PoC Contract 0.1` schema section | Project team | The discriminated-union form, carrying the refutation of the strong hypothesis with it |

### Implementation

| Artifact | Identity or hash | Data class | Evidence used | Disposition | P1 contract or question | Retention/deletion owner | Rationale |
|---|---|---|---|---|---|---|---|
| `platform_core/` | 7 files changed since `f83fe3c` | `public` | 1192-test suite; PLATFORM-CORE-GATE-2026-08-17 | `REBUILD_FROM_CONTRACT` | `CONTRACT-JOB-0.1` | P1 owner | The **shape** survived P0-B and is the strongest P0 result. `AGENTS.md`: P0 code must not become a P1 dependency. |
| `domain/` (store, outbound, transport, inputs, secrets, migrations) | working tree | `public` | outbound security review; `test_outbound_*`, `test_input_registry.py` | `REBUILD_FROM_CONTRACT` | `PoC Contract 0.1` outbound and input sections | P1 owner | The guard held under adversarial review; four defects in one day say the *implementation* is hard, not that the design is wrong |
| `addon_host/` incl. `capabilities.py` | working tree | `public` | `test_capabilities.py`, `test_normalizer_capability.py`, `test_importer_local_jsonl.py` | `UNRESOLVED` | [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md), [OQ-014](../open-questions/OQ-014-externalized-acquisition.md) | Project team | The *direction* is proved; **where to cut the seam is deliberately unsettled**, and OQ-014 may move acquisition out of the service entirely |
| `addons/collector.naver.*` (3) | working tree | `public` | real API runs 2026-08-19 | `ARCHIVE_REFERENCE_ONLY` | — | P1 owner | Source-specific by design and disposable by charter. 13–15% is duplicated plumbing the layer rule forces. |
| `addons/normalizer.naver.*` (2), `normalizer.conformance` | working tree | `public` | `test_normalizer_*`, real snapshots | `ARCHIVE_REFERENCE_ONLY` | — | P1 owner | Same. `normalizer.conformance` is the harness's subject, not a product component. |
| `addons/importer.local.jsonl` | working tree | `public` | `test_importer_local_jsonl.py`, `test_obf_real_data.py` | `ARCHIVE_REFERENCE_ONLY` | [OQ-001](../open-questions/OQ-001-source-capability.md) dataset half | P1 owner | Proves the import *path*. `[확인 사실]` **Since 2026-08-20 it also reads a real external file** — Open Beauty Facts delta exports ([DP-027](../decisions/DP-027-dataset-standard-and-share-alike.md)). An earlier revision of this row said it reads a file this project authored; that was true until TASK-007. |
| `addons/normalizer.obf.product` | working tree | `public` | `test_normalizer_obf_product.py` (41 cases), `test_obf_real_data.py` | `ARCHIVE_REFERENCE_ONLY` | [OQ-003](../open-questions/OQ-003-normalization-protocol.md) | P1 owner | Schema 0.3's only producer ([DP-028](../decisions/DP-028-schema-0-3-product-records.md)). Survived an independent attack; its five weak assertions are in [P1-INHERITED-DEFECTS](P1-INHERITED-DEFECTS.md) §3. |
| `addons/normalizer.rule.baseline` | working tree | `public` | `test_normalizer_rule_baseline.py` | `ARCHIVE_REFERENCE_ONLY` | [OQ-013](../open-questions/OQ-013-addon-responsibility-boundary.md) | P1 owner | The only add-on that *judges* rather than reshapes; answers hypothesis 6 on fixtures. Its six stated gaps are in [P1-INHERITED-DEFECTS](P1-INHERITED-DEFECTS.md) §2. |
| `addon_kit/` (generator + harness) | working tree | `public` | `test_addon_kit.py`, `test_addon_harness.py` | `ARCHIVE_REFERENCE_ONLY` | — | P1 owner | Build-time tooling. `[측정]` Its harness understates what the platform refuses — at least two more cases than the four it lists. |
| `dashboard/` | 7 files changed since `f83fe3c` | `public` | `test_dashboard.py`, `test_operator_loop.py`, real normalized rows | `REBUILD_FROM_CONTRACT` | OQ-005 operations contract | P1 owner | The four actions and the telemetry set are the promotable part; the React code is not |
| `tools/structural_fixture.py` | `RULESET_VERSION = "1"` | `public` | `tests/test_structural_fixtures.py` (30 cases) | `PROMOTE` | [DP-022](../decisions/DP-022-structural-fixtures.md) | Project team | Generation, not redaction. The only way this project can commit a fixture shaped like `local` data. |

### Scenarios, evidence, and data

| Artifact | Identity or hash | Data class | Evidence used | Disposition | P1 contract or question | Retention/deletion owner | Rationale |
|---|---|---|---|---|---|---|---|
| `tests/acceptance/` JOB-001…008, OPS-001…004, SEC-001…004 | 16 scenarios | `public` | each has an executable counterpart | `PROMOTE` | `PoC Contract 0.1` acceptance set | Project team | `[확인 사실]` The `SEC-00N` numbering here differs from `p0-security.md`'s; the mapping table in that file must travel with them |
| `experiments/integrated-p0/tests/` | 1192 tests | `public` | itself | `REBUILD_FROM_CONTRACT` | promoted scenarios | P1 owner | The *assertions* are the asset; they are written against P0 internals |
| `evidence/2026-08-17-f83fe3c/` | captured artifacts + SHA-256 | `public` | P0-A gate | `ARCHIVE_REFERENCE_ONLY` | — | Project team | `[측정]` Evidence about `f83fe3c` **and nothing else** — behaviour it measured has since changed. Corrected 2026-08-19. |
| `evidence/naver-real-data/README.md` | hashes + retrieval procedure | `public` | the three real runs | `PROMOTE` | — | Project team | Hashes and instructions only. **No payload is committed and none will be.** |
| NAVER captures in the local database | `sha256:70adcc03…`, `sha256:af9505b3…`; one digest lost | `local` | — | `DELETE_AFTER_EVIDENCE_CAPTURE` | — | **Operator** | Basis is personal research and study, which is not a redistribution basis. Digests and retrieval instructions are recorded; the rows themselves are the operator's to delete. |
| The blog capture's lost digest | — | `local` | — | `UNRESOLVED` | — | Project team | `[결정]` Recorded as a gap, not back-filled. A digest from a *second* capture would not be that run's digest. |
| Local PostgreSQL databases used by the suite | per-run, ephemeral | `local` | — | `DELETE_AFTER_EVIDENCE_CAPTURE` | — | Operator | Recreated per run; nothing in them is evidence once a digest is recorded |
| `~/.config/cosmai/env` | key names only in repo | `private` | — | `DELETE_AFTER_EVIDENCE_CAPTURE` | — | **Operator** | Outside the working tree by rule. The repository holds key *names*; the values are the operator's to rotate or delete. |

### Reviews and open questions

| Artifact | Identity or hash | Data class | Evidence used | Disposition | P1 contract or question | Retention/deletion owner | Rationale |
|---|---|---|---|---|---|---|---|
| `ADVERSARIAL-REVIEW-2026-08-17/18/19/19-MUTATION.md` | 4 documents | `public` | 208 mutants in the last | `PROMOTE` | — | Project team | The review record is the reason the repairs are believable. Committed **before** repair, by convention. |
| `DEBT-REVIEW-2026-08-19.md`, `JUDGMENT-DEBT-2026-08-18.md` | 2 documents | `public` | — | `PROMOTE` | — | Project team | Where the process failures are written down, including the out-of-order source selection |
| OQ-001 (dataset half), OQ-003…008, OQ-010, OQ-013, OQ-014 | open questions | `public` | — | `UNRESOLVED` | carried to P1 | Project team | Each is an explicit blocker or open item rather than an implied one |

## Required inventories

- **Experimental and promoted contracts** — `CONTRACT-JOB-0.1`; `addon_api` 1.3 (no document); Normalized Schema 0.2; the outbound and input policies. `[확인 사실]` Only the first exists under `contracts/experimental/`.
- **Acceptance scenarios and deterministic expected outputs** — 16 scenarios, all with executable counterparts.
- **Public, local, and private fixtures or runtime inputs** — no `local` or `private` payload is committed. Structural fixtures under DP-022 are generated, not redacted.
- **Source capability records, hashes, retrieval instructions** — [SRC-001](../../experiments/source-probes/SRC-001-naver-api-hub.md), [SRC-002](../../experiments/source-probes/SRC-002-local-jsonl.md), the selection matrix, and `evidence/naver-real-data/README.md`.
- **P0 backend, dashboard, migrations, orchestration** — all under `experiments/integrated-p0/`; four migrations.
- **Logs, metrics, traces, screenshots, temporary databases** — ephemeral; the dashboard is asserted through rendered text rather than screenshots, by design.
- **Architecture decisions, rejected alternatives, unresolved questions** — DP-001…017, OQ-001…012.

## Acceptance checks

- [x] Every material P0 artifact has exactly one disposition.
- [x] Every `PROMOTE` item has an accepted decision and compatibility status where required.
- [x] Every `REBUILD_FROM_CONTRACT` item links the accepted contract and P1 owner.
- [x] Every `ARCHIVE_REFERENCE_ONLY` implementation is prohibited as a P1 runtime or package dependency.
- [x] Every `DELETE_AFTER_EVIDENCE_CAPTURE` item has required metadata, hashes, summaries, and deletion responsibility recorded.
- [x] Every `UNRESOLVED` item links an Open Question or explicit blocker.
- [x] Restricted data, credentials, and raw conversations are not preserved contrary to project conventions.
- [ ] **An archive tag exists.** `[확인 사실]` Not yet created; the charter requires archiving P0 implementation by Git tag or equivalent. This is the one acceptance check that is not met.

## Decision

- Outcome: `NOT ACCEPTED` — pending the P1 Entry Gate
- `[결정]` This register is complete as a **draft**. It cannot be `ACCEPTED` here: acceptance is the P1 Entry Gate's act, and one acceptance check (the archive tag) is not met.
- Remaining blockers to P1 entry:
  1. The archive tag does not exist.
  2. `addon_host/`'s disposition is `UNRESOLVED` pending OQ-013 and OQ-014 — and OQ-014 could change what P1 builds.
  3. `SEC-006` must be satisfied, not waived, before P1 runs against real sources.
