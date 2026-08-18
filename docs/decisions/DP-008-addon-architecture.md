# DP-008 — Add-on architecture for collectors and normalizers

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-18
- Owners: Project team
- Supersedes: [DP-005](DP-005-two-part-pre-p1-execution.md) P0-B order steps 4–6 and [DP-006](DP-006-p0a-platform-foundation.md) D1's module layout; every other DP-005 and DP-006 decision stands
- Related Open Questions: [OQ-001](../open-questions/OQ-001-source-capability.md), [OQ-002](../open-questions/OQ-002-project-decision-contract.md), [OQ-003](../open-questions/OQ-003-normalization-protocol.md), [OQ-004](../open-questions/OQ-004-snapshot-boundary.md), [OQ-006](../open-questions/OQ-006-job-concurrency.md), [OQ-007](../open-questions/OQ-007-credential-scope.md)
- Affected contracts: every P0-B experimental contract, and the future `PoC Contract 0.1`
- Affected acceptance tests: `ACQ`, `RAW`, `SNP`, `NRM`, domain `OPS`, `SEC-002`, `SEC-003`, `SEC-004`

## Decision question

DP-005 step 6 and the charter's flow item 7 require P0-B to implement one REST collector, one
dataset importer, and one `rule-baseline@0.1` normalizer as platform code. The project owner
has decided that each new source must not add platform code. What replaces the platform-code
model, and what does that supersede?

## Candidates

1. **Platform code, as currently recorded.** Each collector and normalizer is a module inside
   the platform, wired by name at import time.
2. **Out-of-repository add-ons**, distributed as packages and installed from a template
   repository into a deployment directory.
3. **In-repository add-ons behind a contract**, discovered from a directory, loaded in-process,
   granted capabilities by kind, and isolated by a dependency direction that a test enforces.
4. **Subprocess add-ons**, with OS-level isolation and a serialized stdio protocol.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: The add-on contract can be fixed without a selected source, so the add-on layer is not blocked by OQ-001 or OQ-002. | Defining a context, capability, or manifest field requires knowing which provider was chosen, or requires the decision consumer OQ-002 has not yet fixed. |
| H2: Every outbound obligation in the P0 Security Baseline can stay on the platform while a collector add-on still does useful work. | A selected REST source cannot be collected without the add-on composing its own URL, holding a credential, or opening its own socket. |
| H3: A dependency-direction test is sufficient to keep the coupling loose in practice. | An add-on cannot be written against `addon_api` alone without reaching into `platform_core`, or the guard cannot distinguish a legitimate import from a violating one. |
| H4: A contract written in serializable shapes keeps subprocess isolation reachable as a host change. | A capability or context member cannot be expressed without passing a live object that has no serialized equivalent. |

H1 is testable immediately and is the reason the work can start now. H2 is tested by the first
real collector in B3 and is the hypothesis this packet is least certain of.

## Evidence

`[확인 사실]` `experiments/integrated-p0/platform_core/jobs/registry.py` already documents a
capability-passing boundary: the handler context is "deliberately thin", carries "nothing that
would let a handler reach the job tables directly", and an unregistered handler name fails as
`HANDLER_UNKNOWN` on first claim without retry.

`[추론]` `JobContext` plus `apply_effect` plus that failure rule is an add-on seam that already
exists and is already tested. An add-on that is not installed therefore already has defined
behaviour, under a contract P0-A verified.

`[확인 사실]` [OQ-003](../open-questions/OQ-003-normalization-protocol.md) describes a "minimal
provider protocol", a "provider input/output/error contract", and a "contract-conforming
normalizer test double". [DP-002](DP-002-project-identity-and-stack.md) names no normalizer
library.

`[추론]` The record never intended the normalizer to be platform code. It intended a protocol
with providers. This packet changes who authors a provider and how it arrives, not that
providers exist.

`[확인 사실]` `docs/project-state.md` §4 records as `[결정]` that collection and normalization
are independently controlled job domains, that normalization starts explicitly by an operator,
and that the dashboard is P0 instrumentation.

`[확인 사실]` `source_id` and "registered source" exist only as concepts.
`docs/conventions/p0-security.md` requires selecting a registered `source_id`, OQ-007 scopes
credentials by it, and `docs/conventions/secret-setup.md` says a Source row must hold no
credential value. No document states what that row contains. Cursor, watermark, and resumption
appear only in `docs/conventions/evidence-labels.md`, as illustrations of how to label a claim.

`[추론]` The cause is structural. With the collector as platform code, "which source" was
answerable from the code and "where did I stop" from the job payload. Neither survives
operator-installed components, so this packet must define both.

