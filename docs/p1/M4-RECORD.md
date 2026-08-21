# M4-RECORD — the platform-gaps addendum

This file is not a full M4 milestone record — M4's per-source lanes (NAVER blog,
NAVER DataLab, trend-radar, tubedepth, the importer/obfuscation-normalizer pair) each
keep their own batch report under `.superpowers/sdd/2026-08-21-m2-m7-batch/`. This is
the **platform-gaps section** M4x's task packet asked to be registered here: the two
architecture gaps `collector.tubedepth.rest`'s own README and its finder's report
named as blocking live collection, and the platform mechanisms that close them.

- Worktree: `/home/user1/github_prj/Main/service/cosmai/.worktrees/m4x`, branch
  `p1/m4-platform-gaps`, cut from `dev` after `p1/m4-tubedepth` merged (`a87ff08`).
- Controlling evidence: `.superpowers/sdd/2026-08-21-m2-m7-batch/m4-tubedepth-report.md`
  ("Live verification, and two platform-level findings"); `apps/addons/collector.tubedepth.rest/README.md`
  (same section, now updated); [DP-031](../decisions/DP-031-p1-collector-topology.md) D3
  and its 2026-08-21 addendum (why these two capabilities are owed to the two adapter
  targets DP-031 fixed).
- Full evidence and commit hashes: `.superpowers/sdd/2026-08-21-m2-m7-batch/m4x-platform-gaps-report.md`.

## Gap 1 — plain HTTP for loopback

`domain.transport.SocketTransport` was HTTPS-only (`http.client.HTTPSConnection`, a
real TLS handshake, no other scheme accepted). tubedepth's live instance serves plain
HTTP by design (its own `docs/api.md`: "There is no TLS here"), so no live collect
through the real host worker could reach it.

**The mechanism.** `domain.outbound.OutboundProfile` gains a `scheme` field
(`"https"` unless a profile states `"http"`). `domain.outbound.resolve` grants
`"http"` only when the profile's `allow_loopback` is also set — the same flag that
already admits a loopback address into `check_resolved_addresses` at all, rather than
a second flag that could disagree with it. That is the validation half, and it is
testable with no socket, the way every other rule in `domain/outbound.py` is.

`domain.transport.SocketTransport` holds the transport half: before it will speak
plain HTTP, it checks that every address `resolve_addresses` actually resolved is
itself loopback (`_refuse_http_off_loopback`), independent of what the profile
claims. A hostname that resolves to loopback once and something else the next time is
exactly the rebinding hole this module's own docstring already refuses to create for
TLS; this is the same discipline with no certificate to fall back on. `SocketTransport`
picks `http.client.HTTPConnection` or `HTTPSConnection` per request based on
`PreparedRequest.scheme`; every other property (one hop, no redirect followed, one
deadline for the whole request, credential attachment, header stripping) is unchanged
for the plain-HTTP path.

**What it does not cover — recorded as a deviation, not silently absorbed.**

- `scheme` is a profile-wide setting, not per-endpoint. A source needing HTTP for one
  endpoint and HTTPS for another is not representable; every fixed adapter target this
  platform has hosted so far speaks one scheme for every route it serves, so this was
  not a reduction against a named uncertainty.
- Plain HTTP never leaves loopback, by construction: the validation half requires
  `allow_loopback`, and the transport half re-checks the resolved address regardless of
  what the profile says. There is no path by which `scheme: "http"` reaches a
  non-loopback address — a public or private-range host with `scheme: "http"` is
  refused at `resolve` (no `allow_loopback` needed to be missing) and, if it somehow
  reached the transport anyway, refused again there.
- A redirect from a plain-HTTP endpoint is not specially handled: `check_redirect`
  still only allows `ALLOWED_SCHEMES = {"https"}`, so any redirect off a loopback-HTTP
  endpoint is refused outright rather than re-validated as a same-scheme hop. Untested
  because tubedepth's target routes do not redirect; recorded as a known gap for a
  future loopback target that does.
- Nothing about `p0-security.md`'s HTTPS-only policy changed for a non-loopback
  destination. This is a narrow, named exception for the one case DP-031 D3 already
  created a private-network egress precondition for — not a general HTTP allowance.

## Gap 2 — path parameters

`domain.outbound.resolve` had one fixed path per `endpoint_ref`; `params` only ever
became a query string (`GET`) or a body (`POST`, DP-020). tubedepth's dereference
route needs `digest` **in the path** (`GET /v1/artifacts/{digest}`), known only at run
time from the previous page, so it could not be one of the paths an operator
pre-approves the way every other endpoint's path is.

