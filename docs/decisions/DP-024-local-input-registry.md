# DP-024 — An importer names an input, and the operator's profile says what that is

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project team
- Contract impact: `addon_api` **1.2 → 1.3** (`Declarations.inputs`, `Limits.max_input_bytes`)
- Schema impact: `source.input_profile` (migration `0004`)
- Closes: `addon_host/capabilities.py` `_UNBOUND_KINDS["importer"]` — *"open_input needs a
  registry of approved local inputs, and no document defines one yet"*
- Related: [DP-008](DP-008-addon-architecture.md) D4, [DP-020](DP-020-request-method-and-body.md),
  [OQ-001](../open-questions/OQ-001-source-capability.md)

## Decision question

`[확인 사실]` `ImportContext.open_input: Callable[[str], InputStream]` has been in the
contract since B0 and is bound by nothing. The host refuses every importer by name, with a
reason that names the missing piece: no document defines what an approved local input is.

`[확인 사실]` P0-B work package B1 asks for **one REST source and one dataset**. Only the
REST branch was built. B4's *"malformed and partially invalid dataset rows"* scenarios
cannot run at all while `importer` is unbound.

So: what is the registry, and what stops an importer from reading a file nobody approved?

## Decision

`[결정]` **The same shape as the outbound grant, with a filesystem instead of a network.**

### D1 — An importer names an input, never a path

`open_input("rows")` takes a **name the add-on declared**, exactly as `fetch("blog", …)`
takes an endpoint name. The add-on composes no path, joins no segments, and receives no file
object — only `Iterator[bytes]`.

`[추론]` This is the one property that makes the rest checkable. If an add-on could pass a
path, every other rule here would be advice.

### D2 — `[declares].inputs` is a request; `source.input_profile` is the grant

The manifest lists the input names the add-on needs. An operator writes the profile that
maps each name to a real file. `[declares]` cannot grant anything, which is DP-008 D4's rule
applied unchanged.

```json
{"root": "/home/op/datasets/beauty", "inputs": {"rows": "2026-08/posts.jsonl"}}
```

### D3 — Resolution is contained in the root, checked after symlinks

`root / member` is resolved with symlinks followed, and the result must still be inside the
resolved root. A member containing `..`, an absolute member, and a symlink pointing outside
are each refused by rule rather than by string inspection.

`[측정]` This clause is written the way it is because the outbound guard's equivalent was
wrong once: `ADVERSARIAL-REVIEW-2026-08-19.md` F4 found the redirect path range bypassable by
dot segments, because it compared strings instead of comparing resolved segments. The same
mistake is available here and is refused the same way.

### D4 — Reading is bounded

`Limits.max_input_bytes` (default 64 MiB) bounds one input stream. Exceeding it raises the
importer's equivalent of a bounded failure rather than filling memory.

`[추론]` A dataset is legitimately larger than an HTTP response, so this is a separate limit
rather than a reuse of `max_response_bytes`. The number is a starting point, not a measured
one.

### D5 — The root may be inside the working tree, and that is a data-handling question

`[결정]` No rule here forbids a root inside the repository. `[추론]` `data-handling.md`
already governs what may be committed, and forbidding in-repo roots would forbid the
legitimate case it permits — a small fixture with a recorded redistribution basis. The threat
this packet addresses is **an add-on reading what nobody approved**, not an operator
approving something unwise; the operator is the party who writes the profile, exactly as they
write the outbound one.

### D6 — An importer still reaches no network

`[확인 사실]` Already true and already enforced: `addon_api.manifest` refuses an importer
declaring hosts or endpoints, and the database refuses to give a non-collector an outbound
profile. This packet adds the mirror constraint — a **collector or normalizer may not hold an
`input_profile`** — so each kind's input surface is exactly one thing.

### D7 — `open_input` returns an `OpenedInput`, not a stream

`[측정]` **Discovered while implementing this packet, and both corrections are kept.** The
contract's committed shape was `open_input: Callable[[str], InputStream]` where
`InputStream = Iterator[bytes]`. Two things were wrong with it:

1. **An importer could not emit anything.** `RawItem.envelope_ref` is the link from an item
   to the original it came from, and a bare iterator carries no such handle. A collector
   gets one from `FetchResponse`; an importer had no equivalent, so `emit_raw` would have
   refused every item it produced.
2. **A live iterator is not serializable.** The first repair returned an `OpenedInput`
   holding an `Iterator[bytes]`, and
   `tests/environment/test_addon_contract_is_serializable.py` refused it:
   [DP-008](DP-008-addon-architecture.md) H4 keeps every boundary type serializable so
   subprocess isolation stays a host change rather than a contract rewrite.

`[결정]` `OpenedInput` carries `input_ref`, `envelope_ref`, and `body: bytes` — exactly
`FetchResponse`'s shape. The input is read whole in any case, bounded by
`max_input_bytes` and required to exist before `emit_raw` can name its envelope, so the
streaming form bought nothing and cost the property DP-008 was protecting. `InputStream`
is removed from the contract; nothing used it.

`[추론]` The guard found the second one. A contract clause written eight days earlier
against a capability nobody had bound was wrong in two ways, and neither was visible until
something ran.

## Alternatives

- **A path in the configuration.** Smallest change and wrong: configuration is operator data
  the add-on reads, so the add-on would be composing its own destination. This is the
  arbitrary-URL problem with a different scheme.
- **A single fixed directory for all importers.** No per-source grant, so every importer
  reaches every dataset. Rejected for the same reason one allowlist for all collectors would
  be.
- **Hand the add-on an open file object.** Simpler host code; gives the add-on `.name`,
  `.seek`, and a directory it can walk from. Rejected: `Iterator[bytes]` is what the contract
  already says, and it is the version that cannot be escalated.

## Falsification

| Claim | Falsified by |
|---|---|
| Naming an input is enough for a real importer | A dataset that needs a file chosen at run time — a directory listing, a date-stamped member — which no declared name can express |
| Containment after symlink resolution is sufficient | A path that resolves inside the root and still reads what the operator did not approve (a hardlink, a bind mount, a `/proc` entry) |
| One byte bound is the right shape | An input whose damage is record count or nesting depth rather than size |
| `input_profile` and `outbound_profile` are genuinely exclusive | A source that must both fetch and import — at which point the two-kind split is the thing to re-examine |

## Consequences

1. `addon_api` rises to **1.3**. Existing add-ons declare no inputs and are unaffected;
   `requires_contract = ">=1.0,<2.0"` continues to admit them.
2. Migration `0004` adds `source.input_profile` with two constraints: only an importer may
   hold one, and an importer may hold no `outbound_profile`.
3. `_UNBOUND_KINDS` loses `importer` and the host binds `open_input`.
4. B4's dataset-row failure scenarios become runnable, which is the reason this exists now
   rather than in P1.
