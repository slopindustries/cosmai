# DP-006 — P0-A Platform Foundation Choices

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-17
- Owners: Project team
- Related Open Questions: OQ-005, OQ-006, OQ-007
- Related experiments: [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md)
- Closes: DP-003 remaining uncertainty "Process entrypoints for API, worker, and dashboard"; DP-003 remaining uncertainty "PostgreSQL and Node project files, deferred to P0 entry"
- Affected contracts: [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md)

## Decision question

A1 requires closing the repository, toolchain, local PostgreSQL, Node, and test-runner readiness gaps before A2 can produce platform evidence. Which concrete foundation does P0-A build on, and which of DP-002's named strong defaults does it decline?

Every choice below is either a gap DP-003 explicitly left open or a departure from a default DP-002 recorded as "subject to P0 evidence." None of them is a permanent product commitment.

## Acceptance status

`[결정]` **Accepted 2026-08-17**, at the P0-A Completion Gate, with the reading in the next section accepted and one required change recorded below.

It was written before the work it governs, so that no consequential choice was resolved silently, and it stayed `DRAFT` through execution while the evidence showing whether each choice held accumulated in [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md). All eight decisions held. D4's and D5's arguments were never tested against the friction they predicted, because no schema evolution and no complex query arose in one day — that is a limit on the evidence, not a defect in the decision.

## A tension with Project State, stated rather than assumed away

`[확인 사실]` [Project State](../project-state.md) section 4 **said, before this packet was accepted**: *"Framework and library selections such as FastAPI, SQLAlchemy, Alembic, HTTPX, React Router, TanStack Query, and MUI are strong P0 defaults but remain replaceable if an experiment produces contrary evidence."* The sentence has since been clarified as this packet's required change; it is quoted here as it stood, because the tension below is what prompted the clarification.

D4, D5, and D6 decline Alembic, SQLAlchemy, and three frontend libraries **without** contrary evidence. Read strictly, that sentence sets a bar this packet does not clear, so the reading it relies on is recorded here for the gate reviewer to accept or reject rather than left implicit.

`[추론]` The sentence governs **replacing a default that is in use**. None of these is in use; no application code exists at all. The question A1 actually faces is adoption, not replacement, and adoption is governed by a different accepted rule — AGENTS.md's *"Avoid abstractions that do not reduce a named uncertainty."* [DP-002](DP-002-project-identity-and-stack.md)'s own "Scope and reversibility" section supports this reading: it calls these "strong defaults subject to P0 evidence," which describes evidence as the thing that settles them rather than as a precondition for declining them.

`[추론]` The asymmetry is deliberate and in the project's favour. Adopting a default costs configuration time now and produces no evidence about whether it was needed. Declining one costs a later import if P1 wants it. Under [DP-001](DP-001-p0-lifecycle.md), P1 is reconstructed from contracts rather than from this code, so a P0-A decision not to adopt a library constrains P1 not at all.

**If the reviewer rejects this reading, the correct outcome is to adopt the named defaults in P0-A, not to keep the choice unrecorded.** That is why the tension is written down instead of resolved in a commit message.

`[결정]` **The reviewer accepted this reading on 2026-08-17**, and asked additionally that the sentence itself be clarified so the ambiguity does not recur. [Project State](../project-state.md) section 4 now separates the two questions explicitly: adopting a default is optional and needs a recorded reason, while replacing one already in use needs contrary evidence. That matters for P0-B, which meets the same question again with FastAPI and HTTPX.

---

## D1 — Module layout and process entrypoints

### Problem

`[확인 사실]` `pyproject.toml` sets `[tool.uv] package = false` and `[tool.pytest.ini_options] pythonpath = ["."]`.

`[확인 사실]` The directory name `integrated-p0` contains a hyphen, which is not a valid Python module name. With the current configuration there is no way to import P0-A code from a test.

### Decision

`[결정]` P0-A code lives in an importable root named `platform_core` **inside** the experiment directory, and pytest's path configuration is extended to reach it.

```text
experiments/integrated-p0/
  platform_core/          import root
    __init__.py
    config.py             configuration loading and validation
    obs/                  structured logging, redaction, correlation, metrics
    db/                   connection, migration applier, migrations/*.sql
    jobs/                 state machine, claim/lease/retry, handler registry
    handlers/             synthetic handlers and failure injectors
    api/                  operator HTTP API
    worker.py             worker process entrypoint
  tests/                  executable P0-A tests, disposable with the experiment
  dashboard/              Vite + React + TypeScript
  evidence/               gate evidence, committed
```

```toml
pythonpath = [".", "experiments/integrated-p0"]
testpaths = ["tests", "experiments/integrated-p0/tests"]
```

