# Integrated P0

This directory contains the disposable Architecture Discovery Prototype for both P0-A and P0-B. Stage boundaries are governed by [DP-005](../../docs/decisions/DP-005-two-part-pre-p1-execution.md) and the [P0 Execution Plan](../../docs/p0-execution-plan.md).

## P0-A

Build only the source- and normalization-independent platform core:

- PostgreSQL runtime, migrations, and source-neutral transaction foundations;
- handler-neutral jobs, API and worker lifecycle, claims, leases, retries, terminal states, interruption, and recovery;
- source-neutral dashboard health, generic job state, logs, metrics, correlation, failure inspection, and safe retry;
- redaction, loopback, secret-store location guards, synthetic handlers, and platform failure injection.

P0-A must not explore or select sources or create acquisition, Raw, snapshot, or normalization contracts, ports, fixtures, test doubles, persistence, UI behavior, or implementations. Synthetic handlers may exercise generic success and failure behavior but must not imitate a collector, importer, Raw payload, snapshot producer, or normalizer.

`[결정]` **The P0-A gate is accepted `GO` as of 2026-08-17, with no conditions.** The record is [PLATFORM-CORE-GATE-2026-08-17.md](PLATFORM-CORE-GATE-2026-08-17.md), written from [PLATFORM-CORE-GATE-TEMPLATE.md](PLATFORM-CORE-GATE-TEMPLATE.md); the experiment behind it is [EXP-001](EXP-001-platform-core.md) and every `PASS` claim was put to an [adversarial review](ADVERSARIAL-REVIEW-2026-08-17.md) first.

`[측정]` **P0-B's capability layer is built, reviewed, and half repaired.**
[EXP-003](EXP-003-capability-layer.md) put a collector on the platform; the
[adversarial review of `27f712b`](ADVERSARIAL-REVIEW-2026-08-18.md) then returned three
blocking findings against it, two of them properties EXP-003 claimed and the code did not
have. As of 2026-08-18 the three blocking findings and the two major ones (F2, F3, F1, F5,
F4) are repaired test-first; **F6 to F10 are not**, and the review's work-items table says
which is which. Read it before building on the capability layer.

`[결정]` **The P0-B entrypoints are `python -m addon_host.worker` and `python -m
addon_host`**, not the `platform_core` ones. The platform entrypoints stay source-neutral
and run no add-ons — DP-008 D1 forbids `platform_core` from importing the add-on layer at
all — so each gained one source-neutral seam (`RegistryFor`, `create_app(extend=…)`) and the
add-on half lives in `addon_host`. Decisions taken under time pressure, and due for
re-evaluation rather than adoption, are in
[JUDGMENT-DEBT-2026-08-18.md](JUDGMENT-DEBT-2026-08-18.md) — including one **process
failure**, recorded as P1 there.

`[측정]` **The whole operator loop runs against the real NAVER API Hub.** As of 2026-08-19,
three collectors and two normalizers are installed and have each been exercised end to end —
registered source → `POST /collect` → worker → `POST /snapshots` → `POST /normalize` →
worker → `GET /results` → the dashboard screen those responses make:

| Add-on | API | Measured |
|---|---|---|
| `collector.naver.blog` | `GET /search/v1/blog` | 10 posts over 2 pages |
| `collector.naver.searchtrend` | `POST /search-trend/v1/search` | 14 points, 2 keyword groups × 7 weeks |
| `collector.naver.shoppinginsight` | `POST /shopping/v1/categories` | 7 points, 1 category × 7 weeks |
| `normalizer.naver.blog` | — | Schema 0.1 documents |
| `normalizer.naver.trend` | — | Schema 0.2 trend points |

Two decisions came out of that and are worth reading before extending any of it:
[DP-020](../../docs/decisions/DP-020-request-method-and-body.md) — the DataLab endpoints are
`POST` with a JSON body and the guard was `GET`-only — and
[DP-021](../../docs/decisions/DP-021-schema-0-2-trend-points.md), which records that
`project-state.md` §5's hypothesis 5 is **refuted in its strong form**: one schema carries a
common envelope across a document and a trend point, and no common content.

Read the gate's "What this gate does not claim" section before building on any of it. P0-A completion is not evidence that a real collector, dataset importer, Raw model, snapshot, or normalizer will work.

## P0-B

P0-B begins with bounded source exploration and selection. It then defines and implements the complete acquisition and normalization domain, runs the real-data and failure scenarios, and completes Architecture Synthesis, artifact disposition, `PoC Contract 0.1`, and the P1 reconstruction plan.

Source probe code remains under `experiments/source-probes/`; it is measurement code and must not be silently promoted into the integrated collector or importer.

Keep every disposable backend, dashboard, migration, and orchestration artifact inside this boundary so none can be mistaken for P1 application code. A gate decision must name the tested code revision and evidence; it cannot be inferred from code existence.

Create each integrated experiment from [`experiments/EXPERIMENT-TEMPLATE.md`](../EXPERIMENT-TEMPLATE.md). P0 may optimize for observability and experimental clarity over long-term maintainability, but it must not compromise source rights, secret handling, provenance, or result labeling.
