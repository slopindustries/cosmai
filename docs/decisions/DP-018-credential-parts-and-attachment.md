# DP-018 — Credential parts, and where the platform attaches them

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-18
- Owners: Project team
- Supersedes: nothing. Extends [DP-008](DP-008-addon-architecture.md) D4 and D6 with the vocabulary they left out.
- Resolves: [OQ-009](../open-questions/OQ-009-credential-shape.md) for P0-B, on the evidence of one source
- Related Open Questions: [OQ-007](../open-questions/OQ-007-credential-scope.md) — narrowed, not closed
- Affected contracts: `source.outbound_profile`, `addon_api` manifest `[declares].needs_credential`
- Affected acceptance tests: the `SEC` outbound cases, and the first real-data collector run

## Decision question

An add-on declares that its source needs a credential. How does the platform learn what
shape that credential has, and where each part of it goes in an outbound request?

`[확인 사실]` Nothing answered this. `Declarations.needs_credential` is one boolean,
`source.credential_ref` is one nullable column, and no code path attached a credential to
anything. The first real collector — `collector.naver.blog` — needs **two** header values,
and said so in its own module docstring rather than in a contract.

## Decision

**D1 — A credential is a set of named parts, and a part is a key name plus a header name.**
The source's `outbound_profile` gains a `credentials` array:

```json
"credentials": [
  {"header": "X-NCP-APIGW-API-KEY-ID", "ref": "COSMA_SRC_NAVER_BLOG_CLIENT_ID"},
  {"header": "X-NCP-APIGW-API-KEY",    "ref": "COSMA_SRC_NAVER_BLOG_CLIENT_SECRET"}
]
```

`ref` is a secret-store key name and follows `secret-setup.md`'s existing
`COSMA_SRC_<SOURCE_ID>_<PURPOSE>` convention. It is never a value.

**D2 — The mapping lives in the operator-approved outbound profile, not in the manifest.**
OQ-009 H2, adopted. An add-on that named its own header would be describing the wire format
of a request DP-008 D4 forbids it to compose, putting one fact in two places that can
disagree. `[결정]` The manifest keeps `needs_credential` as a *request*; the profile is the
*grant*, exactly as it already is for hosts and endpoints.

**D3 — Every credential header must be a protected header.** A header name that
`domain.outbound.PROTECTED_HEADERS` does not carry is refused when the profile is read.
`[추론]` This is the load-bearing half of the decision. `strip_protected_headers` is what
keeps a credential out of `raw_envelope.response_headers`, and it works from a fixed list;
a source free to name any header could name one that is attached on the way out and
recorded on the way back. Tying attachment to that list makes "attached" and "stripped" the
same set by construction rather than by two people remembering.

**D4 — Resolution happens at the worker boundary, per request, through one function.**
`domain.secrets.resolve_credential(ref)` reads the store named by `COSMA_SECRET_SOURCE` at
the point of use and returns a value wrapped in a type whose `repr` is redacted. There is no
resolver interface and no provider abstraction — `secret-setup.md` says so and gives the
reason: a second secret source does not exist yet, and an abstraction over one instance
reduces no named uncertainty.

**D5 — An unresolvable credential is `CONFIGURATION_INVALID`, never a retry and never an
anonymous request.** `[측정]` **Narrower in the code than in this sentence.** `ADVERSARIAL-REVIEW-2026-08-19.md` F2 measured two adjacent doors the platform leaves open: an add-on declaring `needs_credential` against a profile granting none sends an anonymous request, and any non-2xx response is stored as Raw with the job `SUCCEEDED`. The protection covers a *named but unresolvable* credential and nothing else. `secret-setup.md` invariant 4. A collector whose credential is missing
must not fall back to an unauthenticated request that a source might answer with a `200` and
an error body.

**D6 — The add-on never learns that attachment happened.** `fetch` takes an endpoint name
and returns a response with protected headers already stripped. No `CollectContext` field
names a credential, a header, or a ref. DP-008 D4 is unchanged by this packet; this is how
it is kept while a real request is authenticated.

## Evidence and reasoning

`[확인 사실]` Naver API Hub authenticates with two headers, documented at
`https://guide.ncloud-docs.com/docs/apihub-overview` (fetched 2026-08-18). That is the one
real source examined.

`[추론]` OQ-009 says a single example cannot settle the general shape, and that is still
true — this packet is `ACCEPTED_FOR_POC` on one example and is expected to move. What makes
it safe to adopt now is that **the two-part header case is a strict superset of the one-part
case** an ordinary `Authorization: Bearer` source needs, so nothing here has to be undone to
serve the simpler shape.

### What this deliberately does not decide

- **Query-parameter and signed-request credentials.** OQ-009 H1's falsification condition.
  A source needing one is refused rather than served by a guess. `[가설]` No P0-B source
  needs one; falsified by the second source selected.
- **Which refs a given worker may resolve.** That is [OQ-007](../open-questions/OQ-007-credential-scope.md)
  and stays open. P0-B resolves any ref a registered source names, which is the widest
  possible answer and is recorded as such rather than as a decision.
- **Rotation, expiry, and multi-tenant authorization.** Non-goals in `p0-security.md`.

### Why not the alternatives

- **Header names in the manifest.** Rejected under D2. It also means an operator approving
  a source cannot see what the request will carry without reading the add-on's source.
- **One `credential_ref` column, with the add-on splitting it.** The add-on would hold a
  credential value to split it. Directly forbidden by DP-008 D4.
- **A `credential_type` enum — `bearer`, `api_key`, `ncp` — with the platform knowing each
  shape.** Every new source is then a change to `platform_core`'s vocabulary, which is the
  coupling the add-on layer exists to remove.

## Consequences

- `source.credential_ref` keeps its column and its CHECK constraint and **grants nothing.**

  `[측정]` This bullet said the column *"becomes the single-part convenience form: a profile
  with no `credentials` array and a source with a `credential_ref` is read as one part
  filling `Authorization`."* Nothing implemented that, found 2026-08-19 while repairing F2,
  and it should not be implemented. Filling `Authorization` from a bare `credential_ref`
  means **the platform guessing a header nobody approved for that source** — a worse version
  of the mistake D2 forbids an add-on, because at least an add-on's guess would be visible in
  its manifest. A source that needs a credential says which header it fills, in the
  `credentials` array, where an operator approved it.

  The column stays because its `source_credential_ref_is_a_key_name` CHECK is real evidence
  about what a `credential_ref` is, and dropping a constraint to tidy a shape is the wrong
  trade. It is a name the schema knows how to check, not a grant.
- The dashboard's source form must show `ref` names and never offer a value field.
- `tests/environment` gains a guard that no committed profile names a header outside
  `PROTECTED_HEADERS`.

## Falsification

This packet is wrong if any of the following is observed:

| Claim | Falsified by |
|---|---|
| A credential is a set of header parts | A selected P0-B source needing a query parameter, body field, or computed signature |
| The mapping belongs to the profile | Two sources of one add-on needing different header names for the same part — which this packet *permits*, so the falsifier is the opposite: an add-on that cannot be written without knowing its header names |
| Protected-header membership is the right constraint | A real source whose credential header must also be visible in recorded Raw for debugging |
