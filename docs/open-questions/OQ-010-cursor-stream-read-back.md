# OQ-010 — Which cursor an add-on reads back when it writes several

- Status: `OPEN`
- Priority: P0-B — blocks any collector or importer with more than one stream
- Owner: Project team
- Blocks: multi-stream collectors and importers; the conformance suite's resume scenario
- Related experiments: [EXP-003](../../experiments/integrated-p0/EXP-003-capability-layer.md)
- Resolution Decision Packet: not created

## Question

`CollectContext.cursor` is **one value**. `advance_cursor` takes **a stream name and a
value**. When an add-on declares more than one stream, which stream's cursor does it
read back?

## Why this surfaced

`[측정]` Found on 2026-08-18 while implementing the capability layer — that is, by the
first code that had to answer it. Both halves are in the committed contract:

```python
# addon_api/context.py
cursor: Any | None
advance_cursor: Callable[[str, Any], None]
```

`[확인 사실]` The asymmetry is real and undocumented. `docs/conventions/addon-authoring.md`
lists `cursor` and `advance_cursor` as two collector capabilities and says nothing about
how they line up. `domain.store.CURSOR_STREAM_DEFAULT` exists for "an add-on that advances
a cursor without naming one", but the contract's `advance_cursor` **requires** a name, so
no add-on can reach that default through a capability.

`[측정]` `addons/collector.naver.blog` reads `context.cursor` and writes
`advance_cursor("items", start)`. It declares `streams = ["items"]`. Under the naive
reading — `cursor` is the `default` stream — it would read a stream it never writes and
restart from position 1 on every attempt: no error, no lost record, and every record
collected again on every run. `[추론]` That failure is silent in both directions an
operator could look, which is why this is a question rather than a bug to patch.

## Scope

### Included

- What `CollectContext.cursor` and `ImportContext.cursor` mean for a multi-stream add-on.
- Whether `[declares].streams` constrains what `advance_cursor` may name.
- Whether the two capabilities should be symmetric, and at what contract version.

### Excluded

- What a cursor **value** may contain. It stays opaque to the platform (`0002_domain.sql`),
  and nothing here proposes interpreting one.
- Snapshot selection semantics, which are [OQ-004](OQ-004-snapshot-boundary.md)'s.

## Hypotheses and falsification

| Hypothesis | Falsification condition |
|---|---|
| H1: Most sources need exactly one stream, so the single-valued read is the common case and multi-stream is the exception worth extra vocabulary. | Two or more of the sources selected in B1 need independent positions. |
| H2: Making `cursor` a mapping of stream to value is a strictly better contract, at the cost of a contract version rise and every existing add-on. | The mapping form makes the common single-stream add-on measurably harder to write, or the template's example stops reading clearly. |
| H3: The host can bind the cursor to the add-on's single declared stream without any contract change, and refuse the multi-stream case until this is settled. | An add-on needs two streams before this question is answered. |

## Alternatives

- **`cursor` is the default stream's.** Today's naive reading. Silently wrong for every
  add-on that names a stream, which is every add-on, because the capability requires a name.
- **`cursor` is the add-on's single declared stream; more than one is refused.** No contract
  change. What the host does now — see the interim position.
- **`cursor` becomes `Mapping[str, Any]`.** Symmetric, and a `CONTRACT_VERSION` rise.
- **`advance_cursor` loses its stream argument and streams are dropped.** Smallest contract;
  discards a capability nothing has yet needed, which is evidence not yet gathered.

## Minimum experiment

- Write one add-on that genuinely needs two independent positions and express it under each
  alternative.
- Confirm resumption works: two attempts, second one starting where the first stopped,
  observed in `source_cursor` rather than in a log line.
- Positive control: an add-on that writes a stream it did not declare must fail, and the
  test must show the assertion can fail.

## Interim position

`[결정]` The capability layer binds one stream per source: the add-on's single declared
stream, or `CURSOR_STREAM_DEFAULT` when it declares none. An add-on declaring two or more
is **refused at job time with this question named**, and an `advance_cursor` naming any
other stream raises `AddonOutputInvalid`.

`[추론]` This is a refusal, not an answer. It was chosen over binding the default stream
because that reading fails silently, and over guessing the mapping form because one add-on
is not enough evidence to fix a contract shape. `addons/collector.naver.blog` declares
exactly one stream, so nothing installed today is blocked by it.

## Exit condition

The team can state what `cursor` holds for an add-on with several streams, whether
`[declares].streams` is a constraint or a description, and — if the shape changes — which
`CONTRACT_VERSION` the change lands in.

## Resolution

Not completed while status is `OPEN` or `EXPLORING`. Resolution requires a Decision Packet,
and a contract version rise if `CollectContext` or `ImportContext` changes shape.