**The mechanism.** An approved path may carry a `{name}` placeholder. The profile
declares one validation regex per placeholder in the endpoint's `path_params` — read
and checked at profile construction (`_read_endpoints`/`_read_path_params`): every
placeholder needs exactly one declared regex and every declared regex needs a matching
placeholder, or the row is refused with a `ValueError` when it is written, not on the
add-on's first `fetch`. The add-on supplies the value through `fetch`'s **existing**
`params` channel — no signature change to `addon_api.context.Fetch` was needed, since
`params: Mapping[str, str] | None` already carried exactly this shape; `collector.
tubedepth.rest`'s own `context.fetch(_ARTIFACT_PAYLOAD, {"digest": digest})` call
(written before this gap closed, to the contract's *intended* shape) needed no change
at all. `resolve` validates the value against the declared pattern, substitutes it into
the path, and only then runs the **same** segment-by-segment `comparable_segments`
containment every approved path has always been checked with — now against the path a
template actually resolved to, which is what makes a traversal attempt fail two
independent controls rather than one: the declared regex refuses it as a value, and
(separately, provable with a deliberately permissive regex) the containment check would
refuse it as a path even if the regex had not.

**What it does not cover — recorded as a deviation, not silently absorbed.**

- Validation is exactly as strong as the profile's own declared regex, and no
  stronger. A profile author who declares `path_params: {"digest": "^.*$"}` gets no
  help from the regex layer; the containment check (dot-segment / encoded-separator
  refusal) is what still stands between that value and a request, and it is a **weaker**
  guarantee than a tight regex — it catches `..` and `%2e`/`%2f`, not an arbitrary
  extra path segment that contains neither (a value like `foo/bar` with no dots would
  pass containment and change the request's shape). tubedepth's own `digest`
  declares `^[0-9a-f]{64}$`, which admits no such value; a future template endpoint's
  safety depends entirely on its own operator writing an equally tight pattern.
- A template placeholder consumes its name out of the `params` a query string would
  otherwise use; it does not add a new parameter-count or type-shape check beyond the
  regex. `allowed_parameters` (when a profile sets one) is checked against what remains
  after template names are consumed, so a profile that lists `allowed_parameters`
  without also listing its own template names is unaffected — the template name is
  never subject to that check at all, by design (it is not a query parameter).
- The redirect range a templated endpoint grants uses the **literal** `{name}` text as
  the approved segment (`OutboundProfile.approved_paths()` returns the unsubstituted
  template). A real redirect's concrete segment can never textually equal `{digest}`,
  so a redirect from a templated endpoint is refused by `check_redirect` unconditionally
  — untested against tubedepth (its routes do not redirect) and worth a follow-up if a
  future templated endpoint's target does.

## Evidence

- `apps/tests/test_outbound_policy.py`: `TestScheme` (scheme validation, no socket),
  `TestPathTemplates` (substitution, regex refusal, the traversal test split across
  the validation and containment layers per the P0 one-control-per-test style, missing
  parameter, template-free endpoints unaffected), `TestPathTemplateDeclaration`
  (read-time refusal of a malformed `path_params` declaration).
- `apps/tests/test_outbound_transport.py`: `TestPlainHttpForLoopback` (a real plain-HTTP
  stub server reached over loopback; credential stripping still applies; a hand-built
  request to a non-loopback address refused by the transport even with `allow_loopback`
  set on the profile; the existing HTTPS path unaffected).
- `[측정]` Full `apps` suite: 1003 passed, 2 pre-existing failures unrelated to this
  diff (`test_outbound_transport.py::TestLoopbackIsOnlyReachableByFlag`, both cases —
  `REPO_ROOT`'s `.worktrees` path-segment collision when run from inside a worktree,
  first recorded by `m4-tubedepth-report.md` and reproduced identically here, confirmed
  by re-running the same two cases before this task's diff). `mypy --strict` and
  `ruff check` clean on the whole `apps/` tree. Root guard: 87 passed.
- `[측정]` Live smoke, 2026-08-21: one bounded `collect()` through the real host worker
  against the live tubedepth instance (`127.0.0.1:8080`, now `1.1.0` — moved again since
  `m4-tubedepth-report.md`'s `1.0.3` finding, artifacts-feed surface unchanged).
  **SUCCEEDED**: 5 `artifacts_list` pages, 224 `artifact_payload` dereferences (every
  one a real plain-HTTP loopback request with a validated-and-substituted `{digest}`),
  224 Raw items, watermark advanced, and `domain.store.seal_snapshot_from_raw` sealed a
  224-item snapshot. Full detail in the task report named above.

## Required changes recorded elsewhere

- `apps/addons/collector.tubedepth.rest/README.md` — the "Live verification, and two
  platform-level findings" section is replaced with "Live verification" (unchanged
  facts) plus "M4x — the two platform gaps this add-on named, closed" (the mechanism
  and the live-smoke result), and a new "The operator-approved outbound profile"
  section giving the exact profile shape that now reaches the target.