`[결정]` Executable P0-A tests live under `experiments/integrated-p0/tests/`, not under the repository's `tests/` tree.

`tests/README.md` assigns three roles: `acceptance/` holds promotable scenario **documents**, `fixtures/` holds classified inputs, and `environment/` holds tests of the repository itself which are explicitly not promotion candidates. Executable P0-A tests are none of these — they are disposable P0 code, and DP-001 requires P0 code to stay under `experiments/integrated-p0/`. Placing them in the repository `tests/` tree would blur the promotion boundary that `tests/README.md` exists to draw.

The boundary guard and the module-layout test remain under `tests/environment/`, because they verify the repository's own guards rather than platform behavior.

`[결정]` Process entrypoints are `python -m platform_core.worker` and `python -m platform_core.api`. This closes the entrypoint uncertainty DP-003 left open.

### Rationale

The name `platform_core` describes the P0-A boundary rather than the product, so nothing at the repository root becomes importable and DP-003's core protection is preserved: no module named after the product exists for P0 code to accumulate inside. DP-001's prohibition on P0 becoming a P1 runtime dependency is unaffected — the import root is reachable only through pytest's path configuration and the two `-m` entrypoints, both of which disappear with the experiment.

`experiments/source-probes/` has the same hyphen problem and will reuse this pattern in P0-B.

### Rejected alternatives

- **Rename the directory to `integrated_p0`.** Would work, but the hyphenated name is referenced by DP-001, DP-005, the P0 Charter, the Execution Plan, AGENTS.md, and the experiment README. The rename cost exceeds the benefit.
- **Import through `importlib` machinery.** Works without configuration changes but makes every test file carry loader boilerplate.
- **Declare a real package.** Directly contradicts DP-003.

### Reversibility

Full. Removing the second `pythonpath` entry and the directory removes every trace.

---

## D2 — PostgreSQL runtime: repository-local, passwordless, Unix socket only

### Problem

`[확인 사실]` `flake.nix` provides the PostgreSQL binaries only. No cluster, data directory, port, or startup procedure exists.

`[확인 사실]` `config/env.example` lines 29–35: *"A connection string carrying a password is a credential. Store it here by key and resolve it through `credential_ref`; do not pass it as an environment variable."*

`[확인 사실]` `docs/conventions/secret-setup.md` "Stage boundary": credential resolution and `credential_ref` authorization belong to P0-B. P0-A verifies only the store location, permissions, redaction, and configuration-failure behavior.

`[추론]` If P0-A used a password-bearing database URL, that URL would be a credential by the project's own definition, and P0-A would have to implement the `resolve_credential` function that `secret-setup.md` assigns to P0-B. A passwordless local connection is the only configuration that satisfies both documents at once.

### Decision

`[결정]` P0-A runs a repository-local PostgreSQL cluster with no password, reachable only through a Unix domain socket.

- `PGDATA` is `var/postgres/`, which is already gitignored (`/var/`) and already excluded from ruff (`extend-exclude = ["var"]`).
- The socket directory is `PGDATA` itself. `listen_addresses = ''` — the cluster exposes no TCP port at all.
- `initdb --auth=trust` with the invoking OS user. No role password is ever set.
- `scripts/with-database.sh` is the launcher, following the shape of the existing `scripts/with-secret-source.sh`: validate, prepare, export, `exec`.
- The launcher exports `COSMA_DB_HOST` (the socket directory), `COSMA_DB_NAME`, and `COSMA_DB_USER`. These are local configuration, not credentials, so they do not belong in the secret store — `config/env.example` states that non-credential local configuration is out of scope for it.

`[결정]` `COSMA_DB_URL` is not used in P0-A. The commented example in `config/env.example` describes the P0-B case where a connection string carries a password.

### Rationale

This is stronger than the loopback-binding requirement the charter asks for: a cluster with `listen_addresses = ''` has no network surface to bind incorrectly. It also removes the credential question from the platform core entirely, which is what keeps P0-A inside its declared boundary.

`.gitignore` already contains `/var/` and `[tool.ruff] extend-exclude` already contains `var`. The repository anticipated a local runtime directory; this decision uses it rather than inventing a location.

### Rejected alternatives

- **Docker or Podman Compose.** Introduces a new mandatory dependency for every contributor while reducing no named uncertainty. DP-003 rejected making Nix a prerequisite for the same reason; a container runtime is the same class of coupling.
- **A password-protected cluster with the URL in the secret store.** Would drag P0-B's `resolve_credential` into P0-A and produce credential-handling evidence that OQ-007 explicitly defers.
- **A system-wide PostgreSQL on port 5432.** Couples the experiment to machine state outside the repository and makes the environment non-reproducible from the checkout.

