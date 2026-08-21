# DP-033 — Widening the P1 operator surface: six screens, Raw made readable, exports made streamable, collection put on a schedule

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-21
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-21, brainstorming session — docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md)`
- Related Open Questions: [OQ-005](../open-questions/OQ-005-operations-contract.md) — partially answered. D1 fixes P1's screen set and D3 fixes the export shape; OQ-005's telemetry-detail and diagnosis-scenario questions stay open for M5/M6 implementation evidence, so OQ-005 itself does not close here. [OQ-008](../open-questions/OQ-008-operator-reexecution-authority.md) — explicitly **not** touched by this packet; stays `OPEN` (see Remaining uncertainty).
- Affected contracts: [`PoC Contract 0.1`](../../contracts/experimental/POC-CONTRACT-0.1.md) §8 Operations gains the six-screen set and the Raw-read action in its next revision; a new `schedule` table is not yet named in any contract.
- Affected acceptance tests: none by this packet. M5 (dashboard) and M6 (scheduler, downloads) implementation evidence is where `OPS` and `SEC` scenarios for these screens get written (spec §10); M5's dashboard tests must additionally assert that the data-browser screen renders a Raw payload as plain text only — never as interpreted markup — per D2's plain-text-rendering control, added 2026-08-21 (fix-wave repair of `REVIEW-GATE-M0` F4).

## Decision question

DP-006 D6 gave P0-A a three-screen, library-free dashboard because "a component library, a
data-fetching cache, and a router are answers to problems P0-A's three operator screens do not
have." `raw_summary` (`experiments/integrated-p0/domain/store.py:632`) refused to page Raw
payloads to an operator at all. Neither of those was revisited for P0-B's real sources, and the
owner's `plan.md` "원하는 목표" (six numbered goals) now asks for a dashboard that shows every
collected item per domain, lets Raw be exported by scope, gives normalization a management frame,
and manages exactly one collector per domain — plus recurring collection on a schedule
(`plan.md` §7.1, §원하는 목표 1–6). So: what is P1's operator surface — its screen set, whether
Raw payloads become readable, how exports are scoped and delivered, which frontend stack the
dashboard is built on, and whether collection runs unattended?

## Candidates

**Screen set (D1):**
1. Six screens: collector-domain, data browser, downloads, normalization management, job
   monitoring, health/metrics.
2. Keep P0-A's three screens and add only source-specific views as each add-on lands, with no
   fixed P1 set.
3. One combined screen mixing browsing, download, and normalization control.

**Raw payload visibility (D2):**
1. Keep P0-B's refusal: counts only, never payload bytes, on any operator screen.
2. Allow the data-browser screen to page the already-persisted, already-redacted Raw payload.
3. Allow Raw payload access only through a separate, audited export path — never inline in the
   dashboard.

**Downloads (D3):**
1. One format, no scope filter: a single full-table JSONL or CSV dump per source.
2. JSONL default for Raw (lossless, re-importable) plus a CSV option (metadata columns + a
   payload-string column); normalized results flattened to CSV; scoped by source, period, and
   `item_key` prefix; streamed rather than buffered.
3. A generic database-export tool (e.g. `pg_dump`-shaped) exposed through the dashboard.

**Dashboard stack (D4):**
1. Keep DP-006 D6's bare Vite + React + TypeScript + `fetch` foundation unchanged into P1.
2. Adopt MUI + React Router + TanStack Query — the stack named as a strong default in
   [Project State](../project-state.md) §4 Technology constraints.
3. Adopt only one of the three (e.g. a router without a component library).

**Collection scheduling (D5):**
1. No scheduler; every collection run stays operator-triggered, as P0-B already does.
2. A `schedule` table plus a scheduler process that creates `collect` jobs on interval;
   normalization stays manual-start, with an optional schedule layered on top.
3. A single scheduler drives both collection and normalization automatically end to end.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Six domain-oriented screens are sufficient for the P1 operator scenarios named in `plan.md`'s six goals, without inventing an unbounded set. | M5 finds a required operator scenario that needs a seventh first-class navigation object, which is exactly OQ-005 H1's own falsification condition, now applied to the six-screen answer. |
| H2: Paging the already-persisted Raw payload on the data-browser screen is acceptable without a body-level redaction mechanism, resting instead on the loopback operator boundary, plain-text-only rendering, and export data-classing (`[결정]` corrected 2026-08-21 — no body-level redaction mechanism exists to rest on, and the original H2 wrongly implied one). | A Raw payload page in M5 renders a body as interpreted markup rather than plain text, or a payload page is rendered where the boundary assumptions do not hold (the dashboard reachable by other than the single local operator, or a protected-header value appearing in a body rather than the already-stripped headers). |
| H3: Streaming, scope-filtered export (source, period, `item_key` prefix) satisfies `plan.md` goal 3 without buffering a full result set in memory. | M6's download implementation cannot complete a full-source export without holding the entire result set in process memory at once. |
| H4: The move from three P0-A screens to six P1 screens is, by itself, the "recorded reason" DP-006's adoption-vs-replacement rule requires before adopting a declined default — no contrary evidence is needed because nothing is being replaced. | A reviewer finds that these libraries are already "in use" in the DP-006 D6 sense, which would make this an unevidenced replacement rather than an adoption. |
| H5: A `schedule` table plus scheduler-created `collect` jobs satisfies `plan.md` goal 1 without changing the job or effect-key model `CONTRACT-JOB@0.1` already fixes. | A scheduled run collides with an in-flight or already-succeeded job for the same source and period in a way `effect_key` idempotency does not already resolve, forcing a job-model change. |

## Experiment

- Scope: no new experiment is run by this packet. It reads the owner's 2026-08-21 brainstorming
  session (`plan.md`, formalized as `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md`
  §5, §7, §8) together with P0's recorded evidence and decides.
- Environment and versions: none — a document-only milestone (M0), per the plan's own
  Architecture statement.
- Input and fixture identity: `plan.md` (owner's raw notes, repository root, untracked);
  `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md` §5, §7, §8, §9; P0-B's
  `raw_summary` docstring; [DP-006](DP-006-p0a-platform-foundation.md) D6; `Project State` §4.
- Known limitations: every claim below about what P1's dashboard needs is a decision made from
  the owner's stated goals and P0's recorded behavior, not from an M5 build that exists yet. None
  of H1–H5 is tested until M5/M6 implementation.

## Evidence

`[확인 사실]` `plan.md` "원하는 목표" goal 6 (repository root, untracked owner notes): collectors
are managed one per domain in the dashboard — the dashboard shows and operates on the jobs inside
each collector's own domain area. Goal 2 asks that everything collected per domain be fully
browsable with pagination. Goal 3 asks that raw data already collected be extractable
(downloadable) from the dashboard, filterable by scope, with the owner noting uncertainty about
which export format the database most easily supports. Goal 4 asks for a management frame for
normalization work, explicitly not full implementation yet. Goal 5 asks that a collector's
required secret or id be capturable through that collector's own dashboard screen. Goal 1 asks
for scheduled collection, status, and history to be visible per collector.

`[확인 사실]` `raw_summary` (`experiments/integrated-p0/domain/store.py:632`) returns counts and
a last-retrieved timestamp only, with its own docstring stating the refusal's rationale: *"A page
of Raw bodies on an operator screen is a page of unreviewed external text, and nothing in P0-B
needs one to answer 'did the collection do anything'."*

`[확인 사실]` [OQ-005](../open-questions/OQ-005-operations-contract.md) H1 names the P0-A
navigation model as "Sources, imports, jobs, snapshots, normalization runs, results, logs, and
metrics" and its own falsification condition is "A required operator scenario cannot be completed
without direct database inspection or an additional first-class object not represented by the
model." No Raw-payload-reading object is in that model.

`[확인 사실]` [DP-006](DP-006-p0a-platform-foundation.md) D6 declined MUI, TanStack Query, and
React Router for P0-A with the stated reason that "a component library, a data-fetching cache,
and a router are answers to problems P0-A's three operator screens do not have," and recorded
adoption as reversible and additive: "each library can be introduced in P0-B when a concrete need
appears."

`[확인 사실]` [Project State](../project-state.md) §4 Technology constraints, as clarified by
DP-006's acceptance: adopting a declined default requires only a recorded reason; replacing one
already in use requires contrary evidence. MUI, TanStack Query, and React Router remain unadopted
anywhere in P0, so their P1 adoption is the "recorded reason" case, not the "contrary evidence"
case.

`[확인 사실]` `docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md` §5.5: collection
scheduling is driven by a `schedule` row per enabled source, creating a `collect` job when
`next_run_at` is due; normalization stays manual-start with an optional schedule layered on top,
matching the operator-triggered run-creation pattern spec §6 UI already describes for
normalization ("select snapshot → select normalizer/version → create run").

`[추론]` DP-006 D6's own rationale was scoped to "P0-A's three operator screens." D1 below grows
that set to six, two of which (data browser, downloads) are the data-heavy, scope-filtered
screens the declined stack (a router for six destinations, a query cache for paginated and
filtered fetches, a component library for filter forms and tables) was built to serve. The same
sentence that justified declining the stack at three screens is what now supports adopting it at
six.

`[확인 사실]` [DP-018](DP-018-credential-parts-and-attachment.md) D3 ties every credential header
to `PROTECTED_HEADERS`, and `strip_protected_headers` removes them from a response's *headers*
before `raw_envelope` ever persists them. A Raw payload page therefore renders a payload whose
*headers* have already passed through that stripping step at collection time; D2 below does not
add, remove, or bypass that header-stripping step — it only exposes what is already stored.

`[확인 사실]` **Correction, 2026-08-21 (fix-wave repair of `REVIEW-GATE-M0` F4).** The paragraph
above, and D2's original wording below, called the *payload* "already-redacted." That is false:
`strip_protected_headers` (`experiments/integrated-p0/domain/outbound.py:698`) takes and returns
only a header mapping — its signature is `Mapping[str, str] -> dict[str, str]`. Its one production
call site (`domain/transport.py:269`) applies it solely to `dict(response.getheaders())` for the
`headers` field of `TransportResponse`; the same call passes `body` straight through, unexamined,
into the same object. No function anywhere in P0 redacts, strips, or inspects a response *body*
before it becomes `raw_item.payload`, and D2 below does not add one. `raw_summary`'s own
docstring, already quoted in this packet's Decision question, is the accurate description: *"A
page of Raw bodies on an operator screen is a page of unreviewed external text."* The corrected
D2 and its new third paragraph, below, state what actually makes reversing the refusal acceptable
without inventing a redaction mechanism that does not exist.

## Decision

`[결정]` **D1 — P1's operator surface is six dashboard screens.** Collector-domain screen (one
per domain — the management unit `plan.md` goal 6 names, status, schedule configuration, a
config form generated from the add-on manifest's config schema, credential entry per §8,
job history, and last successful collection); data browser (full, paginated, per-domain Raw item
listing with a payload preview); downloads (scope-filtered, streaming export, §D3); normalization
management (§6 of the spec — a management frame, not new normalization logic); job monitoring
(P0's screen carried forward: list, filter, detail, attempts, protected debug detail, retry);
health and metrics (P0's screen carried forward, plus scheduler status).

`[결정]` **D2 — The operator may read Raw payloads on the data-browser screen, reversing P0-B's
refusal, on the basis of a boundary and rendering control rather than a body-level redaction
control.** The refusal's own rationale — "nothing in P0-B needs one to answer 'did the collection
do anything'" — was true of P0-B's synthetic-adjacent scope; `plan.md` goal 2 now names a P1
scenario the refusal structurally blocks: browsing everything a domain collected. `[결정]`
**Correction, 2026-08-21:** this packet does not invent a body-redaction mechanism to answer that
scenario, because none exists to invent one from. What actually makes reversing the refusal
acceptable is three things, none of them a change to what the payload contains: (a) the loopback
operator boundary `p0-security.md`'s `SEC-005` and DP-023 already rely on — the dashboard binds
to loopback only, so the viewer is the single local operator, never an untrusted or external one;
(b) a new M5 implementation requirement this decision creates: the data-browser screen renders a
Raw payload as **plain text only** — never interpreted or rendered as HTML, Markdown, or any
other markup, so a payload cannot execute or link out of the page that shows it; and (c) a
screenshot or export taken from a payload page carries the payload's own data class under
[`data-handling.md`](../conventions/data-handling.md) (for example, Open Beauty Facts stays
`local` under [DP-027](DP-027-dataset-standard-and-share-alike.md) D4) — showing the bytes on a
screen does not reclassify them to a more permissive class. The existing header-stripping path is
unchanged — `strip_protected_headers` still runs on headers before persistence, and this decision
adds no new stripping step and removes none; it also adds no body-level control, because it does
not have one to add.

`[결정]` **What D2 does not cover, stated rather than smoothed over:** no body-level redaction
exists anywhere in P0 or in this decision. `strip_protected_headers` never receives a body and is
not extended to one by this packet. A Raw payload page is, as `raw_summary`'s own docstring
already said, a page of unreviewed external text; D2 does not change that sentence — it decides
that sentence describes an acceptable local-operator-only, plain-text-rendered exposure, not a
reason to keep refusing. Separately, and unchanged from the original text: the data-class
determination that applies once a payload leaves the local operator boundary — through an export
shared externally, or if the dashboard is ever exposed beyond loopback under
[RC-007](../roadmap-candidates.md) — is not re-decided here. Each source keeps whatever class
`data-handling.md` and its own registration already assigned; any future external-exposure
decision must examine that separately.

`[결정]` **D3 — Downloads are scope-filtered and streamed.** Scope conditions are source, a date
period, and an `item_key` prefix. Raw exports default to JSONL (payload lossless, directly
re-importable) with a CSV option (metadata columns plus a single payload-string column).
Normalized results export as flattened CSV. All exports stream rather than buffer a full result
set.

`[결정]` **D4 — The dashboard adopts MUI, React Router, and TanStack Query.** This is the
[Project State](../project-state.md) §4 registered default stack, declined for P0-A by DP-006 D6
and not adopted anywhere in P0-B. The basis is the screen-count increase from three to six —
DP-006's own recorded reason for declining no longer applies once two data-heavy, multi-route,
filter-driven screens exist. Under DP-006's adoption-vs-replacement rule this is an adoption
(nothing built on the declined stack is being replaced), so a recorded reason is the bar, not
contrary evidence — and this paragraph is that record.

`[결정]` **D5 — Collection runs on a schedule; normalization stays operator-triggered, with an
optional schedule.** (`[확인 사실]` corrected 2026-08-21 — an earlier headline read "normalization
does not," which contradicted this same decision's own body below and the spec's "수동 시작 유지
+ 선택적 스케줄.") A `schedule` table holds
one row per source with an interval and a `next_run_at`; a scheduler process creates a `collect`
job when a schedule is due. The dashboard exposes per-source interval configuration and an
enable/disable toggle. Normalization keeps its existing operator-triggered pattern (select
snapshot, select normalizer and version, create run) with scheduling added only as an option on
top of that manual path, not as a replacement for it — the accepted P0-B principle stays as it
was.

## Rejected alternatives

- **D1 Candidate 2, no fixed P1 screen set.** Rejected: it answers OQ-005's H1 by deferral rather
  than by naming a model, and `plan.md`'s six goals already give six concrete destinations — not
  naming them here would just move this decision into M5 without adding information.
- **D1 Candidate 3, one combined screen.** Rejected: the owner's goals separate browsing (goal 2)
  from export (goal 3) from normalization control (goal 4) as distinct concerns with different
  scope-filter shapes; collapsing them would make each screen's filter state ambiguous about
  which concern it belongs to.
- **D2 Candidate 1, keep the refusal.** Rejected: it leaves `plan.md` goal 2 unanswerable from the
  dashboard, which is exactly the "direct database inspection" fallback OQ-005's exit condition
  says the accepted operator scenarios must not need.
- **D2 Candidate 3, payload only through a separate audited export.** Rejected as the *only*
  path: the download screen (D3) already serves that role for bulk, scoped extraction; adding
  inline paging on the data browser is what actually answers goal 2's "browse everything,
  paginated" request, and D3's export path remains available alongside it.
- **D3 Candidate 1, one format with no scope filter.** Rejected: `plan.md` goal 3 explicitly asks
  for scope-conditioned download, and a full-table dump does not compose with a source that
  collects continuously — the export would grow unbounded and unfilterable.
- **D3 Candidate 3, a generic database-export tool.** Rejected: it exposes a capability broader
  than the operator scenario needs (arbitrary schema access, not source-scoped Raw or normalized
  rows) and reopens exactly the "direct database inspection" path OQ-005 treats as the fallback of
  last resort, not a delivered feature.
- **D4 Candidate 1, keep the bare foundation.** Rejected: DP-006 D6's own stated condition for
  revisiting — "when a concrete need appears" — is met by D1's screen count, and hand-rolling
  routing, data fetching, and form/table components across six screens repeats work the declined
  libraries exist to remove, for no offsetting benefit now that the condition has changed.
- **D4 Candidate 3, adopt only one library.** Rejected: the three defaults were declined together
  in DP-006 D6 for one reason (screen count), and that reason applies to all three at once —
  splitting them would need a per-library reason this packet has no evidence for.
- **D5 Candidate 1, no scheduler.** Rejected: `plan.md` goal 1 explicitly asks for regular
  collection, and P0-B's manual-trigger-only model cannot produce "정기 수집" (periodic
  collection) without an operator remembering to run it.
- **D5 Candidate 3, schedule normalization automatically too.** Rejected: the spec's own §5.5 and
  §6 keep normalization manual-start as "the accepted principle," and nothing in this session
  revisited that; automating it would be a separate, unaddressed decision about trusting
  unattended normalization output.

## Tradeoffs and risks

- Benefits: OQ-005's screen-set question gets an answer instead of remaining a P0-A-only
  hypothesis; all six of `plan.md`'s "원하는 목표" goals get a named landing screen; adopting the
  registered default stack removes the cost of hand-rolling routing and data fetching across six
  screens; the scheduler closes the gap between "P0-B collects when told to" and goal 1's
  "collects regularly."
- Costs: D2 reintroduces on an operator screen exactly the thing P0-B's refusal was written to
  avoid — "a page of unreviewed external text" — and that text is now whatever each of the five
  P1 add-ons collects, unreviewed by this packet. D4 adds three real frontend dependencies that
  DP-006 explicitly deferred and that produced no P0 evidence about their fit. D5 adds a new
  table and a new always-running process (the scheduler) that P0 never had.
- Failure modes: a reader could take D2 to mean the dashboard is now safe for an untrusted or
  external viewer — it is not; [RC-007](../roadmap-candidates.md) records dashboard
  authentication as a precondition for any exposure beyond loopback, still unadopted. A reader
  could take D5 to mean normalization is now scheduled by default — D5 states plainly that it is
  not.
- Reversibility: D1, D3, D4 are additive (new screens, new libraries) and reversible by removal.
  D2 is a read path over data already persisted, rendered as plain text under the loopback
  boundary rather than through any body-level redaction (`[결정]` corrected 2026-08-21 — no such
  redaction exists); reversible by removing the view without touching what is stored. D5 adds one
  table and one process; reversible by disabling
  all schedules, which returns every source to the manual-trigger model P0-A and P0-B already
  used.

## Remaining uncertainty

- [OQ-008](../open-questions/OQ-008-operator-reexecution-authority.md) stays `OPEN`. D5's
  scheduler creates a new `collect` job per due schedule; it does not re-execute a job that
  already succeeded, so it does not by itself answer OQ-008. But a scheduled run against a source
  whose previous run already succeeded for an overlapping period is close to the case OQ-008's own
  "Why this cannot be decided yet" section anticipated for P0-B ("a collection run that succeeded
  against stale upstream data... are cases where re-executing succeeded work is the operator's
  actual intent"); M6 should record whether that case actually arises once scheduling is real,
  rather than this packet asserting it does not.
- Whether six screens remain sufficient once M4's eight or nine add-ons (`[확인 사실]` corrected
  2026-08-21, fix-wave round 3, D3 — M4 builds four or five collectors, one importer, and three
  normalizers; see `P1-RECONSTRUCTION-PLAN.md`'s M4 row) and the source track are fully
  connected — OQ-005 H1's own falsification condition — is untested until M5.
- Whether streaming, `item_key`-prefix-scoped export is adequate at the volumes trend-radar and
  tubedepth will actually produce is unmeasured; `plan.md` goal 3 itself states the owner does not
  know which export format the database most easily supports.
- D4 is an adoption decision, not evidence. DP-006 D6's declination produced no P0 evidence about
  MUI, React Router, or TanStack Query's fit for this project, and this packet does not produce
  any either — it only records that the reason to decline no longer holds.

## Required changes

- Project State: record D1–D5 as the P1 operator-surface decision in §4; note OQ-005 as
  partially answered (screen set, export shape) with its telemetry-detail and diagnosis-scenario
  parts still open; note OQ-008 explicitly unresolved.
- Contract or schema: `PoC Contract 0.1` §8 Operations should gain the six-screen set and the
  Raw-read action in its next revision; a `schedule` table is new schema, not yet named in any
  contract.
- Acceptance tests: none by this packet. M5 (dashboard screens, Raw browser) and M6 (scheduler,
  download streaming) implementation is where `OPS` and `SEC` scenarios for these screens are
  written, per spec §10's "신규" list (adapter contract tests, scheduler, download streaming,
  secret write path).
- Migration or compatibility: a new `schedule` table (M1/M2 migration); no change to existing P0
  tables from this packet alone.
- Implementation handoff: M5 builds the six screens including the Raw browser against D1–D2; M6
  builds streaming export against D3 and the scheduler against D5; both build the frontend against
  D4's adopted stack rather than DP-006 D6's bare foundation.

## Post-decision corrections

Appended, not a rewrite of the sections above — `docs/conventions/project-memory.md`'s
own rule for a packet already accepted.

- **`[정정, 2026-08-21, m7-fixwave, M-X5]` H5's falsification condition names the
  wrong mechanism.** H5 above is framed entirely on `CONTRACT-JOB@0.1`'s
  `effect_key` idempotency ("without changing the job or effect-key model...
  already fixes"). What M6 actually built for duplicate suppression
  (`apps/scheduler/store.py`'s `non_terminal_job_exists`, a lock-held check for
  a `PENDING`/`RUNNING` job with the same handler and `source_id`) is
  unrelated to `effect_key` — that mechanism lives at
  `apps/platform_core/jobs/store.py:376-379` and fences the *effects of one
  running job's own attempts*, not whether a second job gets created at all.
  `grep -rn effect_key docs/p1/` finds no mention connecting the two. H5 was
  therefore never actually evaluated against the mechanism M6 built — the
  scheduler's suppression is real and tested (M6-RECORD's own evidence
  section), but nothing in this record or M6-RECORD checked it against H5's
  stated condition, because that condition describes a different mechanism.
  Separately, this section's own "Remaining uncertainty" bullet above asked M6
  to record whether the OQ-008 case (re-executing already-succeeded work)
  actually arises once scheduling is real, rather than this packet asserting
  it does not. `docs/p1/M6-RECORD.md:107-111` holds that answer without
  naming OQ-008: `test_a_terminal_job_does_not_suppress_the_next_pass`
  confirms a `SUCCEEDED` job does **not** suppress the next scheduled pass —
  meaning a scheduled run against a source whose previous run already
  succeeded for an overlapping period **does** create a new collect job. That
  is exactly the case OQ-008 asks about; M6's own evidence answers it (the
  case arises), and this note is the connection that was missing. See M-X5,
  `docs/agent-workflow/reviews/REVIEW-M2-M7.md`.
