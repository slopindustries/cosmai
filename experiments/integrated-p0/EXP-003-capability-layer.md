# EXP-003 — Capability layer and outbound guard

## Identity and status

- Experiment ID: `EXP-003`
- Type: `INTEGRATED_P0`
- Status: `RUNNING` — steps 1-5 complete; step 6 outstanding
- Related Open Question or Decision Packet: [DP-008](../../docs/decisions/DP-008-addon-architecture.md) D4; blocked in part by [OQ-009](../../docs/open-questions/OQ-009-credential-shape.md); informs [OQ-006](../../docs/open-questions/OQ-006-job-concurrency.md), [OQ-007](../../docs/open-questions/OQ-007-credential-scope.md); opened [OQ-010](../../docs/open-questions/OQ-010-cursor-stream-read-back.md)
- Owner: Project team
- Created at: 2026-08-18T15:40:00+09:00
- Last executed at: 2026-08-18T20:09:00+09:00

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

`[결정]` **Amended 2026-08-18, after the box was exceeded and measured.** The owner
released the time bound; the experiment now stops when the procedure below is complete,
step 6 included. The original bound and the measured overrun stay in the Result section,
because the point of writing a box down in advance is lost if it is rewritten to match
what happened.

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

- Code revision: `fcf4b8a` at start; `b91d51c` at the start of this package
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
[측정] 2026-08-18, procedure steps 1-5. Suite: 815 passed, 2 skipped.
       ruff clean; mypy --strict clean over 78 files; both add-ons clean under
       scripts/check-addons.sh.

[측정] addons/collector.naver.blog — written on 2026-08-18 by a separate author against
       the documentation alone, before any of this existed, and NOT modified for this
       run — collected 10 items and a cursor through JobRunner, addon_host.capabilities,
       domain.outbound, domain.transport, a TLS socket, and into PostgreSQL.
       tests/test_outbound_transport.py::TestTheInstalledCollectorRunsThroughThePlatform.
       It composed no URL, held no credential, and opened no socket.

[측정] Two requests for one page of results, as the add-on's own docstring predicts: it
       does not trust `total`, so it pays a second call to confirm exhaustion.

[측정] SEC-002: an unregistered source_id and an ungranted endpoint are both refused with
       zero requests sent. SEC-003: a redirect outside the profile is refused and not
       followed (one hop sent, not two); a redirect inside it is followed. SEC-004: an
       oversized body is refused as RESPONSE_TOO_LARGE while reading, and a server that
       sleeps 6s is abandoned in under 3s against a 1s read timeout, measured on elapsed
       wall-clock rather than on the exception alone.

[측정] Mutation check on the three load-bearing rules, each removed in turn:
         - drop _check_no_refusal_was_swallowed  -> 2 failed
         - drop the items_emitted cross-check     -> 1 failed
         - write immediately instead of enlisting -> 1 failed (the atomicity test)
       Each mutation took down exactly the test that claims the rule.

[측정] The add-on contract was not widened. `addon_api`'s shapes are unchanged; one
       `FetchResponse` docstring sentence was corrected, and no add-on can observe the
       difference. The widening landed on the platform instead: `JobContext` gained
       `attempt_id`.

[측정] Three defects found by running this rather than by reading it:
       1. `CollectContext.cursor` is single-valued while `advance_cursor` names a stream.
          collector.naver.blog reads the default stream and writes "items", so under the
          naive reading it would restart from position 1 forever, silently. -> OQ-010.
       2. `ConfigValidationError` is a plain Exception, so a bad source row was classified
          as "the add-on raised an unexpected ConfigValidationError" — an add-on defect —
          rather than CONFIGURATION_INVALID. Found by the first integration run.
       3. `raw_envelope.attempt_id` and `source_cursor.updated_by_attempt` are both
          `not null`, and `JobContext` carried no `attempt_id`. A durable effect could be
          written but not attributed.
```

## Interpretation

```text
[추론] H2 is SUPPORTED for every outbound obligation except credential attachment. The
       strongest single piece of evidence is that the collector was written by someone
       else, from the documentation, before the platform side existed, and needed no
       change to run — which is what "the obligation stays on the platform" has to mean
       if it means anything. The falsification condition named three things a collector
       must not need; it needed none of them.

[추론] Credential attachment is the untested obligation, and it is untested because
       OQ-009 has not settled what a two-part credential looks like. `p0-security.md`
       lists it among the outbound obligations, so H2 is not fully discharged. What this
       run shows is that the *other* obligations do not require the add-on's cooperation;
       whether the credential one can be added without widening the contract is open.