### Reversibility

Full. The cluster lives under an ignored path and is deleted with the directory. Nothing in the schema or query layer depends on the socket transport.

---

## D3 — Test isolation and concurrency evidence are separate mechanisms

### Problem

Conflating these two makes A3 unrunnable.

| | Purpose | Requirement |
|---|---|---|
| Test isolation | Concurrently running tests must not corrupt each other's state | Each test worker needs its own database |
| Concurrency evidence | A3 must show that two workers cannot hold conflicting active ownership of one job | Multiple worker processes against **one** database |

### Decision

`[결정]` Test isolation uses a template database. A session-scoped fixture creates `cosma_p0_template` and applies migrations once; a worker-scoped fixture issues `CREATE DATABASE cosma_p0_<worker> TEMPLATE cosma_p0_template`. `pytest-xdist` is added to the development dependency group.

`[결정]` Concurrency evidence uses a dedicated fixture that starts real worker processes against a single database, marked with a `concurrency` pytest marker. It is not an isolation mechanism and must not be confused with one.

### Rationale

Template-database cloning is fast because PostgreSQL copies files rather than replaying migrations. Without it, A3's concurrency scenarios cannot be re-run cheaply, and a failing concurrency test cannot be iterated on.

### Reversibility

Full. Both are test infrastructure.

---

## D4 — Migrations: numbered plain SQL, not Alembic

### Decision

`[결정]` Migrations are numbered plain SQL files under `platform_core/db/migrations/`, applied in filename order by a small applier that records applied versions in a `schema_migrations` table.

### Rationale

`[확인 사실]` DP-002 lists Alembic as a strong default subject to P0 evidence.

`[확인 사실]` `docs/project-state.md` section 5 lists six architecture hypotheses. None of them concerns migration tooling.

`[추론]` Alembic therefore reduces no named uncertainty in P0-A, while adding `env.py` wiring, autogenerate configuration, and an interaction with `package = false` that must be solved before the first table exists. AGENTS.md: *"Avoid abstractions that do not reduce a named uncertainty."*

The charter requires a "migration mechanism," not a specific tool. A numbered-SQL applier is a migration mechanism, and the SQL itself is more legible as gate evidence than a generated Python migration.

### Rejected alternatives

- **Alembic.** The named default. Declined for the reason above; revisit in P1, where schema evolution over time is a real requirement rather than a hypothetical one.
- **No migrations, `CREATE TABLE IF NOT EXISTS` at startup.** Cheaper still, but the charter explicitly requires a migration mechanism and P0-B will add tables.

### Reversibility

Full, and cheap: P0-A is expected to have a small number of migrations. Adopting Alembic later means importing the same SQL as an initial revision.

---

## D5 — Data access: psycopg3 directly, no ORM

### Decision

`[결정]` P0-A uses psycopg 3 directly. SQLAlchemy is not adopted.

### Rationale

Same reasoning as D4. `[확인 사실]` DP-002 lists SQLAlchemy as a strong default subject to P0 evidence, and no architecture hypothesis concerns it.

`[추론]` P0-A's queries are few and centre on `FOR UPDATE SKIP LOCKED`, lease expiry predicates, and an idempotent insert. These are exactly the statements where an ORM's generated SQL becomes something the reader must reconstruct — and the gate reviewer has to read them to judge OQ-006's H2. Hand-written SQL is the more legible evidence.

### Rejected alternatives

- **SQLAlchemy Core.** A reasonable middle ground. Declined because the query count is small enough that the abstraction pays for nothing in P0-A.
- **SQLAlchemy ORM.** Adds identity-map and session-lifetime semantics on top of the transaction boundaries P0-A is trying to observe directly.

### Reversibility

Full. P1 is reconstructed from contracts, not from this code.

---

## D6 — Dashboard dependency floor

### Decision

`[결정]` The P0-A dashboard uses Vite, React, TypeScript, and the platform `fetch` API. MUI, TanStack Query, and React Router are not adopted in P0-A.

`[결정]` DP-002's `[결정]` "Dashboard language and UI foundation: React with TypeScript" is unchanged and remains in force.

### Rationale

`[확인 사실]` `docs/project-state.md`: *"Dashboard control, logs, metrics, and debugging evidence are part of P0 instrumentation."* The Execution Plan states dashboard observability is experimental instrumentation, not deferred visual polish.

`[추론]` A component library, a data-fetching cache, and a router are answers to problems P0-A's three operator screens do not have. Each is a strong default DP-002 kept precisely so it could be declined when unneeded.

### Rejected alternatives

