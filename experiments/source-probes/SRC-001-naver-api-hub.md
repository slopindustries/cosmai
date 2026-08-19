# SRC-001 — NCP NAVER API HUB — Source Capability Profile

`[확인 사실]` **This profile was written after the integration, not before it.** P0-B B1 asks
for the profile to precede selection; in practice the collectors were built and run first and
this records what those runs measured. That order is a process failure and is recorded as one
in [`JUDGMENT-DEBT-2026-08-18.md`](../integrated-p0/JUDGMENT-DEBT-2026-08-18.md) rather than
disguised by back-dating. Every measurement below comes from a real run whose evidence is
linked, so the content is sound even though the sequence was not.

## Identity

- Candidate ID: `SRC-001`
- Acquisition mode: `REST_API`
- Provider or producer: NAVER Cloud Platform — NAVER API HUB
- Distributor, if different: same
- Endpoint or dataset page: `https://naverapihub.apigw.ntruss.com`
- Content channel or domain: Korean blog search, search-term trend, shopping-category insight
- Related experiment: [EXP-003](../integrated-p0/EXP-003-capability-layer.md)
- Profile captured at: 2026-08-19T06:34+09:00 (the runs); profile written 2026-08-19

## Rights and processing basis

- Terms or license URL and version/date: NCP service terms; API HUB product documentation at
  `https://api.ncloud-docs.com/docs/naver-api-hub-*`, fetched 2026-08-19
- Permitted experimental use: personal research and study, stated by the operator 2026-08-18
- Redistribution permitted: **`NO`** — the stated basis covers processing, not publication
- Agent processing permitted: `YES` — the same statement covers retrieval, local storage, and
  processing by this pipeline
- Attribution or deletion obligation: none recorded; not investigated, because redistribution
  is not sought
- Evidence and unresolved interpretation: `[확인 사실]` The two permissions are separate
  decisions under [`data-handling.md`](../../docs/conventions/data-handling.md) and the first
  does not imply the second. Every NAVER source row is registered `data_class = 'local'` and
  no payload is committed.

## Hard gates

| Gate | Result | Evidence or blocking reason |
|---|---|---|
| G1 — Access and rights permit the recorded P0 experiment. | `PASS` | Operator-stated basis covers processing; no redistribution is attempted |
| G2 — Data can be handled without exposing prohibited secrets, personal data, or restricted content. | `PASS` | Credentials resolve at the worker boundary from `~/.config/cosmai/env` (mode 600) and never enter the repository; `data_class = 'local'`; blog text is public-web content and is not redistributed |
| G3 — A representative sample can be retrieved or reconstructed with recorded identity, time, and hashes. | `PASS` (with one gap) | Two of three captures carry SHA-256 digests and snapshot manifests; the blog capture's digest was lost before it was written down and that is recorded as a gap rather than back-filled |
| G4 — The sample exercises at least one named P0 architecture question. | `PASS` | H2 (add-on capability boundary), H2a (atomicity), OQ-003 (Schema 0.x), OQ-010 (cursor), and DP-018/013 all have real-run evidence from these captures |
| G5 — Required access, volume, rate, and cost fit the P0-B timebox. | `PASS` | Free tier; the whole integration spent 2 of 25,000 daily search calls and 2 of 50,000 monthly Data Lab calls |

## REST API capability

- Authentication shape with secret excluded: two protected headers,
  `X-NCP-APIGW-API-KEY-ID` and `X-NCP-APIGW-API-KEY`. `[확인 사실]` This two-part shape is what
  [DP-018](../../docs/decisions/DP-018-credential-parts-and-attachment.md) was written for.
- Allowed HTTPS hosts: `naverapihub.apigw.ntruss.com` only
- Endpoint and method: `GET /search/v1/blog`; `POST /search-trend/v1/search`;
  `POST /shopping/v1/categories`; `POST /shopping/v1/category/keywords`.
  `[확인 사실]` The `POST` endpoints are why
  [DP-020](../../docs/decisions/DP-020-request-method-and-body.md) exists — the contract had
  no request body before them.