`[추론]` The gap lands on the first limitation the
[P0-A Completion Gate](../../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md)
recorded: every duplicate-suppression result rests on one row with a primary-key conflict, and
a durable effect spanning several statements is untested. Cursor advancement together with Raw
persistence is exactly that effect.

`[확인 사실]` The two components have contracts that differ in kind. A collector needs the
outside world, a network the security baseline assigns to the platform, a credential, and
position state; its failures are partial and resumable and its output cannot be deterministic.
A normalizer takes a sealed hash-verified snapshot, needs no network, no credential, and no
state; its failures cannot be partial and its output must be deterministic byte-for-byte.

`[추론]` A normalizer add-on is therefore nearly free and a collector add-on is the real design
work. The same asymmetry predicts that [OQ-006](../open-questions/OQ-006-job-concurrency.md) H3
resolves to "yes, separately", for a structural rather than an empirical reason.

`[확인 사실]` An in-process add-on is trusted code. Nothing prevents one from importing a
database driver and connecting directly.

## Decision

`[결정]` Collectors, importers, and normalizers are **in-repository add-ons behind a contract**
(candidate 3). The following eight decisions define it.

**D1 — Four packages, one-way dependencies.** `addon_host → platform_core`,
`addon_host → addon_api`, `addon_host → domain`, and `addons/* → addon_api` and nothing else.
`platform_core` gains no new dependency and is not modified by this work, so the P0-A gate's
evidence stands. New packages `addon_api`, `addon_host`, `domain`, `addon_kit`, and the
`addons/` tree live beside `platform_core` under `experiments/integrated-p0/`.

**D2 — Discovery by manifest scan, never a static import.** `addon_host` scans a root
directory for `addons/*/addon.toml` and loads the declared module by `importlib` spec. The root
is `COSMA_ADDON_DIR`, defaulting to the in-repository `addons/`. The platform names no add-on
in code. Add-ons register into the existing `HandlerRegistry` at process start.

**D3 — Four version axes, each with a defined failure.** `contract_version` mismatch refuses
the load at process start; a new `addon_version` makes results coexist rather than replace; a
stale `config_schema_version` marks the source `NEEDS_MIGRATION` and refuses to run;
`output_contract_version` validation failure is a permanent domain failure. An absent add-on is
`HANDLER_UNKNOWN`, already contracted.

**D4 — One package format, three capability sets.** Packaging, manifest, discovery, versioning,
config schema, template, and conformance suite are shared. The granted capabilities differ by
`kind`, because the asymmetry above is real. A collector receives `fetch(endpoint_ref, params)`
and never a URL; an importer receives `open_input(input_ref)` and no network; a normalizer
receives `read_snapshot()` and no network, credential, or cursor. **An add-on never receives a
credential, never composes a URL, and never holds a database handle.** A manifest's `[declares]`
block is a request; the operator approves it into the source row before it is a grant.

**D5 — The source row and the cursor.** Migration `0002_domain.sql` creates `source`
(`source_id`, `addon_id`, `addon_version`, `kind`, non-secret `config`,
`config_schema_version`, `credential_ref`, platform-owned `outbound_profile`, `data_class`,
`enabled`) and `source_cursor` (PK `(source_id, stream)`, `cursor` jsonb opaque to the
platform). `emit_raw` and `advance_cursor` commit in one transaction with attempt completion,
gated by the existing `_FENCE` CTE in `jobs/store.py`.

**D6 — Credential flow.** A config field marked `secret = true` is routed by the dashboard to
the repository-external secret store under the existing `COSMA_SRC_<SOURCE_ID>_<PURPOSE>`
naming; the source row stores only `credential_ref`. The API path is **write-only and never
reads a credential back**. The worker resolves at use time, as `p0-security.md` already
requires. Every existing credential invariant is preserved unchanged.

**D7 — Isolation is contractual, and the record says so.** The design prevents accidental
coupling and accidental credential exposure, enforced by a dependency-direction test. It does
**not** defend against a hostile add-on. Because add-ons are in-repository and reviewed, this
is an accepted P0 posture, recorded in `p0-security.md` rather than implied away.

**D8 — No install table.** The add-on directory is the installed set and the source row is the
approved configuration. The database records what add-ons did — Raw provenance carries
`addon_id@version`, results carry lineage — not which add-ons exist.

### Scope and effective version

