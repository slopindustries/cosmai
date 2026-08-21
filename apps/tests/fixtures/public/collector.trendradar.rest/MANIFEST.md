# Fixture provenance — `collector.trendradar.rest`

Per `docs/conventions/data-handling.md`'s `public` class: source, capture time, rights
basis, hash, and representativeness recorded here rather than left to be inferred.

- **Source**: trend-radar 1.0.0 dashboard JSON API, `http://127.0.0.1:8000/api/v1`
  (`docs/api.md` in `service/trend-radar`). This is COSMAI's own sibling project's
  development instance in this workspace — not a third party — running against its own
  collected rows.
- **Redistribution basis**: same repository family (`Main/service/*`), no external
  redistribution; the rows are trend-radar's own already-collected marketplace data
  (product names, prices, review text), captured here only to exercise
  `collector.trendradar.rest`'s parsing, pagination, and filters-echo logic offline. No
  credential was involved — `/api/v1` is unauthenticated by design.
- **Capture time**: 2026-08-21T02:0x UTC (see each response's own `captured_at`/`at`
  fields for the exact hour the underlying rows were collected at; the HTTP capture
  itself was made same-day, single session, unsandboxed shell against the live
  container `shared-db-trend-radar-dashboard-1`).
- **Environment**: trend-radar 1.0.0 (`GET /api/v1` `"version"` field), containerized,
  loopback-only, no TLS (`[측정]` confirmed below).
- **Transformation**: none. Each file is the exact response body `curl` received;
  no fields removed or reformatted.

## Files and hashes (sha256)

| file | endpoint + query | sha256 |
|---|---|---|
| `index.sample.json` *(not committed — see note)* | `GET /api/v1` | — |
| `runs.sample.json` | `GET /api/v1/runs?limit=10` | `aa0a0615788b07dab1d00a7304c4af50d7e64852708b2e8099d3f538300bec2b` |
| `sources.sample.json` | `GET /api/v1/sources` | `a0500bc790c6f87ad15d2dfb4ac81341887b99538c44830de2c25104bf7eeb54` |
| `rank_snapshot.unfiltered.json` | `GET /api/v1/records/rank_snapshot?limit=5` | `1bc81ecf90aaaa9c2119b96f85e7f0d6b9eb50b0dd251f65dd66190d46ee077a` |
| `rank_snapshot.daisomall.page1.json` | `GET /api/v1/records/rank_snapshot?source=daisomall&limit=5&offset=0` | `29d3755d2f990bbb06b54a1b3f1790687f642f27279f40c3c7b20ccba6a79a84` |
| `rank_snapshot.daisomall.page2.json` | `GET /api/v1/records/rank_snapshot?source=daisomall&limit=5&offset=5` | `7de87bf996164c3fa74cbbb88ea7dcedfedefc2fa8ca6afe00e4ca75df8074df` |
| `product.sample.json` | `GET /api/v1/records/product?limit=3` | `09168cd4d0c13cdb0f299293a886785134f26b96078bbc7dd0ccf7ce352ef94c` |
| `price_point.sample.json` | `GET /api/v1/records/price_point?limit=3` | `e5be528a9b46a0efdd160a4cc0627f317852a9fefc557cc443432d6fcf2ad33a` |
| `review.sample.json` | `GET /api/v1/records/review?limit=3` | `6c5960e0da7f8d889eab572ccbb853a654387e9897caa7904a189f7c388d55fe` |
| `review_stats.sample.json` | `GET /api/v1/records/review_stats?limit=3` | `97a57cc062cdcbb2d027b59da0bdb9e2cce56f3bd27c0845ae8a6e317a328504` |
| `review_answer.sample.json` | `GET /api/v1/records/review_answer?limit=3` | `1e711986191ebe21d1b24541d1769518aa831d5f5f882ae4d6135ed553253b7c` |
| `review_summary.sample.json` | `GET /api/v1/records/review_summary?limit=3` | `f6f7215e6d1a74aa04dc7489f6859e99db4ed4479a301600ed8cfc038dfaa89e` |
| `review_topic.sample.json` | `GET /api/v1/records/review_topic?limit=3` | `c1cff5366ba4238687df4e886130658af981897bc806c32c7304e34f2e721454` |
| `new_product.sample.json` | `GET /api/v1/records/new_product?limit=3` | `635d261881a6e3d960d768c2f41ff680bca0afeccf3a6a874872212f4441aff1` |

`index.sample.json` (`GET /api/v1`) was captured and inspected (service/version/endpoint
list) but is not committed — no test reads it, so it is retrieval-procedure-only:
`curl -sS http://127.0.0.1:8000/api/v1`.

## Representativeness

- The two `rank_snapshot` pairs together cover: the unfiltered shape (multiple sources
  and boards mixed in one page, descending `captured_at` order) and a `source`-filtered,
  offset-paginated pair (`page1`/`page2`), which is what the handler's own pagination
  and filters-echo checks are tested against.
- The nine `*.sample.json` files are one page each (`limit=3`) of every record table
  `collector.trendradar.rest` collects, enough to fix each table's row shape and to
  build synthetic multi-row/multi-page test fixtures from real field names and value
  types without re-hitting the live service for every test.
- **Not represented**: an empty page (`rows: []`, e.g. an exhausted table), a non-2xx
  response, and a `filters` echo that silently drops an unrecognized parameter — trend-
  radar's `/api/v1/records/{table}` never emits the last of these for a *recognized*
  key (`docs/api.md`: unrecognized keys are dropped, recognized PK-column keys are
  always echoed), so the silent-drop scenario the handler defends against is
  constructed synthetically in `apps/tests/test_collector_trendradar.py` rather than
  captured, by editing a copy of a real response's `filters` object.

## `[측정]` Scheme measured during this capture

`curl -sS http://127.0.0.1:8000/api/v1/health` succeeded over plain HTTP;
`curl -sSk https://127.0.0.1:8000/api/v1/health` failed with `SSL routines::wrong
version number` — the live instance speaks HTTP only, no TLS on `:8000`. Recorded here
because it is the fact behind this add-on's report concern about `domain.outbound`'s
HTTPS-only `ALLOWED_SCHEMES`; not itself a claim about a config field or a table.

## `[측정]` A captured_at filter 500s on the live instance

`GET /api/v1/records/rank_snapshot?captured_at=<any ISO 8601 form tried>` returned
`500 Internal Server Error` on every attempt (four encodings tried), while `source`
and `board` filters on the same table returned `200` with a correctly echoed `filters`
object. `board`-only and `source`+`board` combinations were also `200`. This is a
property of the live trend-radar instance, not of this add-on; `service/trend-radar`
is read-only to this project (per `AGENTS.md`) and was not modified or investigated
further. `handler.py`'s module docstring names this as the reason it never sends
`captured_at` as a request parameter, and relies on the API's own `captured_at DESC`
row ordering plus its own stored cursor instead.