- **Adopt the full default stack now.** Would consume timebox on configuration that produces no `OPS` evidence.
- **Serve HTML from the API and skip React.** Cheaper, but contradicts DP-002's accepted `[결정]`.

### Reversibility

Full and additive; each library can be introduced in P0-B when a concrete need appears.

---

## D7 — mypy strict applies to P0-A code

### Decision

`[결정]` `[tool.mypy] strict = true` continues to apply to `experiments/integrated-p0/` without a per-directory relaxation.

### Rationale

`[확인 사실]` `experiments/integrated-p0/README.md` permits P0 to optimize for observability and experimental clarity over long-term maintainability, which would justify relaxing it.

`[추론]` The concurrency code is where P0-A's real risk sits, and it is also where type errors around optional rows, timestamps, and connection lifetimes are cheapest to catch statically. The permission to relax exists; using it here would trade the wrong thing.

### Reversibility

Full. A per-directory override is a three-line change if strict typing measurably slows the work.

---

## D8 — The meaning of a generic durable effect

### Problem

The charter's P0-A exit criterion requires that *"duplicate execution does not produce an uncontrolled platform-level durable effect."* At the same time, DP-005 and the gate template forbid synthetic handlers from imitating a collector, dataset importer, Raw payload, snapshot producer, or normalizer.

`[추론]` The exit criterion cannot be tested without some durable effect, so the shape of that effect must be fixed deliberately rather than improvised during implementation. An improvised one drifts into a Raw store.

### Decision

`[결정]` The only durable effect a P0-A synthetic handler produces is a row in `platform_effect`:

```sql
create table platform_effect (
  effect_key text primary key,
  job_id      uuid        not null references job(id),
  applied_at  timestamptz not null default now(),
  payload     jsonb
);
```

`[결정]` The following constraints are part of the decision, not implementation detail:

- `effect_key` is chosen by the handler and is independent of the attempt number. It is the entire idempotency mechanism.
- `payload` is an opaque synthetic value. It carries no schema, no provenance fields, no identity semantics, and no version. Giving it structure would make it a Raw envelope.
- The table is never named or aliased with domain vocabulary. `observation`, `record`, `item`, and `document` are prohibited names.
- No second durable-effect table is created in P0-A.

The full semantics are specified in [CONTRACT-JOB@0.1](../../contracts/experimental/CONTRACT-JOB-0.1.md) and enforced mechanically by `tests/environment/test_p0a_boundary_guard.py`.

### Rationale

This gives the exit criterion something real to test while keeping the deferred-domain inventory in the gate honestly empty. The constraint that `payload` stays structureless is what prevents P0-A from accidentally answering a P0-B question.

### Reversibility

The table is disposable with the rest of P0. What survives is the recorded observation about where the idempotency boundary belongs, which P0-B tests against real effects.

---

## Tradeoffs and risks

- **Benefit:** every A1 readiness gap closes with a choice that is recorded, justified against an accepted document, and cheap to reverse.
- **Cost:** D4, D5, and D6 decline three of DP-002's named defaults. If P1 adopts them after all, P0-A produced no evidence about them.
- **Risk:** D1's `platform_core` name could be misread as a P1 foundation, the same failure mode DP-003 identified for the root manifest.
- **Control:** the name lives inside `experiments/integrated-p0/`, DP-001 governs its disposition, and the artifact disposition register in P0-B assigns it `ARCHIVE_REFERENCE_ONLY` by default.
- **Risk:** D2's passwordless cluster produces no evidence about authenticated database access.
- **Control:** recorded here as a known limitation and carried into the gate's "Platform assumptions P0-B must challenge."

## Remaining uncertainty

- Whether the numbered-SQL applier remains sufficient once P0-B adds domain tables.
- Whether `platform_effect`'s single-table idempotency boundary survives contact with a real durable effect in P0-B. This is the substance of OQ-006 H1.
- CI environment, still undefined. DP-003 listed it and this packet does not close it.

## Required changes

- [x] Clarify [Project State](../project-state.md) section 4 so that adopting a library default and replacing one already in use are separate questions with separate bars. Done 2026-08-17 as the condition of this packet's acceptance.

## Change record

| Version | Date | Change | Evidence or decision |
|---|---|---|---|
| Draft | 2026-08-17 | Initial draft, written before the work it governs | EXP-001 |
| Accepted | 2026-08-17 | `ACCEPTED_FOR_POC`. All eight decisions held under execution; the adoption-versus-replacement reading accepted; Project State section 4 clarified as the required change | [P0-A Completion Gate](../../experiments/integrated-p0/PLATFORM-CORE-GATE-2026-08-17.md), [EXP-001](../../experiments/integrated-p0/EXP-001-platform-core.md) |
