# OQ-014 — Whether acquisition leaves this service and becomes something we read over REST

- Status: `RESOLVED`
- Priority: P1 candidate — an architecture choice, not a P0-B implementation task
- Owner: Project team
- Blocks: the Architecture Synthesis; `PoC Contract 0.1`; the P1 reconstruction plan
- Related: [OQ-013](OQ-013-addon-responsibility-boundary.md), [DP-008](../decisions/DP-008-addon-architecture.md), [DP-018](../decisions/DP-018-credential-parts-and-attachment.md), [DP-020](../decisions/DP-020-request-method-and-body.md)
- Resolution Decision Packet: [DP-012](../decisions/DP-012-independent-scraper-services.md), accepted 2026-08-19 on `agent/operating-model` — before this question was written, and without seeing it

## Question

`[확인 사실]` Today the NAVER collectors run **inside** this service. An add-on composes a
request, the platform resolves and opens the connection from an operator-approved outbound
profile, and the response becomes Raw in the same process and the same job attempt.

The proposal, recorded 2026-08-19: move acquisition **out**. A separate service talks to the
NAVER API on its own schedule and accumulates what it collects. This service then holds only
that external service and a **simple collector that reads the accumulated data over REST**.

Should acquisition leave, and if so, at which seam?

## Why this surfaced

`[측정]` [OQ-013](OQ-013-addon-responsibility-boundary.md) measured what the add-on layer
actually carries: 235–292 lines per collector, of which 13–15% is source-independent
plumbing duplicated because the layer rule forbids sharing it, and 165 identical lines
between the two DataLab collectors. `[추론]` The pressure the proposal names is real and
measured. What the measurement also shows is that **the source-specific 85% does not shrink
by moving** — roughly 250 lines per source relocate rather than disappear.

`[확인 사실]` The proposal has a name in the existing contract already.
`addon_api/manifest.py:375` refuses a manifest where `kind == "importer"` declares hosts or
endpoints, because *"an importer receives no network capability"*. The project has therefore
already written down the shape of an add-on that consumes data someone else acquired.

`[확인 사실]` [DP-008](../decisions/DP-008-addon-architecture.md) considered **subprocess
add-ons with OS-level isolation** as Candidate 4 and rejected it *"for now on cost"*, while
recording that an in-process add-on is trusted code and that isolation is contractual and
test-enforced rather than enforced by the operating system. `[추론]` This proposal reaches
the same isolation goal at a different seam — one acquisition service rather than one
subprocess per add-on — and so is a live answer to a question DP-008 deferred rather than a
new direction.

## Scope

### Included

- Whether the internet-facing request belongs in this service at all.
- Which seam: our side as a **collector** with an outbound profile naming one internal host,
  or as an **importer** reading a store with no network capability.
- What the boundary contract must carry for provenance to survive the extra hop.
- Where the outbound control that exists today is rebuilt, if acquisition leaves.

### Excluded

- Building it. `[결정]` See the interim position: this is recorded as an architecture
  candidate, not started as P0-B work.
- The duplication inside `addon_host/capabilities.py`, and `job.claim_conflict`. Neither is
  affected by where acquisition runs.

## What it buys

- `[추론]` **Rate limits and quota stop competing with job scheduling.** The accumulating
  service paces itself against the source; this service reads whatever has accumulated. Two
  cadences that are genuinely different stop sharing one scheduler.
- `[추론]` **The HTTP-200-that-is-a-failure problem is solved rather than relocated.** We
  author both sides of the boundary, so the boundary need not repeat the source's habit of
  reporting failure in a 200 body. [OQ-013](OQ-013-addon-responsibility-boundary.md)'s second
  clause becomes enforceable *at the boundary*, where today it is a judgment only the add-on
  can make.
- `[추론]` **The duplication OQ-013 measured dissolves on the far side.** The external service
  is not bound by the add-on layer rule, so its own internal sharing is a free choice.
- `[추론]` **A parsing defect in one source can no longer stop the platform worker.**
- `[추론]` **Contractual isolation becomes process isolation**, which is what DP-008 said it
  wanted and could not afford.

## What it costs

- `[측정]` **The outbound control does not travel with it, and that control is the strongest
  thing P0-B built.** The platform resolves host, port, path, and method only from an
  operator-approved row, attaches credentials at the worker boundary, revalidates every
  redirect, and bounds bytes and time. The independent security review could not route a
  request outside the grant. `[측정]` That same code had four defects in one day — an element
  count used as a byte bound, a write phase outside its own deadline, a dot-segment redirect
  bypass, an unenforced page limit — every one caught RED. `[추론]` A service that makes the
  real internet requests needs that control rebuilt, and the defect record says building it
  is not cheap. Externalizing without rebuilding it does not reduce exposure; it moves
  exposure to where nothing is watching.
- `[확인 사실]` **Our own service's output becomes untrusted input by the project's own rule.**
  `AGENTS.md`: *"Treat imported datasets as untrusted Raw input regardless of their claimed
  normalization level."* Authorship does not exempt it.
