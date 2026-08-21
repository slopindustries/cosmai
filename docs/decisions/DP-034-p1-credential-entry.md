# DP-034 — Let the dashboard write a credential once, and say exactly which invariant that bends

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-21
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-21, brainstorming session — docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md)`
- Related Open Questions: [OQ-007](../open-questions/OQ-007-credential-scope.md) — partially
  answered. This packet settles the dashboard/API **write** path (D1, D2). Which
  `credential_ref` a **worker** may resolve at job-execution time — OQ-007's actual scoping
  question — stays `OPEN` and is not addressed here.
- Affected contracts: none in `contracts/experimental/` directly. `docs/conventions/secret-setup.md`
  and `docs/conventions/p0-security.md` each gain one forward-link line to this packet (Required
  changes, done in this commit).
- Affected acceptance tests: none by this packet. A `SEC` scenario for "a submitted credential
  value never appears in an API response or log" is M1/M5 implementation work
  (spec §10 "신규": "시크릿 쓰기 경로").

## Decision question

[DP-008](DP-008-addon-architecture.md) D6 proposed, for P0-B, that a manifest config field marked
`secret = true` be routed by the dashboard to the repository-external secret store, with the
source row keeping only `credential_ref`. It called this a `[결정]` but in the same packet's
Remaining uncertainty listed "whether the dashboard writing to the secret store is acceptable
long-term" as unresolved and left [OQ-007](../open-questions/OQ-007-credential-scope.md) `OPEN`.
`[측정]` No P0 code ever implemented that write path: the dashboard (`domain-view.tsx`, `api.ts`)
only ever reads and displays `credential_ref` names, and no route in `platform_core/api/app.py`
accepts a credential value (grep of `experiments/integrated-p0/dashboard/src/` and
`experiments/integrated-p0/platform_core/api/`, 2026-08-21). `plan.md` §5 and §7.1 now ask for
exactly this path explicitly: a collector's required secret is captured through that collector's
own dashboard screen and held as the running program's own configuration, not a per-user setting.

Separately, [DP-023](DP-023-sec-006-waived-for-p0.md) waived `SEC-006` for P0 and stated its own
expiry condition: *"The P1 Entry Gate must not accept a plan that carries this forward."* The
[P1 Reconstruction Plan](../architecture-synthesis/P1-RECONSTRUCTION-PLAN.md) Phase 0.3 names the
same boundary: *"Satisfy `SEC-006` — narrow the agent sandbox, or record a P1-scoped decision that
is not a waiver."*

So: does P1 build the dashboard credential-entry path DP-008 D6 proposed but never implemented,
and if it does, exactly which of `secret-setup.md`'s four P1-promoted invariants does that bend,
and how narrowly? And separately: what closes Phase 0.3 for `SEC-006` — a repaired sandbox, or a
named P1-scoped decision?

## Candidates

**Credential entry (D1):**
1. No dashboard entry; the operator hand-edits `~/.config/cosmai/env` for every source.
2. A write-only dashboard field, per collector screen, that the API writes to the secret store
   and never reads back or re-displays. (this packet's choice)
3. A read/write field that also displays the currently configured value for in-place editing.

**Scope of the invariant relaxation (D2):**
1. State only that "the dashboard now touches credentials," with no further scoping.
2. Name the specific invariant that bends, and bound the relaxation to one operation only — a
   single input request's write path — while the remaining invariants and remaining scope of the
   bent one stay intact. (this packet's choice)
3. Treat DP-008 D6 as already having settled this, and write nothing new.

**`SEC-006` and the other deferred P0-B security items (D3):**
1. Leave them where DP-023 put them — an expiring P0 waiver — and let the P1 Entry Gate read
   silence as "nothing changed."
2. Move them into the security-recommendations register (`SR-001`–`SR-005`) as an explicit,
   independent P1-scope decision that the waiver is not extended. (this packet's choice)
3. Implement all of `SR-001`–`SR-005` now, inside M0, before the gate.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Confining the API's credential contact to one write-only path — never re-displayed, never echoed in a response, never logged — prevents value leakage through the dashboard/API surface. | Any dashboard/API response body, log line, or error message is found to contain a plaintext credential value rather than a `credential_ref` name. |
| H2: The write-only path needs no second credential-resolution mechanism alongside the worker-side `resolve_credential` DP-018 D4 already defines. | The write endpoint needs to read an existing value back (for validation, confirmation, or display), which would require a second resolver the worker-only design does not have. |
| H3: Registering `SEC-006`, redirect defense, URL enforcement level, and the deletion obligation in `security-recommendations.md` as an explicit P1-scope decision — rather than as a continuation of DP-023's waiver — satisfies Reconstruction Plan Phase 0.3. | An accepted document in this gate's record is found to read as "the DP-023 waiver continues into P1," which DP-023 itself forbids. |

## Experiment

- Scope: no new experiment is run by this packet. It reads DP-008 D6's proposal, OQ-007's own
  assessment of what that proposal did and did not resolve, `secret-setup.md`'s four promoted
  invariants, DP-023's waiver and its stated expiry condition, and the owner's 2026-08-21
  brainstorming answers, and decides.
- Environment and versions: none — a document-only milestone (M0).
- Input and fixture identity: `docs/conventions/secret-setup.md`, `docs/conventions/p0-security.md`,
  [DP-008](DP-008-addon-architecture.md) D6, [DP-018](DP-018-credential-parts-and-attachment.md),
  [DP-023](DP-023-sec-006-waived-for-p0.md), [OQ-007](../open-questions/OQ-007-credential-scope.md),
  `plan.md` §5, §7.1 (owner notes, repository root, untracked); one grep of the current dashboard
  and API source performed 2026-08-21 to confirm the write path is unimplemented.
- Known limitations: this packet decides what P1 builds; it does not itself verify the write path
  (M1/M5 implementation), and it does not test H1–H3 — only names their falsification conditions.

## Evidence

`[확인 사실]` `secret-setup.md`'s four P1-promoted invariants: (1) no credential file exists in
the repository working tree; (2) a credential value does not reside in a process environment
variable — it is resolved at the point of use and held only for the lifetime of that use; (3) no
credential value appears in a source row, job payload, Raw envelope, log, screenshot, or fixture
— only `credential_ref` is stored; (4) a missing or unresolved credential ends the job as a
non-retryable configuration failure, never an empty value or a fallback.

`[확인 사실]` `secret-setup.md`'s "P0-B Worker 구현 규칙" section describes invariant 2's "point
of use" entirely from the worker's side: resolution happens in one function,
`resolve_credential(ref)`, called by the worker at the moment a request is sent, reading the
store named by `COSMA_SECRET_SOURCE`. No comparable rule exists anywhere in `secret-setup.md` or
`p0-security.md` for the API process — the documents describe the API only as a name-carrier
(`credential_ref` is safe to show in logs and the dashboard; the value never is).

`[확인 사실]` [DP-008](DP-008-addon-architecture.md) D6: *"A config field marked `secret = true`
is routed by the dashboard to the repository-external secret store... the source row stores only
`credential_ref`. The API path is write-only and never reads a credential back."* The same
packet's Remaining uncertainty: *"Whether the dashboard writing to the secret store is acceptable
long-term. This packet proposes D6 as OQ-007's resolution path; OQ-007 remains `OPEN`."*

`[확인 사실]` [OQ-007](../open-questions/OQ-007-credential-scope.md) quotes D6's write-only design
and states plainly what it does not settle: *"This does not resolve H1, H2, or H3... The worker
process still holds the value for the life of the request inside `fetch`, so per-source scoping
is still enforced by resolution discipline rather than by process boundary."* OQ-007's own
question — which `credential_ref` a worker may resolve — is unrelated to whether the API may write
one, and D6 narrowed only the latter.

`[측정]` 2026-08-21, `grep -rln credential_ref experiments/integrated-p0/dashboard/src/`
returns `domain-view.tsx` and `api.ts`, both of which only read and render `credential_ref` and a
`CredentialTable` of header/ref-name pairs (`domain-view.tsx:133,147,227`); no write field exists.
`[확인 사실]` Corrected 2026-08-21: an earlier revision of this line recorded
`grep -rln secret\|credential experiments/integrated-p0/platform_core/api/`, a command whose
unescaped `|` is a literal character to `grep`'s basic regular expressions rather than
alternation — it matches nothing and exits 1 on this tree, so it proved nothing about the
route handlers even though its stated conclusion happened to be true. The working form,
`grep -rlnE 'secret|credential' experiments/integrated-p0/platform_core/api/`, returns
`app.py` and `__main__.py` against a clean checkout; every match in both files is inside a
comment or docstring referencing `secret-setup.md`'s guard (`__main__.py:8,181`; `app.py:91`) —
no route handler accepts a credential value. `[확인 사실]` Re-run 2026-08-21 (fix-wave round 3):
against a working tree where `pytest` has already run, the same command also matches a
gitignored `__pycache__/__main__.cpython-313.pyc` build artifact (`.gitignore:19`, untracked) —
not a source file and not part of any checkout that has not executed Python first; the two
`.py` files remain the only tracked matches. DP-008 D6's mechanism was proposed but never built
in P0.

`[확인 사실]` [DP-018](DP-018-credential-parts-and-attachment.md) D3: every credential header must
be a member of `PROTECTED_HEADERS`, refused otherwise, so that attachment and stripping are the
same set by construction. D4: resolution happens through the one worker-side function, wrapped in
a type whose `repr` is redacted.

`[확인 사실]` [DP-023](DP-023-sec-006-waived-for-p0.md): *"The P1 Entry Gate must not accept a
plan that carries this forward"* — the waiver's own first obligation. *"Must be closed before:
P1 Entry Gate"* in the packet's own header.

`[확인 사실]` [P1 Reconstruction Plan](../architecture-synthesis/P1-RECONSTRUCTION-PLAN.md) Phase
0.3: *"Satisfy `SEC-006` — narrow the agent sandbox, or record a P1-scoped decision that is not a
waiver | DP-023 expires at the P1 Entry Gate. P1 runs against real sources and is not
disposable."*

`[확인 사실]` `security-recommendations.md` already registers `SR-001` (unauthorized-URL
enforcement level), `SR-004` (redirect and address-range defense re-implementation), and `SR-005`
(`SEC-006`) with an explicit statement that `SR-005`'s presence in the register "is a new decision
in itself, which [DP-034] scopes... the waiver does not extend here; it ends, and a new decision
takes its place." `SR-001` and `SR-004`'s own "부재가 의미하는 것" columns state that only the
enforcement *level* moves to the register — the outbound guard's *structure* (endpoint naming,
the skeleton credential attachment needs) stays in the P1 contract regardless of this packet.

`[확인 사실]` `plan.md` §7.1: a required secret is kept as the running program's own fixed
configuration, not a per-user file, and is settable through the dashboard — each collector's
config screen can fix its own configured value. §5 goal 5 states the same requirement from the
operator-scenario side: a collector's required secret or id must be capturable through that
collector's own dashboard screen, held as the program's own state once set, not per-operator.

## Decision

`[결정]` **D1 — The collector-domain dashboard screen accepts a credential value as input.** The
API writes it to `~/.config/cosmai/env` (outside the repository, mode `600`) as
`COSMA_SRC_<SOURCE_ID>_<PURPOSE>=<value>`, following the naming `secret-setup.md` and DP-018
already fix. The path is **write-only**: the value is never re-displayed, never echoed in the
write response, and never logged. The screen shows only the `credential_ref` name and whether it
is currently set — exactly what DP-008 D6 proposed and what P0 never built.

`[결정]` **D2 — This is a narrow relaxation of invariant 2, and only of its unstated process
scope, not its stated content.** Invariant 2's text — "resolved at the point of use, held only
for the lifetime of that use, never through a process environment variable" — is unchanged and
still binds. What was never stated, but was true of every path P0 actually built, is that "the
point of use" meant *the worker's outbound request*, and the process holding a value was always
*the worker*. D1 adds a second point of use — the API process, at the moment it receives an
operator's input and writes it to the store — and a second process, bounded to that one call.
`[결정]` The relaxation's scope is exactly this: one input request's write path, once, per
submission. Nothing else moves: repository tree, database, environment variables, Raw, logs, and
screens still never carry a value (invariant 1, 3 unchanged); an unresolved reference still ends
in `CONFIGURATION_INVALID` (invariant 4 unchanged); DP-018's protected-header attachment system is
untouched; worker-side resolution scope stays exactly what OQ-007 leaves open.

`[결정]` **What this relaxation does not cover, and is recorded rather than eliminated:** for the
duration of one write call, the submitted value exists in the API process's memory. This packet
does not add a mechanism that removes that — it states it as the boundary of what D1 costs, so a
future reader does not mistake "write-only" for "the API process never holds a value at all."

`[결정]` **D3 — `SEC-006`, redirect and address-range defense re-implementation, enforcement
level, and the deletion-obligation path move to `security-recommendations.md` (`SR-001`–`SR-005`)
as an independent P1-scope decision, not as an extension of DP-023's waiver.** DP-023's waiver
expires at this gate exactly as it said it would; nothing in this packet or in
`security-recommendations.md` states or implies that the waiver continues. `[결정]` This decision
— that these items are deferred, named, and bounded rather than either blocking or silently
dropped — is what satisfies [P1 Reconstruction Plan](../architecture-synthesis/P1-RECONSTRUCTION-PLAN.md)
Phase 0.3's "or record a P1-scoped decision that is not a waiver" clause.

## Rejected alternatives

- **D1 Candidate 1, no dashboard entry.** Rejected: `plan.md` §5 and §7.1 ask for it explicitly,
  and DP-008 D6 already found the alternative — hand-editing `~/.config/cosmai/env` once per
  source, per collector, with no dashboard visibility into what is or is not set — worse for an
  operator managing eight or nine add-ons across six screens (DP-033 D1) than one write endpoint
  per source (`[확인 사실]` corrected 2026-08-21, fix-wave round 3, D3 — M4 builds four or five
  collectors, one importer, and three normalizers; see `P1-RECONSTRUCTION-PLAN.md`'s M4 row).
- **D1 Candidate 3, read/write with re-display.** Rejected: it reopens exactly the leak channel
  invariant 3 forbids — a value appearing on a screen — for a convenience (viewing the current
  value) that DP-008 D6's design already avoids needing (`[확인 사실]` corrected 2026-08-21 —
  an earlier revision of this line cited "DP-018 D6"; DP-018 D6 exists but is about a
  different subject ("The add-on never learns that attachment happened," DP-018:63) — the
  write-only-editing design under discussion here is DP-008 D6's, quoted correctly elsewhere
  in this packet at line 104): editing is done by
  submitting a new value,
  never by reading the old one back.
- **D2 Candidate 1, no specific scoping.** Rejected: `AGENTS.md`'s rule that a claimed control must
  record what it does not cover applies here in reverse — a *relaxed* control must record what
  still holds, or a reader cannot tell the difference between "one invariant bent once" and "the
  whole credential-handling design is now optional."
- **D2 Candidate 3, treat DP-008 D6 as already settled.** Rejected: D6's own Remaining uncertainty
  said the opposite — that long-term acceptability was unresolved — and OQ-007 confirms it "does
  not resolve H1, H2, or H3." Nothing in the record between 2026-08-18 and this session closed
  that gap; this packet is what closes it, not a restatement of something already closed.
- **D3 Candidate 1, leave `SEC-006` etc. where DP-023 put them.** Rejected: DP-023 explicitly
  forbids this outcome — "must not accept a plan that carries this forward" — and silence at the
  gate would read exactly like the waiver continuing, which is the failure mode DP-023 itself
  named.
- **D3 Candidate 3, implement `SR-001`–`SR-005` now.** Rejected: the [P1 Reconstruction
  Plan](../architecture-synthesis/P1-RECONSTRUCTION-PLAN.md) already sequences outbound/input
  policy work into Phase 2, after Phase 0's structural decisions; front-loading five security
  items into a document-only milestone (M0) contradicts that sequencing, and DP-023's own record
  of four defects found in one day of adversarial review argues for treating this as a component
  needing a dedicated pass, not a rushed addition here.

## Tradeoffs and risks

- Benefits: closes `plan.md` goal 5 without inventing a second credential-resolution mechanism;
  narrows OQ-007 instead of leaving all of it open; retires DP-023's waiver at the gate exactly as
  the waiver's own text requires, replacing silence with a named decision; satisfies Reconstruction
  Plan Phase 0.3 without narrowing the agent sandbox, which DP-023 already argued would cost more
  than it protects at this stage.
- Costs: the API process genuinely holds a plaintext value in memory during each write call — a
  fact D2 records rather than removes. `SR-001`–`SR-005` remain unimplemented going into P1, so P1
  starts real-source work with the same outbound-guard exposure DP-023 found four defects in
  during one day of P0-B review.
- Failure modes: a future implementer could add a "read back for confirmation" endpoint to the
  write path, silently reopening the leak channel D1 forecloses — D2's narrow scoping exists so
  that any such addition is visibly a *new* relaxation, not a continuation of this one. A future
  reader could conflate D3's registry placement with "the security items are handled" — `SR-001`
  through `SR-005`'s own "부재가 의미하는 것" columns, and this packet's own Tradeoffs, exist to
  prevent that reading.
- Reversibility: D1 is additive — one write endpoint and one dashboard field — reversible by
  removal, leaving hand-edited `~/.config/cosmai/env` as the fallback `secret-setup.md` already
  documents. D2 is a scope statement, not code; narrowing it further costs nothing. D3 is a
  registry placement; each `SR` item can be promoted to implementation independently, at any time,
  without revisiting this packet.

## Remaining uncertainty

- OQ-007's actual scoping question — which `credential_ref` a worker may resolve at execution
  time, and whether per-source scoping requires partitioning workers by source — stays fully
  `OPEN`. This packet answers none of OQ-007's H1–H3; it only settles the write side D6 proposed.
- Whether the API process's in-memory handling of a submitted value during the write call should
  use the same `repr`-redacted wrapper type DP-018 D4 defines for the worker's resolved values, or
  needs a separate one for the input path, is undecided — M1 implementation work.
- Whether `~/.config/cosmai/env`'s single-file, whole-process-configuration model (one file, no
  per-operator scoping, per `plan.md` §5) holds once more than one operator or environment is in
  play is out of scope here; `p0-security.md`'s Non-goals already exclude multi-tenant
  authorization, and nothing in this packet revisits that exclusion.
- `SR-001` through `SR-005`'s own remaining-uncertainty content (recorded in
  `security-recommendations.md`) is not narrowed further by this packet — DP-034 only decides that
  they are registered as an explicit P1-scope choice, not what closes each of them.

## Required changes

- Project State: record D1–D3 as the P1 credential-entry decision in §4; note OQ-007 as
  partially narrowed (dashboard write path resolved; worker-resolution scope stays open); note
  that DP-023's `SEC-006` waiver formally expires at this gate, superseded by D3's registry
  placement rather than by an implemented mitigation.
- Contract or schema: none in `PoC Contract 0.1` directly; a future revision should add an
  explicit credential-entry clause under §8 Operations if the general operator-action language
  does not already cover it.
- Acceptance tests: none by this packet. A `SEC` scenario asserting a submitted credential value
  never appears in an API response, error message, or log is M1/M5 implementation work.
- Migration or compatibility: none. No schema change; `~/.config/cosmai/env`'s format
  (`COSMA_SRC_<SOURCE_ID>_<PURPOSE>=value`) is unchanged from what `secret-setup.md` already
  documents.
- Implementation handoff: M1 builds the write endpoint; M5 builds the collector-domain screen's
  credential field against D1–D2. `SR-001`–`SR-005` stay registered, unimplemented candidates
  until a future packet or milestone adopts one, per D3.
- Forward links: `docs/conventions/secret-setup.md` and `docs/conventions/p0-security.md` each
  gain one line pointing to this packet, added in this same commit.

## Post-decision corrections

Appended, not a rewrite of the sections above.

- **`[정정, 2026-08-21, m7-fixwave, M-X6]` D1's own text still says the screen shows
  "whether it is currently set."** That was correctly removed from the shipped
  dashboard by `e2afd95` (M5): the credential write route is genuinely write-only
  with no "configured" status ever queryable anywhere (`docs/p1/M5-RECORD.md:414-424`,
  its own fixed-finding #4 — `apps/domain/api.py`'s `write_source_credential` never
  reads a value back, and no route reports whether a purpose is configured). The
  shipped `CredentialForm` shows "written this session" / "not written this
  session" from the component's own local state instead — a claim about this
  browser tab, never a claim about server state the component cannot see. M5-RECORD
  reconciles this well; only this packet's own D1 sentence was left saying the
  earlier, incorrect thing. See M-X6, `docs/agent-workflow/reviews/REVIEW-M2-M7.md`.
