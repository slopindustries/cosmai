# OQ-009 — How a source's credential is declared and attached

- Status: `OPEN`
- Priority: P0-B — blocks the first collector that actually authenticates
- Owner: Project team
- Blocks: `credential_ref` semantics for multi-part credentials, the platform's outbound header attachment, the dashboard's credential form
- Related experiments: [EXP-002](../../experiments/integrated-p0/EXP-002-addon-layer.md)
- Resolution Decision Packet: not created

## Question

An add-on declares that its source needs a credential. How does the platform learn
**what shape that credential has** and **where each part of it goes** in an outbound
request?

## Why this surfaced

`[확인 사실]` Found on 2026-08-18 by the first author to write a real collector against
the contract, before any credential was resolved. Naver API Hub authenticates with
**two** header values:

```
X-NCP-APIGW-API-KEY-ID:  <client id>
X-NCP-APIGW-API-KEY:     <client secret>
```

`[확인 사실]` The contract has no vocabulary for this.
`addon_api.manifest.Declarations.needs_credential` is a single boolean.
`ConfigField.secret` marks a field as belonging in the secret store rather than in the
source row, but nothing states whether a secret field **is** a credential part, which
outbound header it fills, or what a source needing two of them does.

`[확인 사실]` `docs/conventions/secret-setup.md` names `credential_ref` as one key name
following `COSMA_SRC_<SOURCE_ID>_<PURPOSE>`, and `<PURPOSE>` reads as though it were
meant to distinguish several — but nothing says a source may hold more than one
`credential_ref`, and `domain`'s `source` table has exactly one column for it.

## Why this cannot be decided yet

`[추론]` The one real source examined so far needs two header values. One source is not
enough to tell whether that is the general case, an outlier, or the beginning of a
longer list — a source using OAuth, a signed request, or a query-parameter key would
each push in a different direction. Choosing now would fix the shape from a single
example.

`[추론]` It also interacts with [OQ-007](OQ-007-credential-scope.md). If a source may
hold several credential parts, "which credential may a worker resolve" becomes "which
*parts*", and the scoping question changes shape with it.

## Scope

### Included

- How an add-on declares that its source needs a credential, and of what shape.
- How a stored secret reaches a specific outbound header, query parameter, or signature.
- Whether one source may hold more than one `credential_ref`, and what the `source` row
  and the dashboard form look like if it can.
- What an add-on may know about its credential. `[결정]` It still never sees a **value** —
  DP-008 D4 is not in question here.

### Excluded

- Secret manager product selection, rotation, and multi-tenant authorization. These are
  non-goals in [P0 Security Baseline](../conventions/p0-security.md).
- OAuth flows, refresh tokens, and request signing, unless a selected P0-B source
  requires one.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: A source's credential can be described as a small set of named parts, each filling one named header. | A selected source needs a credential in a request position headers cannot express — a query parameter, a body field, or a computed signature. |
| H2: The mapping from a part to its header belongs in the **source's outbound profile**, which the operator approves, rather than in the add-on's manifest. | An add-on cannot be written without knowing the header names, or two sources of the same add-on need different header names for the same part. |
| H3: One `credential_ref` per part, following the existing `COSMA_SRC_<SOURCE_ID>_<PURPOSE>` naming, is enough. | Expressing a source's credential requires structure a flat set of key names cannot carry. |

`[추론]` H2 is the one worth stating early. If the header names live in the manifest,
an add-on is describing the wire format of a request it is forbidden to compose, which
would put the same fact in two places. If they live in the approved outbound profile,
the platform holds the whole of the request's shape — which is what
`p0-security.md` already assigns to it.

## Alternatives

- **One boolean and one credential.** Today's contract. Cannot express Naver.
- **Named parts in the manifest**, each declaring its header. Simple, and puts wire
  format in the add-on.
- **Named parts in the manifest, header mapping in the approved outbound profile.**
  The add-on says *what it needs*, the operator approves *where it goes*. Consistent
  with `[declares]` being a request rather than a grant.
- **An opaque credential the platform knows how to apply per source profile**, with the
  add-on declaring only `needs_credential`. Smallest add-on surface; pushes every
  source's auth shape into platform configuration.

## Minimum experiment

- Take the two-part case (Naver) and one single-part case, and express both under each
  alternative above.
- Register two sources of the **same** add-on with different credentials and confirm
  each request carries the right one.
- Verify no credential value appears in the source row, job payload, Raw envelope, log,
  screenshot, or fixture, with a positive control proving the assertion can fail.
- Record what an operator sees and types in the dashboard for each shape.

## Evidence

- The declared shape and the approved mapping, per source.
- Which outbound header carried which part, observed rather than assumed.
- Absence-of-value evidence with its positive control.
- What breaks when a source is registered with a part missing.

## Exit condition

The team can state how a source's credential is declared, where each part goes, whether
a source may hold more than one, and what the dashboard asks an operator for — enough to
write the credential section of `PoC Contract 0.1` alongside
[OQ-007](OQ-007-credential-scope.md).

## Interim position

`[결정]` Until this is resolved, `addons/collector.naver.blog` declares
`needs_credential = true` plus two `secret = true` config fields (`client_id`,
`client_secret`). That is **a placeholder, not an accepted design** — it says which
secrets exist and says nothing about which header each fills. It runs today because the
harness needs no credential and the platform's outbound path does not exist yet.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution requires a Decision
Packet linked to the measurements above, a contract version rise if the manifest shape
changes, and a stated interaction with [OQ-007](OQ-007-credential-scope.md).
