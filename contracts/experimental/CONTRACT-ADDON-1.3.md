# CONTRACT-ADDON@1.3 — what an add-on may assume and must provide

- Status: `EXPERIMENTAL`
- Version: `1.3`
- Owner: Project team
- Related Open Question: [OQ-010](../../docs/open-questions/OQ-010-cursor-stream-read-back.md), [OQ-013](../../docs/open-questions/OQ-013-addon-responsibility-boundary.md), [OQ-014](../../docs/open-questions/OQ-014-externalized-acquisition.md)
- Related Decision Packet: [DP-008](../../docs/decisions/DP-008-addon-architecture.md), [DP-018](../../docs/decisions/DP-018-credential-parts-and-attachment.md), [DP-020](../../docs/decisions/DP-020-request-method-and-body.md), [DP-024](../../docs/decisions/DP-024-local-input-registry.md)
- Related experiments: [EXP-002](../../experiments/integrated-p0/EXP-002-addon-layer.md), [EXP-003](../../experiments/integrated-p0/EXP-003-capability-layer.md)
- Producers: the host (`addon_host`)
- Consumers: every add-on under `addons/`
- Last updated: 2026-08-19T+09:00

`[확인 사실]` **Why this document exists.** `AGENTS.md` requires unstable contracts to live
under `contracts/experimental/`, and this one lived only as code in the `addon_api` package.
[`ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md`](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md)
M5 found the gap. `[추론]` It matters beyond bookkeeping: P1 reconstructs from contracts and
is forbidden to import P0 packages, so a contract that exists only as a package is one P1
cannot use.

`[결정]` The **authority** is `addon_api` at `CONTRACT_VERSION = "1.3"`. This document states
the same thing in prose for a reader who cannot import it; where they disagree, the code is
right and this file is a defect. The teaching version is
[`addon-authoring.md`](../../docs/conventions/addon-authoring.md).

## Purpose and boundary

An add-on is **one Python file plus a manifest**, importing `addon_api` and nothing else
local. It receives a context appropriate to its kind and returns an outcome. It never holds
a database handle, a credential, a URL, a file path, or a transaction.

Outside this contract: job execution ([`CONTRACT-JOB-0.1`](CONTRACT-JOB-0.1.md)) and the
domain behaviour add-ons participate in ([`PoC Contract 0.1`](POC-CONTRACT-0.1.md)).

## Compatibility statement

- Compatibility obligation during P0: additive within `1.x`. A manifest declares
  `requires_contract` as a range (`">=1.0,<2.0"`), and the host refuses a manifest whose
  range excludes the running version **before importing its module**.
- Version history:

  | Version | Change | Packet |
  |---|---|---|
  | 1.0 | Initial: three kinds, three contexts, manifest, config schema | DP-008 |
  | 1.1 | `Fetch` gains an optional `body`; endpoints gain a method | DP-020 |
  | 1.2 | `CollectContext.accept_status` — a non-success status must be decided | review F2 |
  | 1.3 | `Declarations.inputs`, `Limits.max_input_bytes`, `OpenedInput`; `InputStream` removed | DP-024 |

- Known incompatible changes: `1.3` removed the `InputStream` alias. Nothing used it — no
  importer existed before `1.3`.
- Promotion or replacement condition: [OQ-013](../../docs/open-questions/OQ-013-addon-responsibility-boundary.md)
  and [OQ-014](../../docs/open-questions/OQ-014-externalized-acquisition.md) both bear on the
  seam this contract draws. OQ-014 in particular could make every collector an importer.

## Schema or message shape

### Manifest — `addon.toml`

```toml
[addon]
id = "collector.example.thing"        # also the directory name and the handler suffix
version = "0.1.0"
kind = "collector"                    # collector | importer | normalizer
entry = "handler:run"                 # module:attribute
requires_contract = ">=1.0,<2.0"
output_contract_version = "0.2"       # normalizer only, and required for one

[config]
schema_version = "1"

[[config.field]]
name = "query"
type = "string"                       # string | integer | boolean | array | object
required = true
secret = false                        # a secret field may never be stored on a source row

[declares]
hosts = ["api.example.com"]           # collector only
endpoints = ["items"]                 # collector only
inputs = ["rows"]                     # importer only
streams = ["items"]                   # collector or importer; at most one is bound (OQ-010)
needs_credential = true
```