- `[추론]` **Provenance has to cross the hop explicitly.** `AGENTS.md` requires preserving
  provenance and lossless Raw. Raw would be produced outside this repository, so the boundary
  contract must carry the source URL, capture time, and the original payload, or provenance
  ends at the boundary and the far side becomes the unverifiable authority.
- `[추론]` **Credentials move to the external service.** `SEC` handling, `credential_ref`
  resolution, and [DP-018](../decisions/DP-018-credential-parts-and-attachment.md) all describe a
  worker boundary that would no longer be where the credential is used.
- `[추론]` **It is a second system to run and observe** during a phase whose stated job is to
  choose an architecture rather than to operate one.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Acquisition and consumption have genuinely different cadences, so separating them removes real pressure. | Measurement shows the collectors never contend for scheduling and never approach a source rate limit — in which case the separation buys decoupling nobody needed. |
| H2: The reading side collapses to one small add-on regardless of how many sources exist behind the boundary. | A second source behind the boundary forces a second reading add-on, or the reading add-on grows source-specific branches. |
| H3: The outbound control can be carried across by making the external service a *client* of the operator-approved profile rather than a replacement for it. | The external service needs a grant the profile cannot express, or two copies of the resolution logic prove unavoidable. |
| H4: The boundary contract can carry provenance losslessly. | A field required by `data-handling.md` cannot survive the hop, or the far side must be trusted for a claim this side cannot check. |
| H5: The relocated 85% is cheaper to maintain outside than inside. | The external service re-grows the same duplication OQ-013 measured, now without the layer guard that made it visible. |

## Alternatives

- **Stay in-process.** Today's shape. Keeps one outbound control and one provenance chain;
  keeps the measured duplication and the in-process trust boundary.
- **External service, this side a collector over REST.** The proposal as stated. This side
  keeps its outbound profile, now naming one internal host — the guard survives and its grant
  becomes trivial to state. The internet-facing guard must be built on the far side.
- **External service, this side an importer.** No network capability at all on this side, per
  `manifest.py:375`. Strongest separation; requires a delivery channel that is not HTTP and
  makes the far side wholly responsible for provenance.
- **Subprocess add-ons.** DP-008's Candidate 4. Reaches process isolation without a second
  service or a network hop, and keeps the outbound control where it already works.

## Minimum experiment

- Measure whether the pressure H1 names exists: run the three collectors at realistic
  cadence and record scheduling contention and distance from the source's rate limit. `[확인
  사실]` No collector has yet reached a NAVER rate limit, so this is unmeasured.
- Write the boundary contract for one source and check every field
  `docs/conventions/data-handling.md` requires against it. Provenance either survives on
  paper or it does not, and that costs nothing to find out.
- Express the outbound grant for the external service under H3 and see whether the existing
  `OutboundProfile` shape can state it without a second resolver.

## Interim position

`[결정]` **Record as an architecture candidate; do not build it during P0.**

`[추론]` `AGENTS.md` states P0's mission as building evidence that lets the team *choose* the
architecture, and forbids long-lived application code before the P1 Entry Gate accepts
`PoC Contract 0.1`. An acquisition service is a long-lived component and a choice, not
evidence. Building it now would spend P0 operating an architecture instead of measuring one,
and would create precisely the durable dependency the P0 boundary exists to prevent.

`[결정]` Sequencing: [OQ-013](OQ-013-addon-responsibility-boundary.md)'s clause C lands
first. `[추론]` An add-on judgment that nothing can check is worse, not better, once the
judgment is made in another service — and the mechanism that makes a judgment reportable is
the same mechanism a boundary contract would need. Settling it inside the current shape
produces the vocabulary the boundary would be written in.

## Exit condition

The Architecture Synthesis can state whether acquisition belongs in this service, at which
seam, what the boundary contract carries, and where the outbound control lives under each
alternative — with H1 measured rather than assumed.

## Resolution

`[확인 사실]` **Answered by [DP-012](../decisions/DP-012-independent-scraper-services.md),
which decided the same question on the same day.** DP-012 was accepted on
`agent/operating-model` while this question was being written on the domain branch; neither
document cites the other because neither existed to the other. DP-012 selects the second
alternative below — the external service, with this side a collector over REST — and its
Candidate 1 is this question's "stay in-process".

`[결정]` **This question closes rather than competing with an accepted packet.** Two records
of one question, one `ACCEPTED` and one `OPEN`, is not a disagreement a reader can act on. The
material this question holds that DP-012 does not is its **measurement**, and that is carried
into DP-012 as falsification input rather than kept here as a rival opinion. What survives:

- H5's falsification condition — the relocated 85% re-growing the same duplication outside,
  now without the layer guard that made it visible — is the risk DP-012's H1 does not cover
  and is now recorded there.
- H1 is still **unmeasured**. DP-012 assumes cadence separation buys something; nothing in P0
  measured contention or rate-limit proximity. That gap moves to DP-012's experiment section.
- The sequencing note stands: [OQ-013](OQ-013-addon-responsibility-boundary.md)'s clause C
  lands before an adapter is written, for the reason given above.

`[추론]` Closing this does not make DP-012 more certain than it is. It makes the record say
once what it was saying twice.
