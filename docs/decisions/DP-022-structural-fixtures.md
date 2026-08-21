# DP-022 — Structural fixtures: keeping the evidence of a real capture without its content

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project team
- Extends: [Data Handling Convention](../conventions/data-handling.md) — its `public` promotion rules, not replaced
- Affected artifacts: `tests/fixtures/public/`, the evidence records under `experiments/integrated-p0/evidence/`
- Related: [OQ-001](../open-questions/OQ-001-source-capability.md) — this is how a probe's output becomes reusable evidence

## Decision question

Every response fixture in this repository was written **from the vendor's documentation**,
by hand. That is why three assumptions in `collector.naver.blog` and two in each DataLab
collector are labelled `[가설]`: nothing in the offline suite has ever seen what the API
actually sends.

A real capture would fix that permanently and offline. It cannot simply be committed:
`data-handling.md` requires a redistribution basis, the operator's basis is personal
research and study, and that covers processing and not republication.

The convention also forecloses the obvious workaround, in as many words:

> 원본의 일부를 잘랐거나 redaction했다는 사실만으로 재배포 권리가 생기지 않는다.

So: **is there a form of a capture that carries its evidential value and is ours to
publish?**

## Decision

**D1 — Yes, and it is not redaction.** A **structural fixture** is a *newly generated*
document that reproduces every structural property observed in a real capture and contains
none of its content. It is not the original with parts removed; it is a record of what was
observed about the original's shape.

`[추론]` The distinction is the whole packet and it is not a technicality. A redacted blog
post is still that blog post, which is why the convention refuses to let redaction create
rights. A structural fixture contains no sentence anyone wrote, no title anyone chose, and
no URL anyone owns — it is the same kind of artifact as the sentence *"this endpoint returns
`items` as an array of objects each carrying `link` as a non-empty string."* That sentence
has always been publishable. This is that sentence, executable.

**D2 — What must be preserved is exactly what a test can assert on.**

| Preserved exactly | Replaced |
|---|---|
| Key names, nesting, key order | Every string's textual content |
| Array lengths | Every identifier and URL path |
| JSON type of every value | Author and blog names |
| `int` vs `float` distinction | Numeric magnitudes |
| `null` vs absent vs `""` | — |
| **Markup and entity structure inside strings** | the words between the tags |
| **Format class of date-like strings** | the date itself |
| **Shape of URL-like strings** — scheme, host depth, path depth | host and path segments |

`[결정]` The last three rows are the ones that make this worth building rather than
hand-waving. `collector.naver.blog`'s normalizer exists to strip `<b>` and decode `&quot;`;
a fixture that replaced `촉촉한 <b>수분크림</b> 후기` with `제품 후기` would destroy the only
property the rule is about, and the test over it would pass while proving nothing — which is
the failure mode this repository has now met four times. So markup positions survive and the
words between them do not.

**D3 — The transformation is deterministic and its rule set is versioned.** The same capture
and the same rule set produce byte-identical output. A fixture that could not be regenerated
would be an assertion nobody can re-derive, and re-derivation is what makes it evidence
rather than a file someone once made.

**D4 — Every structural fixture carries a manifest naming what it came from.** The
original's `sha256`, the capture instant, the endpoint, the rule-set version, and the
fixture's own `sha256`. `[추론]` The original's digest is what ties a synthetic document back
to a real event: without it, a structural fixture is indistinguishable from something
invented, and inventing one is exactly what it is meant to replace.

**D5 — The manifest states what the fixture does *not* represent.** A single capture is one
moment of one query. It cannot show a `429`, an empty result set it did not contain, or a
field the API omits only sometimes. `data-handling.md`'s promotion rule already requires
"sample이 대표하는 behavior와 대표하지 못하는 범위" and this is where it goes.

**D6 — This changes nothing about runtime data.** Collected Raw stays in PostgreSQL under
`var/`, which is `.gitignore`d, and `source.data_class` keeps classifying what a source
*produces*. A structural fixture is a test input derived once and by hand-run tooling, never
a runtime path.

## Why not the alternatives

- **Commit the capture and rely on fair use / research exception.** `data-handling.md`'s
  checklist forbids reading an `UNKNOWN` as permission, and neither NCP's terms nor the
  bloggers' have been read. Declining is the rule, not a preference.
- **Redact and commit.** Refused by the convention's own sentence, quoted above.
- **Keep only hashes** — the status quo before this packet. It preserves accountability and
  discards every bit of the evidence. The `[가설]` labels stay `[가설]` forever.
- **Ask the operator to approve republication.** They cannot: the rights are the bloggers',
  not theirs.

## What this does *not* settle

- **Whether the DataLab responses could be committed as-is.** `[추론]` They are a different
  case: `title` and `keywords` are terms *we* sent, and `ratio` is an aggregate relative
  number. There is no third-party creative content and no personal data in them. But NCP's
  terms have not been read, that makes the redistribution question `UNKNOWN`, and the
  convention says an `UNKNOWN` is not a permission. They get structural fixtures like
  everything else until someone reads the terms.
- **Whether a structural fixture is representative.** D5 requires the gap to be stated; it
  does not make the gap smaller. A fixture derived from one lucky response is one lucky
  response with the words taken out.

## Falsification

| Claim | Falsified by |
|---|---|
| D1 — a structural fixture is ours to publish | A structural property that is itself the third party's creative choice and cannot be preserved without copying it |
| D2 — preserving structure preserves the test's value | A test that passes against the fixture and fails against the capture it came from |
| D3 — the transformation is deterministic | Two runs over one capture producing different bytes |
| The whole packet | A capture whose interesting behaviour lives in its *content* rather than its shape |