- Pagination or cursor behavior: blog search pages by `start` (1-based, ceiling 1000) and
  `display` (max 100). The Data Lab endpoints do not page: one request returns the whole
  requested window.
- Rate and quota behavior: `[측정]` Not observed. No run approached either quota, so
  `Retry-After` and throttling behaviour are **`UNKNOWN`** and remain so.
- Retry and `Retry-After` behavior: `UNKNOWN` — see above
- Response envelope: JSON. Blog search returns `{total, start, display, items[]}`; Data Lab
  returns `{startDate, endDate, timeUnit, results[{title, keywords[], data[{period, ratio}]}]}`
- Provider record identifier: blog — the post `link` URL; Data Lab — no record identifier
  exists, so `(series title, period)` is synthesised as one
- Event, publication, and update timestamps: blog — `postdate` (`yyyyMMdd`, day precision
  only); Data Lab — `period` (`yyyy-MM-dd`), the point's own date
- Correction and deletion behavior: `UNKNOWN` — not investigated
- Redirect behavior: `[측정]` None observed. Every request returned `200` directly.
- Observed schema or response drift: `[측정]` None across the runs, which spanned minutes and
  is far too short an interval to be evidence of stability.

## Measured data profile

- Sample identity and size: `[측정]` Search Trend 757 bytes → 14 items; Shopping Insight 423
  bytes → 7 items; Blog Search two envelopes → 10 items. Digests for the first two are in
  [`evidence/naver-real-data/README.md`](../integrated-p0/evidence/naver-real-data/README.md).
- Field profile: blog items carry `title`, `link`, `description`, `bloggername`,
  `bloggerlink`, `postdate`. `title` and `description` contain `<b>` markup around the
  matched term.
- Null counts or rates: `[측정]` None in the captured samples.
- Duplicate counts or rates: `[측정]` None in the captured samples. Blog `link` was unique
  across ten items; `(series, period)` unique across all Data Lab points.
- Invalid record counts or rates: `[측정]` None.
- Payload or row size distribution: `[측정]` 423–757 bytes per Data Lab response; blog items
  a few hundred bytes each.
- Time coverage: `[측정]` Data Lab windows are operator-chosen; the runs used seven weekly
  points. Blog search returns whatever is most recent and has no window control.
- Observed failures and limits: `[측정]` `SE01` on a malformed date window; `401` with a
  `200`-shaped body absent — the API returns a real `401` status. `[가설]`
  `collector.naver.blog`'s first assumption concerns a source that answers `200` with an
  error body; **this source does not do that**, so the assumption is untested here.

## Reproduction and artifacts

- Reproduction command: see *Retrieval procedure* in
  [`evidence/naver-real-data/README.md`](../integrated-p0/evidence/naver-real-data/README.md)
- Environment and versions: Python 3.13, PostgreSQL 18, `uv`; recorded in the same file
- Retrieval procedure: `--run-network --run-credential` gated pytest scenarios
- Original content hash and algorithm: SHA-256, recorded per capture
- Redistributable fixture or local-only metadata location: **no fixture is committed**;
  hashes and retrieval instructions only, per `AGENTS.md`'s rule for `data_class = 'local'`
- Redaction or transformation: none applied to Raw. Structural fixtures generated by
  [`tools/structural_fixture.py`](../../tools/structural_fixture.py) under
  [DP-022](../../docs/decisions/DP-022-structural-fixtures.md) carry shape without content.

## Recommendation

- Outcome: **`CONDITIONAL GO`**
- Conditions or blocking gates: redistribution is not permitted, so nothing captured may be
  committed; rate-limit and `Retry-After` behaviour is `UNKNOWN` and must not be described as
  tested.
- P0 questions this candidate can test: H2, H2a, OQ-003, OQ-010, DP-018's credential shape,
  DP-020's request body.
- Known representativeness limits: `[추론]` One provider, one authentication shape, three
  endpoints, and a few minutes of observation. Nothing here is evidence about sources that
  page deeply, throttle, redirect, drift, or report failure in a `200` body — and that last
  one is the case `accept_status` was built for.
- Proposed next action: none for P0. Any further characterisation belongs to P1.