`[결정]` **A declaration a kind cannot honour is refused at load time, not ignored.** A
silently ignored declaration is undiscoverable: the author believes they requested something
and nothing ever says otherwise.

### Contexts, by kind

| Member | `CollectContext` | `ImportContext` | `NormalizeContext` |
|---|---|---|---|
| `source_id` | ● | ● | — |
| `run_id`, `snapshot_id` | — | — | ● |
| `config`, `config_field()` | ● | ● | ● |
| `cursor` | ● | ● | — |
| `limits` | ● | ● | — |
| `fetch` | ● | — | — |
| `accept_status` | ● | — | — |
| `open_input` | — | ● | — |
| `read_snapshot` | — | — | ● |
| `emit_raw` | ● | ● | — |
| `emit_result` | — | — | ● |
| `advance_cursor` | ● | ● | — |
| `log` | ● | ● | ● |

Entry signatures: `CollectEntry`, `ImportEntry` → `CollectOutcome`;
`NormalizeEntry` → `NormalizeOutcome`.

### Boundary types

`RawItem`, `SnapshotItem`, `NormalizedResult`, `CollectOutcome`, `NormalizeOutcome`,
`Limits`, `FetchResponse`, `OpenedInput`.

`[결정]` **Every one is serializable** (`to_json` / `from_json`, registered in
`addon_api.SERIALIZABLE`) and a guard asserts the registry covers every boundary dataclass.
DP-008 H4: a contract written in serializable shapes keeps subprocess isolation reachable as
a host change rather than a contract rewrite. `[측정]` This guard rejected DP-024's first two
attempts at `OpenedInput`.

## Semantics

### Invariants

1. **An add-on imports `addon_api` and nothing else local.** Enforced by
   `tests/environment/test_addon_layer_direction.py`.
2. **An add-on names; it does not compose a destination.** `fetch` takes an endpoint name,
   `open_input` an input name. Neither takes a URL, a host, a method, or a path.
3. **An add-on never sees a credential** — not the value, not the key name, not the header
   name. Enforced at the add-on by a scan over **every** installed add-on's executable code.
4. **A refusal cannot be swallowed.** A refused request or input is recorded when raised; a
   run that returns normally after one fails anyway, with the refusal's reason.
5. **A non-success status must be decided** — raise, or `accept_status(response, reason)`
   with a reason that is logged. Silence fails the run.
6. **Writes are enlisted, not performed.** `emit_raw`, `emit_result` and `advance_cursor`
   buffer; the platform writes them inside the completion transaction.
7. **An emitted item names an envelope this run produced.**
8. **Reported counts must match what was emitted.**
9. **A normalizer is deterministic.** Same snapshot and version → byte-identical canonical
   output. Its context offers no clock and no randomness.
10. **`[declares]` is a request; the source row is the grant.**

### Missing, null, unknown, and not-applicable values

- Missing config key: `config_field(name, fallback)` returns the fallback. A *required*
  missing key was already refused when the host validated the row against the schema.
- Explicit null cursor: **prohibited as a stored value.** `read_cursor` returns `None` for
  "never ran", so a stored null would be indistinguishable from it.
- Unknown manifest key: refused, naming the key.
- Not applicable: a capability a kind does not receive is **absent from its context**, not
  present-and-raising.

### Ordering, time, and identity

- Identity boundary: `addon_id` is the add-on's identity and the source row's link to it;
  `RawItem.item_key` is the record's; `NormalizedResult.source_item_key` is the link back to
  sealed bytes.
- Timestamps: the platform owns them. `FetchResponse.retrieved_at` is ISO 8601 with
  timezone.
- Ordering: `emit_raw` preserves the order items were produced in.
- Duplicate or replay meaning: a rerun is a **duplicate**, not a version. Version coexistence
  is by `addon_version` and `output_contract_version`, never by overwriting.

## Expected behavior

- Valid input: the add-on returns its outcome; the platform writes buffered work in the
  completion transaction with the fenced completion last.
