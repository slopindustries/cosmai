# DP-020 — Request method and body in the outbound guard

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-18
- Owners: Project team
- Extends: [DP-008](DP-008-addon-architecture.md) D4 and [DP-018](DP-018-credential-parts-and-attachment.md)
- Bumps: `addon_api` `CONTRACT_VERSION` 1.0 → 1.1 (additive)
- Related Open Questions: [OQ-001](../open-questions/OQ-001-source-capability.md) — this is source-capability evidence
- Affected contracts: `CollectContext.fetch`, `source.outbound_profile.endpoints`, `PreparedRequest`

## Decision question

`domain.outbound.resolve` builds a URL with a query string and `domain.transport._hop`
sends `"GET"`, hardcoded. `CollectContext.fetch(endpoint_ref, params)` has nowhere to put a
request body.

`[확인 사실]` Two of the three selected Naver API Hub endpoints are `POST` with a JSON body:

| API | Path | Method |
|---|---|---|
| Search — blog, news, cafe, web | `/search/v1/*` | `GET` |
| DataLab — Search Trend | `/search-trend/v1/search` | `POST`, JSON |
| DataLab — Shopping Insight | `/shopping/v1/*` | `POST`, JSON |

Fetched 2026-08-18 from `api.ncloud-docs.com/docs/naver-api-hub-search-trend` and
`.../naver-api-hub-shopping-insight-categories`.

So the platform cannot reach two thirds of the selected source without a decision about who
owns a request body.

## Decision

**D1 — The method belongs to the operator-approved profile, not to the add-on.** An endpoint
entry becomes either a string (a `GET` path, unchanged) or an object:

```json
"endpoints": {
  "blog":  "/search/v1/blog",
  "trend": {"path": "/search-trend/v1/search", "method": "POST"}
}
```

`[결정]` Same reasoning as DP-018 D2 and as hosts and paths already: an add-on that chose
its own method would be composing part of a request DP-008 D4 says it does not compose, and
an operator approving a source could not see whether it was granting a read or a write.
Only `GET` and `POST` are accepted; anything else is refused by name.

**D2 — The body belongs to the add-on.** `fetch` gains an optional `body` argument, and its
bytes are the add-on's.

`[추론]` This is the half worth arguing, because it looks like a widening of DP-008 D4 and
is not. What D4 protects is that the add-on cannot decide **where a request goes** — host,
port, path, scheme, credential. A body decides **what is being asked for**, which is exactly
what the query string already is and always has been: `resolve` accepts `params` from the
add-on today and percent-encodes them. Refusing a body while accepting a query string would
be drawing the line at the transport's spelling rather than at the property being protected.
`{"startDate": ..., "keywordGroups": [...]}` is a search term, not a destination.

**D3 — A body is bounded, and the bound is the platform's.** `[측정]` **As implemented it is not, and the note is kept here rather than in an errata.** `ADVERSARIAL-REVIEW-2026-08-19.md` F1 measured the check counting `len(body)` — elements, not bytes — so a `list[bytes]` of 1 MiB passes a 64 KiB grant. The decision stands; the implementation does not yet deliver it. `max_request_bytes` joins the
per-source limits, default 64 KiB, enforced in `resolve` before anything is sent. `[추론]`
`ADVERSARIAL-REVIEW-2026-08-18.md` F1 is the reason this is stated with the decision rather
than left for later: a limit that exists in a contract and in no counter is not a limit, and
this packet is where that lesson is cheapest to apply.

**D4 — A body on a `GET` endpoint is refused, and so is a `POST` with none.** Both are
`Refusal`s naming the endpoint. A `GET` with a body is legal HTTP that many servers ignore,
which makes it a request the operator approved and the add-on did not get; refusing is the
only outcome where what was approved and what was sent are the same thing.

**D5 — `Content-Type: application/json` is set by the platform for a `POST`.** The add-on
supplies bytes and does not name a media type. `[결정]` One media type in P0-B, because the
selected source uses one and a second would need a rule for which bodies may claim which —
falsified the moment a source needs a form encoding.

**D6 — `CONTRACT_VERSION` goes to 1.1.** Adding an optional parameter is additive, so every
existing `requires_contract = ">=1.0,<2.0"` add-on still loads and none has to change.

## What this does not decide

- **Idempotency and retry semantics of a `POST`.** The platform retries a transient failure,
  and a `POST` that partially succeeded is not distinguishable from one that did not.
  `[가설]` Both selected DataLab endpoints are reads expressed as `POST`, so a retry is
  harmless. Falsified by a selected source whose `POST` mutates anything.
- **`PUT`, `PATCH`, `DELETE`.** Refused by name. Nothing in P0-B needs them, and a write to
  a source is a different safety question that `p0-security.md` has not been asked.

## Falsification

| Claim | Falsified by |
|---|---|
| D2 — a body is the add-on's, like a query string | A source where the body carries routing rather than a question — a target URL, a host, a path |
| D5 — one media type is enough | A selected source needing form or multipart encoding |
| The `POST`-retry assumption | A selected `POST` endpoint that is not a read |
