# collector.naver.blog

Naver API Hub blog search, copy-adapted from `experiments/integrated-p0/addons/collector.naver.blog/`
(M4 naver-blog worktree). See `handler.py`'s module docstring for the vendor documentation
this add-on is built against, and the three `[가설]` assumptions a real capture would need to
confirm.

## What the collector kind is granted

- `context.fetch(endpoint_ref, params)` — one request through the platform's
  outbound guard; returns a `FetchResponse` whose bytes are already recorded as
  a Raw envelope, whether or not this add-on emits anything from it.
- `context.emit_raw(items)` — hand off carved `RawItem`s for durable, lossless
  storage.
- `context.advance_cursor(stream, cursor)` — record where this stream stopped.
- `context.log(event, fields)`, `context.config_field(name, fallback)`.

No `open_input` and no `read_snapshot` — those belong to the other two kinds.

## What every kind is refused

No add-on ever receives a credential, a URL, or a database handle (DP-008 D4). A
collector's `fetch` takes an endpoint name, not a URL, and composes the request
from the source's approved profile; a credential named by `needs_credential = true`
is resolved inside `fetch`, and this add-on never sees its value.

## Versioning (DP-008 D3)

- Bump `[addon].version` whenever this add-on's behavior changes. A new version
  makes results coexist rather than silently replace the old ones.
- Bump `[config].schema_version` whenever `[[config.field]]` changes shape. A
  source configured under an older schema is marked `NEEDS_MIGRATION` and refuses
  to run until an operator reconfigures it.
- `requires_contract` states which `addon_api.CONTRACT_VERSION` values this add-on
  supports. A host running an incompatible contract version refuses the load at
  process start, before any job runs.

## Secrets

Mark a config field `secret = true` to route it to the repository-external secret
store instead of the source row (DP-008 D6). This add-on declares none — the two
NCP credential parts (`X-NCP-APIGW-API-KEY-ID`, `X-NCP-APIGW-API-KEY`) live in the
source's approved outbound profile (DP-018), not in `[[config.field]]`; see
`handler.py`'s module docstring for why.

## Failures

Raise from `addon_api.errors`, not a bare exception, so the platform can classify
the failure instead of guessing from an exception type:

- `AddonTransient` — this exact call could succeed if retried (a rate limit, a
  timeout, a 5xx).
- `AddonPermanent` — retrying will not help (an unparseable record, a non-auth
  4xx).
- `AddonConfigInvalid` — the stored configuration for this source is wrong; only
  an operator can fix it (this covers a 401 or 403, since the credential is part
  of the configuration).

## Verification

`apps/tests/test_collector_naver_blog.py` exercises this add-on's fixture-based
behavior through `addon_kit.harness.run_addon`, and its conformance-suite class runs
`addon_kit.conformance.run_conformance` against this directory directly — the
"the other half of work package B0.4" the P0 README noted as not yet existing now
does, and both must pass. `apps/tests/test_addon_host.py`'s naver-blog case (or the
dedicated fixture in this add-on's own test file — see the "discovered from
apps/addons/" test) checks that this package is discovered and passes the version
gate from the platform's default `COSMA_ADDON_DIR`.