- Idempotency: the add-on carries none. It is the platform's, via effect keys and unique
  indexes.
- Retry: an add-on signals retryability by **error class**, not by retrying itself.
  `AddonTransient` is retryable; `AddonPermanent`, `AddonConfigInvalid`, and
  `AddonOutputInvalid` are not.
- Durable effects: none are the add-on's. It cannot open a transaction or reach a connection.
- Observability: `log(event, fields)` writes one structured line under `addon.<event>`, with
  the add-on's fields nested so they cannot overwrite platform identity fields.

## Error behavior

| Error class | Trigger | Retryable | Durable state | Safe operator action |
|---|---|---|---|---|
| `AddonTransient` | the add-on judges a failure worth retrying | yes | none | wait for the retry |
| `AddonPermanent` | the add-on judges a failure not worth retrying | no | none | fix the add-on or the source |
| `AddonConfigInvalid` | the stored configuration is unusable in a way the schema did not catch | no | none | fix the configuration |
| `AddonOutputInvalid` | raised by the **host**: miscounted output, wrong return type, undeclared cursor stream, item naming no envelope | no | none | fix the add-on |
| `PlatformPermanentError` | raised by the **host**: refused request or input, unswallowed refusal, undecided status | no | none | fix the profile or the add-on |

`[결정]` `AddonOutputInvalid` is declared in `addon_api` although the host normally raises it,
so an add-on validating its own output raises the class the host would rather than inventing
a second spelling.

## Provenance and security

- Required provenance the add-on supplies: `item_key`, `content_type`, `envelope_ref`, and
  optional `notes`. Everything else is the platform's.
- Credential handling: the add-on declares `needs_credential` and receives nothing.
- Prohibited in an add-on's executable code: header names, secret-store key names, URLs, and
  the `COSMA_SRC_` prefix. **Docstrings citing vendor documentation URLs are permitted** —
  the scan reads what the code *names*, not what the prose explains.
- Data class constraints: an add-on does not see `data_class` and cannot act on it. Whether
  a payload may be redistributed is the source row's and `data-handling.md`'s.

## Examples

- Valid, collector: [`addons/collector.naver.blog`](../../experiments/integrated-p0/addons/collector.naver.blog/)
- Valid, importer: [`addons/importer.local.jsonl`](../../experiments/integrated-p0/addons/importer.local.jsonl/)
- Valid, normalizer: [`addons/normalizer.naver.blog`](../../experiments/integrated-p0/addons/normalizer.naver.blog/)
- Invalid: `tests/test_addon_host.py` and `tests/test_addon_api_contract.py` hold the refusal
  cases — unknown kind, bad entry point, a kind declaring what it cannot honour, a duplicate
  config field, a non-string secret field, an unsafe `addon_id`.

## Acceptance criteria

- Related acceptance scenario IDs: the add-on layer has no `tests/acceptance/` scenario of
  its own; its evidence is `tests/test_addon_*.py`, `test_capabilities.py`,
  `test_normalizer_capability.py`, and `test_importer_local_jsonl.py`.
- Required deterministic result: a normalizer's canonical output over a fixed snapshot.
- Required failure evidence: [`B4-SCENARIO-COVERAGE.md`](../../experiments/integrated-p0/evidence/B4-SCENARIO-COVERAGE.md).

## Known limitations and unresolved semantics

1. **One cursor stream per source.** More than one is refused, which is
   [OQ-010](../../docs/open-questions/OQ-010-cursor-stream-read-back.md)'s interim position
   and not an answer to it.
2. **Judgments only an add-on can make are checked by nothing**
   ([OQ-013](../../docs/open-questions/OQ-013-addon-responsibility-boundary.md)).
3. **The layer rule forces duplication.** `[측정]` 13–15% of each collector is
   source-independent plumbing, written once per add-on because there is nowhere shared to
   put it.
4. **In-process add-ons are trusted code** (DP-008 D10). Isolation is contractual and
   test-enforced, not enforced by the operating system.
5. **`accept_status` is not unswallowable the way a refusal is.** Calling it on every
   response succeeds. What changed is the default: silence used to succeed and now fails, and
   buying the old behaviour back costs a call and a written reason per response — both
   logged and countable.