[추론] H2a is SUPPORTED. TestCollectionIsAtomic proved the transaction at the store level
       with no add-on involved, on purpose. This adds the half that was missing: a worker
       whose lease is stolen mid-fetch persists neither Raw nor cursor, the job stays
       claimable, and the positive control beside it persists all three.

[추론] The weaker failure the falsification section named — "the guard can only be
       satisfied by widening the add-on contract" — did not occur, and the measurement is
       above: the contract's shapes are untouched. That is a real result and not an
       absence of one, because the alternative was visible and available at three points
       (the cursor stream, the envelope handle, the credential) and was taken at none.

[추론] The unswallowable refusal is the part of this package least likely to have been
       written without the failure mode in view. `fetch` raises a PlatformError, and
       `except BaseException` is legal Python; without recording the refusal separately,
       a collector could turn every outbound rule into a suggestion and still report
       success. Its positive control matters as much as the assertion: the same
       swallowing add-on against a granted endpoint succeeds, so the failure is the
       refusal and not the `try` block.

[추론] The three defects above share a shape worth naming: all three were invisible to
       reading and appeared on the first execution. Two of them (1 and 2) fail *silently*
       in production and loudly nowhere, which is the class this project's conventions
       are written against.
```

## Result

- Outcome: `PARTIAL` — steps 1-5 complete; step 6 (adversarial review) running.
- Falsification condition met: `NO` for H2 within its tested scope, `NO` for H2a.
- Exit condition met: `RELEASED`. `[측정]` The 2.5-hour box opened at
  2026-08-18T17:03+09:00 (`040ad0c`) and steps 1-5 ran to 20:09, about 3h05m — over it.
  The sacrifice order fixed in advance was "reduce the `SEC` scenarios first, keep the
  capability layer and the outbound guard"; nothing was sacrificed under it, because the
  `SEC` scenarios landed as well. `[결정]` The project owner released the box on
  2026-08-18 after that measurement, so step 6 runs rather than being recorded as cut.
  The overrun is left on the record rather than erased: a box that is deleted once it is
  exceeded stops being a box, and the next experiment's estimate is worth more if this
  one's error is visible.
- Known limitations:
  - **No credential is attached anywhere.** Blocked by OQ-009 and stated in the
    integration test's own docstring rather than implied.
  - **The stub is not the provider.** Its response shape is the vendor documentation's;
    no capture of the real source exists. collector.naver.blog's three `[가설]`
    assumptions are not confirmed by these tests passing.
  - **Only `collector` is bound.** `normalizer` has no result table (OQ-004) and
    `importer` has no registry of approved inputs. Both are refused by name.
  - **Multi-stream add-ons are refused**, which is OQ-010's interim position and not an
    answer to it.
  - **No adversarial review has run.** A security control's failure mode is passing while
    blocking nothing, and the mutation check above is the author's own — it shows the
    tests are load-bearing, not that the rules are the right ones.

## Impact and next action

- Uncertainty reduced: H2's non-credential half; H2a through a real add-on; the shape of
  the transaction boundary for a multi-statement acquisition effect (OQ-006 H1).
- New uncertainty discovered: OQ-010 (which cursor an add-on reads back). Two smaller
  facts now recorded rather than open: a stored cursor may not be `null`, and an item must
  name an envelope this run fetched.
- Proposed next experiment: the adversarial review that closes this record, then the
  conformance suite, then B1's source selection record, then the operator surfaces.

## Artifacts

- Experiment record: this file
- Code: `experiments/integrated-p0/domain/outbound.py`,
  `experiments/integrated-p0/domain/transport.py`,
  `experiments/integrated-p0/addon_host/capabilities.py`, and their tests
  (`tests/test_outbound_policy.py`, `tests/test_outbound_transport.py`,
  `tests/test_capabilities.py`)
- Fixture or retrieval procedure: synthetic sources and a local TLS stub only. The stub's
  certificate is generated per session with `openssl` and trusted through a per-process
  `ssl.SSLContext` passed to `SocketTransport`; nothing on a source row can widen it.
- Data class and retention responsibility: `public`; no external or personal data

## Completion checklist

- [x] The hypothesis is falsifiable.
- [x] The falsification and exit conditions were fixed before interpreting the result.
- [x] Inputs, rights, environment, versions, and hashes are recorded.
- [x] The procedure is replayable without relying on undocumented session context.
- [x] Observations and interpretations use the project evidence labels correctly.
- [x] Secrets, restricted inputs, and raw conversations are absent.
- [x] The result includes limitations and a concrete next action.
