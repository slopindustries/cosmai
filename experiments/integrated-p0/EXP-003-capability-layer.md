# EXP-003 — Capability layer and outbound guard

## Identity and status

- Experiment ID: `EXP-003`
- Type: `INTEGRATED_P0`
- Status: `RUNNING`
- Related Open Question or Decision Packet: [DP-008](../../docs/decisions/DP-008-addon-architecture.md) D4; blocked in part by [OQ-009](../../docs/open-questions/OQ-009-credential-shape.md); informs [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md), [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md)
- Owner: Project team
- Created at: 2026-08-18T15:40:00+09:00
- Last executed at: 2026-08-18T15:40:00+09:00

## Question

Can a collector do useful work when the platform owns **every** outbound obligation —
the URL, the allowlist, the redirect check, the address-range check, the limits, and the
credential?

## Hypothesis

`[가설]` **H2.** Every outbound obligation in the
[P0 Security Baseline](../../docs/conventions/p0-security.md) can stay on the platform
while a collector add-on still does useful work.

This is the one hypothesis [EXP-002](EXP-002-addon-layer.md) did not reach, and the
largest remaining bet in the add-on architecture. `[추론]` If it fails, the conformance
suite and the operator surfaces would be built on a contract that has to change — which
is why both wait for this rather than proceed beside it.

`[가설]` **H2a.** A collection is atomic through a real add-on, not only through the
store: an interruption between the Raw write and the completion leaves neither a lost
record nor a repeated one.

`[측정]` H2a has store-level evidence already
(`tests/test_domain_store.py::TestCollectionIsAtomic`). What is untested is the same
property when an add-on is what drives it.

## Falsification condition

- **H2** is refuted if a collector cannot do its work without composing its own URL,
  holding a credential, or opening its own socket — or if the platform cannot construct
  a valid request from an `endpoint_ref` and an approved source profile alone.
- **H2a** is refuted if an interruption through the real handler path leaves Raw without
  its cursor, or a cursor without its Raw.

`[추론]` A weaker failure is also worth naming: if the guard can only be satisfied by
widening the add-on contract, H2 survives but at a cost, and the size of that widening is
the measurement.

## Exit condition

Stops at **2.5 hours**, or when the capability layer, the outbound guard, and the
security scenarios below are complete, whichever comes first.

If the box expires mid-package, the incomplete part is recorded as unfinished with what
was and was not built. **The order of sacrifice is fixed in advance**, so that a running
clock does not decide it: the `SEC` scenarios are reduced first, and the capability layer
and outbound guard are kept — those two are what test H2.

## Scope

### Included

- The outbound guard: URL construction from a registered source profile, scheme/host/
  port/path allowlist, redirect revalidation, DNS address-range blocking, per-source
  timeouts and body/page/record limits, protected-header stripping.
- The capability implementations behind `addon_host.registration.Invoke`, which is a seam
  that currently refuses.
- Running `addons/collector.naver.blog` **through the platform** rather than the harness.
- `SEC-002`, `SEC-003`, `SEC-004` against a synthetic registered source.

### Excluded

- **Credential attachment.** Blocked by [OQ-009](../../docs/open-questions/OQ-009-credential-shape.md):
  the selected API needs two headers and `Declarations.needs_credential` is one boolean.
  `[추론]` The guard is fully testable against a source that needs no credential, so the
  block is partial and the split is along that line.
- Any request to a real provider. Everything is a local stub, so `SEC-006` (narrowing the
  agent sandbox) is not yet triggered.
- The conformance suite, the operator surfaces, and B1's source selection record.

## Inputs and provenance

| Input | Source or provider | Captured at | License or usage basis | Version or hash | Storage note |
| --- | --- | --- | --- | --- | --- |
| None | — | — | — | — | Synthetic sources and a local stub server only. No external input. |

## Environment

- Code revision: `fcf4b8a` at start
- Runtime and dependency versions: Python 3.13.7, psycopg 3.3.4, pytest 8.x, mypy strict, ruff
- External service or database versions: PostgreSQL 18.4, repository-local cluster over a Unix socket
- Relevant configuration with secrets removed: no credential is resolved in this package
- Reproduction command: `./scripts/with-database.sh .venv/bin/pytest -q`

## Procedure

1. **Outbound guard** — `domain/outbound.py`. Implement `p0-security.md` §Outbound one
   obligation at a time, each with the test that shows it refusing.
2. **Capabilities** — `addon_host/capabilities.py`. Fill the `Invoke` seam: read the
   source row, assemble the kind's context, bind `emit_raw`/`advance_cursor` to
   `DomainStore`, and cross-check the add-on's reported count against what it emitted.
3. **One transaction, completion last** — the pattern `domain/store.py` specifies. A
   worker that lost its lease must persist neither Raw nor cursor.
4. **Real integration** — run the collector through the platform.
5. **`SEC-002`/`SEC-003`/`SEC-004`** against a synthetic source.
6. **Adversarial review** — an independent agent tries to get a request past the guard.
   `[추론]` A security control's failure mode is passing while blocking nothing, which is
   the shape its own author is least able to see.
7. Classify any failure as implementation, specification, assumption, evaluation, or goal
   before changing anything.

### Known obstacle, decided in advance

The DNS rule blocks loopback, so a local stub cannot be reached through the production
path. A per-source test-only `allow_loopback` flag is permitted, with **two** tests: no
committed source sets it, and with the flag off a loopback address is actually refused.
`[추론]` The second is not optional — an absence assertion with no positive control
passes equally well against a guard that checks nothing.

## Evidence collection

- Metrics and units: test counts and durations; refusal reasons; lint and type cleanliness.
- Log or trace location: `var/log/platform.jsonl`.
- Output artifact location: `evidence/<date>-<sha>/`, captured opt-in with
  `--capture-evidence=DIR`.
- Integrity check: SHA-256 per artifact, with `git diff <sha>..HEAD` empty over the code
  paths the evidence names.

## Observations

```text
[측정] Not yet recorded.
```

## Interpretation

```text
[추론] Not yet recorded.
```

## Result

- Outcome: `INCONCLUSIVE` — the experiment is `RUNNING` and this section is not final.
- Falsification condition met: `NOT TESTED`
- Exit condition met: `NO`
- Known limitations: to be recorded.

## Impact and next action

- Uncertainty reduced: to be recorded.
- New uncertainty discovered: to be recorded.
- Proposed next experiment: the conformance suite, then B1's source selection record,
  then the operator surfaces — in that order, and all of them after H2 has an answer.

## Artifacts

- Experiment record: this file
- Code: `experiments/integrated-p0/domain/outbound.py`,
  `experiments/integrated-p0/addon_host/capabilities.py`, and their tests
- Fixture or retrieval procedure: synthetic sources and a local stub only
- Data class and retention responsibility: `public`; no external or personal data

## Completion checklist

- [x] The hypothesis is falsifiable.
- [x] The falsification and exit conditions were fixed before interpreting the result.
- [x] Inputs, rights, environment, versions, and hashes are recorded.
- [ ] The procedure is replayable without relying on undocumented session context.
- [ ] Observations and interpretations use the project evidence labels correctly.
- [ ] Secrets, restricted inputs, and raw conversations are absent.
- [ ] The result includes limitations and a concrete next action.
