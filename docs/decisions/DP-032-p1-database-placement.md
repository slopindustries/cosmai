# DP-032 — Placing P1 on the shared PostgreSQL server, as its own database with the operating rules it must keep

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-21
- Owners: Project owner
- Owner confirmation: `CONFIRMED (project owner, 2026-08-21, brainstorming session — docs/superpowers/specs/2026-08-21-p1-reconstruction-design.md)`
- Carries forward: [DP-002](DP-002-project-identity-and-stack.md)'s `Primary database: PostgreSQL` (unchanged) and [DP-006](DP-006-p0a-platform-foundation.md) D4/D5 (numbered-SQL migrations, psycopg3 directly — reused, not re-adopted from scratch)
- Addresses: [DP-006](DP-006-p0a-platform-foundation.md) D2's own recorded limitation — "D2's passwordless cluster produces no evidence about authenticated database access... carried into the gate's 'Platform assumptions P0-B must challenge'" — `[확인 사실]` corrected 2026-08-21: this packet records the decision; the evidence DP-006 D2 asked for (a working authenticated connection, negative tests refusing a bad or missing password) is deferred to M1's provisioning and negative tests, not produced here. An earlier revision of this line said "Closes," which overstated what a document-only packet can close.
- Related Open Questions: none opened or closed by this packet
- Affected contracts: none in `PoC Contract 0.1` directly — no section names a database technology or deployment target; new M1 artifacts: `service-db.json` manifest, provisioning SQL. [`secret-setup.md`](../conventions/secret-setup.md) gains a forward-link line to this packet (Required changes), and D4 below records a short analysis of where `COSMA_DB_*` sits relative to that document's naming rule and invariant 2.
- Affected acceptance tests: none yet — implementation is M1 (provisioning and migrator)

## Decision question

DP-006 D2 ran P0-A's PostgreSQL as a repository-local, passwordless, Unix-socket-only cluster —
a choice DP-006 itself scoped to P0-A and flagged as producing "no evidence about authenticated
database access." P1 does not get to keep that placement: the owner has moved development onto a
shared PostgreSQL server that other services also use, and has supplied an operating-rules
document (outside this repository) that governs multi-service sharing of one PostgreSQL server.
That document's own stated scope is a service owning a **schema inside one shared database**; the
owner's actual instruction for P1 is a service owning its **own dedicated database on a shared
server** — one level up from what the document literally describes. What does P1 owe the
operating rules under that placement, and what changes about applying a schema-scoped rule set to
a database-scoped tenant?

## Candidates

1. Continue DP-006 D2's repository-local, passwordless PostgreSQL for P1 as well.
2. P1 owns a schema inside one shared database used by multiple services — the operating-rules
   document's literal described configuration.