`ACCEPTED_FOR_POC` for P0-B only. `addon_api` starts at `CONTRACT_VERSION = "1.0"` and is not
`CONTRACTED` until P0-B evidence supports it. This packet does not promote anything to P1;
DP-001 remains binding and the contract, not the implementations, is the promotion candidate.

## Rejected alternatives

- **Candidate 1, platform code as recorded.** Rejected by the project owner: the backend grows
  with every source, and every source's token lives in project source.
- **Candidate 2, out-of-repository add-ons.** Rejected for P0. It answers a distribution
  question P0 does not have, and splitting the contract across repositories before it has ever
  been exercised would fix the contract at its least informed moment. D2's `COSMA_ADDON_DIR`
  keeps this reachable later as a deployment change.
- **Candidate 4, subprocess add-ons.** Rejected for now on cost. It is the stronger isolation
  and the only candidate that makes D7's limitation go away, but it adds a serialization
  protocol, streaming, and process lifecycle to a stage whose purpose is evidence. H4 and the
  serializability guard keep it reachable as a host change rather than a contract rewrite.
- **In-process with no serializability constraint.** Cheapest, and rejected because it spends
  the option above for a small saving.
- **Separate contracts for collector and normalizer.** The asymmetry is real, but it lives in
  the granted capabilities, not in packaging, discovery, versioning, or configuration. Two
  contracts would duplicate all of that and give the owner two templates instead of one.

## Tradeoffs and risks

- **Benefits:** a new source adds a directory, not platform code; credentials never enter an
  add-on or project source; the security baseline needs no amendment because every outbound
  obligation stays on the platform; the add-on layer is not blocked by OQ-001 or OQ-002, so it
  runs in parallel with source exploration; `SEC-002`, `SEC-003`, and `SEC-004` become testable
  before the first real outbound request exists.
- **Costs:** a contract, a host, a template, a conformance suite, and a generator that the
  platform-code model did not need. Two `[가설]`-level hypotheses (H2, H3) are not settled until
  a real collector exists.
- **Failure modes:** H2 fails if a real source cannot be collected through a
  platform-composed request — the visible symptom is an add-on wanting a URL. H3 fails if the
  contract is too thin to write an add-on against — the symptom is an add-on reaching into
  `platform_core`. Both are caught by tests rather than by review.
- **Reversibility:** full inside disposable P0. If H2 fails, the platform-code model is
  recoverable because the add-on implementations are the same code with a different caller.

## Remaining uncertainty

- H2 and H3 are unresolved until B3 implements a real collector against a real source.
- Whether the outbound guard's DNS rule and a loopback test server can coexist without a
  test-only escape. The recommended `allow_loopback` flag carries a leak risk and needs both a
  test asserting no committed source sets it and a positive control proving the flag off blocks.
- Whether the dashboard writing to the secret store is acceptable long-term. This packet
  proposes D6 as OQ-007's resolution path; OQ-007 remains `OPEN`.
- Whether `contract_version` should gate on the whole contract or per capability. Deferred until
  a second contract version exists.
- Add-on trust remains contractual under D7. Revisit if a P1 deployment ever accepts an add-on
  from outside the review boundary.

## Required changes

- **Project State:** §4 P0-B boundary sequence; §6 Open Question table; record the add-on
  `[결정]` set.
- **Charter:** amend P0-B flow items 5–7; add add-on failure scenarios (contract mismatch,
  config migration, absent add-on, declared-but-ungranted host).
- **Execution plan:** add work package B0; restate B2 and B3 in terms of the add-on contract and
  add-on implementations.
- **Contract or schema:** `addon_api` at `CONTRACT_VERSION = "1.0"`; migration
  `0002_domain.sql`.
- **Security baseline:** record D7's trust limitation and that the platform-side `fetch` is the
  sole outbound path and is not a general URL fetcher.
- **Open Questions:** OQ-006 records the structural prediction for H3; OQ-007 records D6 as a
  proposed resolution path.
- **Acceptance tests:** dependency-direction guard, serializability guard, conformance suite,
  version gate, `emit_raw`/`advance_cursor` atomicity, `addon_kit` end-to-end, credential
  absence with a positive control.
- **Migration or compatibility:** none required. `platform_core` is unmodified and migration
  `0001` is untouched.
- **Implementation handoff:** `tests/environment/test_p0a_boundary_guard.py` forbids `source`,
  `collector`, `importer`, `raw`, `snapshot`, and `normaliz*` in the working tree, so P0-B's
  first file breaks it. Its claim is about revision `f83fe3c`, which is a property of a past
  revision and not of the working tree. Retire it, record that in the gate, and replace it with
  the D1 direction guard.