3. P1 owns its own dedicated database `cosmai` on a shared PostgreSQL server, not a schema
   partition. (owner's selection — `plan.md` addendum, spec §4.2)

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: The operating rules' role-separation, timeout, startup-DDL, and instant-typing points (rules 0, 1, 5, 6, 9) generalize from "schema-within-one-database" to "database-within-one-cluster" without losing the protection their own reasoning sections name. | Restating a rule at the database-ownership level leaves open exactly the hazard the rule's reasoning section says it exists to close — for example, a runtime credential that is still its own schema/database owner, or a boot path that still runs DDL. |
| H2: A dedicated per-service database does not change the cluster-wide connection-budget arithmetic (rule 4) or the extension/cluster-setting central-management rule (rule 8). | `max_connections`, reserved-connection settings, or installed-extension state turn out to be scoped per-database rather than per-cluster on the actual shared server. |
| H3: PostgreSQL's own cross-database limits (no native foreign key across databases, no implicit joinable table without an extension) make rules 10–11's hazard (cross-service FK, shared table) structurally unavailable for P1's placement, not merely policy-forbidden the way it is for a schema tenant. | A component P1 needs turns out to require `postgres_fdw`, `dblink`, or an equivalent cross-database mechanism, reopening the hazard rules 10–11 describe. |

## Experiment

- Scope: no new experiment. This packet reads the owner-supplied operating-rules document
  (`/home/user1/github_prj/Main/postgresql-shared-database-operating-rules.md`, outside this
  repository), the reconstruction spec §4.2, and the already-recorded P0 database decisions
  (DP-002, DP-006 D2/D4/D5), and states what carries forward, what departs, and what needs a
  level-shift to apply.
- Environment and versions: as recorded in the cited sources, dated 2026-08-21.
- Input and fixture identity: the operating-rules document's numbered rules 0–14 and its
  "신규 서비스 도입 체크리스트"; spec §4.2's concrete values; DP-006's own text; `plan.md`'s
  addendum (owner's raw notes, repository root, untracked).
- Procedure: for each rule the brief names as binding, quote its regulatory content, state
  whether it applies unchanged, needs restating one level up (schema owner → database owner),
  or is structurally moot under P1's placement, and record which.
- Known limitations: this packet does not have access to the actual shared server (address,
  current `max_connections`, existing extensions, provisioning procedure) — see Remaining
  uncertainty. It summarizes binding points from the operating-rules document because that
  document lives outside the repository and cannot be linked as evidence; the summary is not a
  substitute for reading the source document at implementation time.

## Evidence

`[확인 사실]` The operating-rules document states its own scope directly: "이 문서는 여러 서비스가
**하나의 PostgreSQL database 안에서 서비스별 schema를 소유**하는 구성에 적용한다." Its literal
object is a schema within one shared database.

`[확인 사실]` `plan.md`'s addendum states the opposite configuration for P1 explicitly: "db내에서
스키마로 분할하는 것이 아닌 각자의 db를 갖는다는 점 유의. 다른 서비스들과 하나의 db를 논리적인
경계로 분할하여 같이 사용할 예정." — not a schema partition; each service, including `cosmai`,
gets its own database, and that placement is what shares the server (cluster) with other
services. The reconstruction spec §4.2 fixes the same placement: "공유 서버에 database `cosmai`,
schema `cosmai`(`public` 비움)."

`[추론]` PostgreSQL connections and several settings (`max_connections`,
`superuser_reserved_connections`, `reserved_connections`, installed extensions) are scoped to the
whole cluster, not to one database. A database boundary therefore does not remove P1 from the
operating-rules document's rule 4 (connection budgeting) or rule 8 (extension/cluster-setting
central management) the way a schema boundary would be expected to for access control — those
two rules apply to P1's placement unchanged, without a level-shift.

`[추론]` Rules 10 (no cross-service foreign key) and 11 (no shared table) describe a hazard —
one object jointly owned or referenced across two services' boundaries — that PostgreSQL cannot
express across two separate databases without an extension: a foreign key cannot target a table
in another database, and no table can be jointly populated from two databases without
`postgres_fdw`, `dblink`, or an equivalent. P1's dedicated-database placement makes the literal
violation structurally unavailable, which is a stronger position than the schema-tenant case the
rules were written for. `[가설]` This does not make the underlying discipline free: nothing
prevents a future `postgres_fdw` link from reopening the same hazard in a more roundabout form,
and this packet does not authorize one. Falsification: a future milestone requests exactly such a
link and finds no recorded decision governing it — which is precisely what this packet's
Remaining uncertainty names as open.

`[확인 사실]` Rules 0, 1, 5, 6, and 9 are written in schema-owner terms (`orders_owner`, schema
`orders`) but their stated reasons do not depend on schema being the isolation unit specifically:
rule 0's reason is about `USAGE`/`CREATE` grants and `search_path` trust; rule 1's is about a
`NOLOGIN` owner separating a DDL accident from a DML accident; rule 5's is about lock and
idle-transaction duration affecting the shared cluster; rule 6's is about repeated boot-time DDL
delaying other tenants; rule 9's is about instant-vs-local-calendar meaning. Restated with
`cosmai_owner`/`cosmai_migrator`/`cosmai_runtime` as roles and schema `cosmai` as P1's one
schema inside its own database, the same reasoning holds without alteration.

`[확인 사실]` The reconstruction spec §4.2 fixes the concrete values this packet records: roles
`cosmai_owner` (`NOLOGIN`) / `cosmai_migrator` / `cosmai_runtime`; runtime `statement_timeout`,
`lock_timeout`, `idle_in_transaction_session_timeout`; a `service-db.json` manifest plus
provisioning SQL, patterned on tubedepth's `deploy/postgres-bootstrap.sql`; migration via a
copied-and-adapted P0 SQL-file applier with the version table inside schema `cosmai` and every
DDL statement schema-qualified; a connection-budget draft of 16 (API 4, worker 4, scheduler 2,
migration 1, headroom 5) fixed with `CONNECTION LIMIT`; the P0 DDL table set (`job`,
`job_attempt`, `platform_effect`, `source`, `source_cursor`, `raw_envelope`, `raw_item`,
`snapshot`, `snapshot_item`, `normalized_result`) inherited plus three changes
(`raw_item.seq bigint generated always as identity` from DP-029 D2, the bytewise
manifest-ordering rule from DP-029 D3, and a new `schedule` table); instant-valued columns as
`timestamptz`; and DB credentials as `COSMA_DB_*` keys in the secret file.

`[확인 사실]` DP-006 D2 scoped its own passwordless, repository-local, Unix-socket-only
PostgreSQL to P0-A and named the gap this packet closes, in its own Tradeoffs and risks: "D2's
passwordless cluster produces no evidence about authenticated database access... recorded here as
a known limitation and carried into the gate's 'Platform assumptions P0-B must challenge.'"

`[확인 사실]` DP-006 D5 selected psycopg3 directly over SQLAlchemy Core for P0-A, reasoning that
"the query count is small enough that the abstraction pays for nothing." This packet's D3 keeps
the same tool for a different reason: P1 is reconstructing already-tested transaction-boundary
code (DP-010's fenced-completion transaction; the concurrency evidence DP-006 D3 built), and
adopting an ORM now would mean re-validating that logic rather than reusing it — a
reconstruction-specific cost DP-006 D5 did not have to weigh, because P0-A had no tested logic
yet to preserve.

## Decision

`[결정]` **D1 — P1 owns a dedicated database `cosmai` on the shared PostgreSQL server; it does
not partition a shared database by schema.** Internally, `cosmai` has exactly one schema, also
named `cosmai`; `public` stays empty of application objects. The owner-provided shared-DB
operating rules — a document outside this repository — bind at the points summarized below,
restated at the database-ownership level this placement actually uses (see Evidence for which
rules needed that restatement and which apply unchanged):

- **Role separation** (rules 0–1): `cosmai_owner` (`NOLOGIN`, schema and object owner),
  `cosmai_migrator` (`LOGIN`, deploy-time only, `SET ROLE` to owner), `cosmai_runtime` (`LOGIN`,
  DML only — no `CREATE`/`ALTER`/`DROP`/`TRUNCATE`/`REFERENCES`/`TRIGGER`).
- **Runtime lifetime limits** (rule 5): `statement_timeout`, `lock_timeout`,
  `idle_in_transaction_session_timeout` set on `cosmai_runtime`; the migrator and any long batch
  use a separate role or an approved session override rather than disabling the runtime
  defaults.
- **No startup DDL** (rule 6): the application boot path never runs `CREATE TABLE`/`ALTER`/`DROP`
  or extension installation; schema change is the reviewed migrator path only.
- **No cross-service FK, no shared table** (rules 10–11): P1 does not create a foreign key
  against another service's rows or a jointly-owned table. The dedicated-database placement
  makes the mechanical form of this hazard structurally unavailable rather than merely
  policy-forbidden (see Evidence H3) — the discipline is named anyway because an FDW-based
  workaround remains possible and is not authorized by this packet.
- **Instant typing** (rule 9): a column meaning a real-world instant is `timestamptz`;
  calendar-local meaning uses `date`/`time`/an explicit IANA zone column instead.

`[결정]` **D2 — Connection budget is 16, fixed by `CONNECTION LIMIT`**: API 4, worker 4,
scheduler 2, migration 1, headroom 5. This is a draft the M1 manifest records and can revise
before provisioning against the real server's `max_connections` and reserved-connection
settings; `service-db.json` and the provisioning SQL are M1 deliverables, not this packet's.

`[결정]` **D3 — The DB access stack is psycopg3 directly plus a SQL-file migrator, both copied
and adapted from P0** (DP-006 D4/D5). The migrator's version table lives inside schema `cosmai`;
every DDL statement is schema-qualified. Rejected alternative: SQLAlchemy Core — reconsidered
here (not merely inherited from DP-006 D5) because P1 is reconstructing DP-010's fenced-completion
transaction boundary and DP-006 D3's tested concurrency behavior; adopting an ORM would mean
re-validating that logic rather than reusing it.

`[결정]` **D4 — DB credentials are carried as `COSMA_DB_*` keys in the secret file** (spec §8:
`~/.config/cosmai/env`), not as DP-006 D2's passwordless local Unix socket. This is a stated
departure from P0-A, not an oversight: a shared server requires a password, and DP-006 D2 itself
named "no evidence about authenticated database access" as a limitation for P0-B/P1 to
challenge. `[확인 사실]` Corrected 2026-08-21: this packet is where that challenge is
**recorded as a decision** — the evidence itself (a working authenticated connection, a
negative test refusing a bad or missing password) is M1 provisioning and testing work, not
produced by this packet; an earlier revision said "this packet is where that challenge is
answered," which claimed evidence not yet produced.

`[확인 사실]` **Recorded analysis: `COSMA_DB_*` sits outside two of `secret-setup.md`'s existing
shapes, not one.** First, naming: `secret-setup.md`'s only named key convention is
`COSMA_SRC_<SOURCE_ID>_<PURPOSE>` for a *source* credential (`secret-setup.md:57` — `[확인 사실]` corrected 2026-08-21, N3: this was `:55` before round 1's own forward-link addition to that file shifted it down two lines); `COSMA_DB_*`
is a second, disjoint key family this packet adds, not an instance of that rule. Second,
lifetime: `secret-setup.md` invariant 2 requires a credential value to be "resolved at the point
of use and held only for the lifetime of that use" — read, as that document's own P0-B Worker
rules read it, at the granularity of one outbound request. A database credential, once used to
open a pooled connection, is held by that connection for the **pool's** lifetime — many requests,
not one — because reopening a connection per query is not how the psycopg3-direct approach D3
fixes actually works, and this packet does not propose changing that. `[결정]` This is recorded as a named,
P1-scoped **extension** of invariant 2's granularity — a second point of use (the connection
pool, not only the outbound request) and a second holding lifetime (pool lifetime, not request
lifetime) — not as a silent violation, and not as a change to invariant 2's own text, which
stands in `secret-setup.md` exactly as written. Whether the pool holds the value in a
`repr`-redacted wrapper for that lifetime, consistent with DP-018 D4's pattern for the worker
side, is M1 implementation work, not decided here.

## Rejected alternatives

- **Candidate 1 (continue DP-006 D2's repository-local, passwordless PostgreSQL).** Rejected:
  it does not exist on a shared, multi-tenant server, and the owner's plan explicitly moves P1
  onto one; DP-006 D2 itself recorded this as a gap for P0-B/P1 to challenge rather than as a
  permanent choice.
- **Candidate 2 (schema partition inside one shared database).** Rejected: `plan.md`'s addendum
  states the opposite explicitly ("스키마로 분할하는 것이 아닌 각자의 db를 갖는다는 점 유의"),
  and the operating-rules document's own rule 14 (extraction test) exists because schema
  partitioning inside one database is the harder case to later separate — a dedicated database
  sidesteps exactly the extraction risk that rule protects against. The cost is that the rule
  set is literally written for the other configuration, which is why D1 performs a level-shift
  restatement rather than quoting the document unchanged.
- **SQLAlchemy Core** (D3's rejected alternative). Rejected for the reconstruction-specific
  reason recorded there; the operating-rules document itself is neutral between hand-written SQL
  and an ORM-driven migration tool (rule 2: "프로젝트가 다른 Alembic 전략을 선택할 수는 있지만..."),
  so this rejection is this project's choice, not one the guide forces.

## Tradeoffs and risks

- Benefits: P1 sidesteps the "later extraction" hazard rules 10, 11, and 14 exist to manage,
  since no other service's rows are ever reachable from `cosmai`'s own connection at all; the
  role/timeout/startup-DDL discipline the operating rules require for a schema tenant is
  preserved even though P1 is a whole-database tenant, so P1 does not lose protection by not
  needing the schema-level form.
- Costs: this packet restates several of the operating rules one level up from how their own
  text is written (schema owner → database owner) — an interpretive step this packet performs,
  not one the source document states directly. A reader comparing this DP against the document
  line-by-line will not find an exact schema-for-database substitution spelled out there.
- Failure modes: rule 4 (connection budgeting) and rule 8 (extension/cluster-setting central
  management) are the two rules this packet did **not** reinterpret, because they are
  cluster-wide by nature and not affected by the schema-vs-database question. If the actual
  shared server's `max_connections`, reserved slots, or already-installed extensions conflict
  with the 16-connection draft or an extension P1 needs, that is a real conflict this packet
  cannot see without access to the server — Remaining uncertainty names it rather than assuming
  it away.
- Reversibility: high. Nothing in D1–D4 is implemented yet; M1 provisioning is where the
  manifest and SQL are actually written, and this packet's summary can be corrected against real
  provisioning access before that happens without touching any shipped code.

## Remaining uncertainty

- The shared server's actual address, its current `max_connections` and reserved-connection
  settings, and the procedure for requesting a new database and roles on it are unconfirmed. The
  brief for this packet itself defers this to the owner at M1 start, and this packet does not
  resolve it.
- Whether 16 connections is enough is a draft budget, not a measured one; nothing here exercises
  P1's actual worker/scheduler concurrency against it.
- Whether any already-installed cluster extension conflicts with one P1 needs is unknown until
  the server is inspected (operating-rules rule 8).
- H3's FDW-based workaround to rules 10–11 is not designed against by this packet; if a genuine
  need for cross-service query access arises later, it needs its own decision, not an assumption
  that "P1 has no foreign keys" already covers it.
- This packet summarizes the operating-rules document's binding points rather than reproducing
  it; the document itself, not this summary, is authoritative at implementation time for any
  point this packet did not restate (its rules 2, 3, 7, 12, 13, and its checklist and audit
  cadence sections are not repeated here because the brief scoped this packet to rules 0, 1, 5,
  6, 9, 10, 11, and 4).

### 2026-08-21 discharge (M1)

`[확인 사실]` The first Remaining-uncertainty bullet above ("the shared server's actual address...
unconfirmed") is discharged for M1's scope. The server is docker container `tubedepth-postgres`
(image `postgres:18-alpine`, PostgreSQL 18.6), reachable at `127.0.0.1:5433`; administrative work
runs as its `fleet` superuser over `docker exec` (container-internal trust, no password),
confirmed live with `docker ps` before provisioning. Provisioning was executed against it, not
merely designed: databases `cosmai`/`cosmai_test` (owner `cosmai_owner`), roles `cosmai_owner`
(NOLOGIN), `cosmai_migrator` (LOGIN, `CONNECTION LIMIT` 2), `cosmai_runtime` (LOGIN,
`CONNECTION LIMIT` 12), schema `cosmai` in each database, `CREATE` revoked from `PUBLIC` on
`public`. A negative test (`SET ROLE cosmai_runtime; CREATE TABLE cosmai.must_fail(...)` →
permission denied) and an authenticated loopback-TCP-with-password connection from `apps/` both
ran successfully against the live server — the "working authenticated connection, negative tests
refusing insufficient privilege" D4 named as still-owed evidence. Full evidence, including the
role-limit query output and the connection test's exact result, is recorded in
[M1-RECORD §a](../p1/M1-RECORD.md#a-provisioning-evidence); this discharge does not re-open or
narrow any of the remaining bullets above (the `max_connections`/reserved-connection settings,
whether 16 connections is enough, installed-extension conflicts, and the FDW hazard all remain
as recorded, unconfirmed by M1).

## Required changes

- Project State: record DP-032's D1–D4 as the P1 database-placement decision, alongside DP-002's
  unchanged "Primary database: PostgreSQL" and DP-006 D2's now-closed P0-A-only scope.
- Contract or schema: none in `PoC Contract 0.1` directly — no section currently states a
  database technology or deployment target; a future revision may add an explicit deployment
  section referencing this packet, but this packet does not add one.
- Acceptance tests: none by this packet. `service-db.json` manifest, provisioning SQL, migrator,
  and role/timeout/startup-DDL negative tests (per the operating-rules document's own "확인 방법"
  sections) are M1 implementation work.
- Migration or compatibility: none — no migration exists yet; the P0 DDL table set plus DP-029's
  three changes and the new `schedule` table are what M1's first migration set builds, not this
  packet.
- Forward links: [`secret-setup.md`](../conventions/secret-setup.md) gains one line pointing to
  this packet, added in this same commit.
- Implementation handoff: M1 provisions `cosmai_owner`/`cosmai_migrator`/`cosmai_runtime`, writes
  `service-db.json`, adapts P0's SQL-file applier with a schema-qualified version table, and
  confirms the connection-budget draft against the real server before fixing it with
  `CONNECTION LIMIT`.
