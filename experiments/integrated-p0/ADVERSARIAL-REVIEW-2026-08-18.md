# Adversarial review of `27f712b` — EXP-003 step 6

- Reviewed: `27f712b` "Put a collector on the platform, and make its refusals unswallowable"
- Date: 2026-08-18
- Reviewer: an independent agent with no write access to the repository, working from a
  copy. It did not author any of the code it reviewed.
- Experiment: [EXP-003](EXP-003-capability-layer.md), procedure step 6
- Outcome: **3 blocking findings, 3 major, 3 moderate, 1 minor.** None of the reviewed code
  has been repaired yet; this document is the record, and the fixes are listed at the end
  as work items.

## Why this exists

The implementer and the author of every claim under review are the same party, so
`27f712b` had no independent axis. This review is that axis, and it is committed beside
the commit rather than summarised into it — for the reason
[ADVERSARIAL-REVIEW-2026-08-17.md](ADVERSARIAL-REVIEW-2026-08-17.md) gives: *"a review
whose findings survive only as the conclusions its subject chose to adopt is not evidence
of anything."*

`[추론]` The 2026-08-17 review found every blocking defect in the *record* rather than in
the platform. This one is the other way round: all three blocking findings are in the code,
and two of them are properties the record claimed and the code does not have.

## Why the findings are recorded before they are fixed

`[결정]` The findings are recorded before anything is repaired. EXP-003's procedure names
the reason: *"A security control's failure mode is passing while blocking nothing, which is
the shape its own author is least able to see."* Repairing first and recording after would
leave no evidence of what the author had believed, and the gap between the two is the most
useful thing here.

What **was** changed immediately is separate and narrow: three docstrings that state a
control in the present tense which does not exist. `AGENTS.md` names that as a failure mode
of its own, and a false claim left standing while a fix is scheduled is a claim someone will
act on in the meantime.

## Verification by the author

`[측정]` Six of the ten findings were reproduced independently by the author, using
different commands than the reviewer's, before this document was written:

| Finding | How it was independently confirmed |
|---|---|
| F1 | `grep -rn "max_pages\|max_records"` over the tree: no platform-side consumer |
| F2 | Reading `runner.py:116-123`: the `_settle` call sits outside the `try` |
| F3 | `grep -rn "bind_capabilities"`: three call sites, all tests; `worker.py` names neither `capabilit` nor `addon` |
| F4 | `check_redirect` called directly: `/admin/keys` refused, `/v1/items/../../admin/keys` allowed, `/v1/items2/secret` allowed |
| F8 | `check_resolved_addresses` on `100.64.0.1` and `fec0::1`: both pass |
| F10 | Reading `test_capabilities.py:327-332`: `attempt_id` is selected and never asserted |

`[확인 사실]` F9 is confirmed by construction rather than by running: the scan is
`EXPERIMENT_ROOT.rglob("*.py")`, so `.sql`, `.json`, and everything under `tests/` at the
repository root are outside it.

`[측정]` F5, F6, and F7 rest on the reviewer's measurements, quoted with the numbers it
reported. They have not been independently reproduced.

## Environment

`[측정]` The reviewer ran the scoped battery — `test_capabilities.py`,
`test_outbound_transport.py`, `test_outbound_policy.py`, `test_durable_scope.py`,
`test_domain_store.py` — and measured **119 passed in 7.5s**, matching the author's 119. Its
sandbox permitted the loopback TLS listener, so the socket-level claims were actually
exercised rather than reasoned about.

`[측정]` `./scripts/with-database.sh` fails under an agent sandbox at `pg_ctl status`, which
cannot see the running postmaster because process signalling is denied. Under the same
sandbox `test_api.py`, `test_ops.py`, and `test_secret_store_guard.py` fail with
`PermissionError` from `ssl.SSLContext.load_verify_locations`; they spawn subprocesses and
bind listeners. `27f712b` touches none of that. `[추론]` These are environment facts, not
findings against the commit.

---

## F1 — `max_pages` and `max_records` are enforced nowhere. **Blocking.**

**Claimed.** `p0-security.md` §Outbound requires a per-source "page/record limit" and then
states that after DP-008 *every* obligation in that section is the platform's, not the
add-on's. `addon_api.context.Limits` said: *"an add-on that ignores these is still bounded —
the platform enforces them whatever the add-on believes."* `27f712b`'s message: *"Every
outbound obligation stays on the platform."*

**Why it is false.** `[측정]` The only consumer of `max_pages` in the tree is
`addons/collector.naver.blog/handler.py:97`. `max_records` is read by nothing. `_fetch` has
no call counter; `_emit_raw` has no item counter.

**Measured.** An add-on fetching 12 times and emitting 600 items against
`{"max_pages": 2, "max_records": 3}` succeeded: 12 requests sent, 12 envelopes, 600 items.

`[추론]` The gap was invisible because the one committed collector honours `max_pages`
voluntarily, so the integration test passes while proving only that the add-on cooperates.
Two of §Outbound's obligations are still the add-on's.

`[추론]` The serious half is the contract text, not the missing counters. `Limits` is
add-on-facing: an author reads it and concludes they need not defend against a runaway page
loop.

## F2 — an exception from enlisted work kills the worker and is misreported. **Blocking.**

**Claimed.** `runner._settle`: *"Enlisted work that raises does the same thing — the
transaction unwinds and the error is classified like any other handler failure."*

**Why it is false.** `[확인 사실]` `_execute` wraps only `handler(context)`. The
`self._settle(...)` call is outside that `try`, so nothing classifies what enlisted work
raises.

**Measured.** A collector passing a missing header through as `content_type` — the shape any
collector produces when a response omits `Content-Type` — leaves:

```
run_once() raises psycopg.errors.NotNullViolation
raw_envelope                                = 0      (the transaction did unwind)
job.state                                   = RUNNING
job_attempt.outcome/error_class/finished_at = NULL
job.lease_owner                             = still held
```

`[측정]` In the real worker this reaches `worker._one_pass`, where `classify` maps SQLSTATE
`23502` to `ConfigurationInvalidError` — non-retryable — so the process exits
`EXIT_CONFIGURATION_INVALID` logging **"cannot reach the platform database"**. One add-on's
output defect stops the worker and misattributes itself as database unreachability.

`[확인 사실]` The suite already knew the exception escapes:
`test_durable_scope.py::test_a_failure_inside_enlisted_work_leaves_nothing_behind` wraps
`run_once()` in `pytest.raises` and then asserts only `rows == 0`. `[추론]` The escape was
visible in the author's own evidence and went unremarked, while the docstring beside it said
the opposite. That is the finding within the finding.

## F3 — H2a's atomicity is a property of the fixture, not of the code. **Blocking.**

**Claimed.** *"A worker that lost its lease persists neither Raw nor cursor."*

**Why it is unproven.** `[확인 사실]` `bind_capabilities` has three call sites, all in tests.
`platform_core/worker.py` never wires the capability layer at all. The property depends on
`DomainStore` and `JobStore` sharing one connection, and that requirement is asserted
nowhere — it lives in a fixture docstring.

**Measured.** The same test with the `DomainStore` on its own autocommit connection:

```
outcome.accepted = False     # the fence still refused
raw_envelope     = 1         # Raw survived it
raw_item         = 2
cursor           = 3
```

`[추론]` `DomainStore` never commits — true, and the reviewer verified it. But "never
commits" and "is inside the fence's transaction" are different properties, and only the
second is what H2a claims. Nothing in the code and no test would catch the mis-wiring, which
matters because the wiring does not exist yet: `worker.py` is where it will be written, and
it is the place the requirement is least visible.

## F4 — the redirect path range is bypassable with dot-segments. **Major.**

**Claimed.** `check_redirect`: *"Same policy means the same function decides — a second,
looser check written for redirects would be the hole."*

**Why it is false.** `[측정]` The check is `parts.path.startswith(p)` on the raw,
un-normalized path, and `transport._path_of` sends the URL verbatim. Reproduced directly:

```
/admin/keys                    REFUSED PATH_NOT_ALLOWED
/v1/items/../../admin/keys     ALLOWED
/v1/items2/secret              ALLOWED     (prefix, not a path segment)
```

`[측정]` The reviewer carried it end to end over TLS against a stub that normalizes its
request target the way RFC 3986 §5.2.4 requires, as nginx and Apache do, and reached a body
it had written as `{"secret": "THIS-PATH-WAS-NEVER-APPROVED"}`.

`[추론]` Same host, so this is a scoping violation rather than SSRF. But the path range is a
stated control, and here the far end rather than the operator decides where a request lands.

## F5 — the read timeout bounds one `recv`, not the read. **Major.**

**Claimed.** `transport`'s module docstring: *"It stops… so SEC-004 holds against a server
that never stops sending as well as one that never starts."*

**Why it is false.** `_read_bounded` calls `source.read(n)`, which blocks until *n* bytes
arrive; `settimeout` bounds each underlying `recv`. A server emitting one byte per
(timeout − ε) never trips either bound.

**Measured by the reviewer**, not independently reproduced: `read_timeout_s=1.0`,
`max_response_bytes=20`, one byte every 0.4s → refused as `RESPONSE_TOO_LARGE` after
**8.1s**, eight times the read timeout.

`[추론]` Occupancy is linear in the body limit. Against `DEFAULT_LIMITS` (30s, 8 MiB) the
reviewer's arithmetic gives ~38 days at one byte per 0.4s. Two multipliers sit on top and
both are visible in the code: `_connect` applies `connect_timeout_s` **per address**, and
`_fetch`'s redirect loop allows `max_redirects + 1` hops each with its own full read. With
F1 the product is unbounded. `[추론]` The fix shape is a monotonic deadline across the whole
of `_fetch`, not a socket timeout.

`[확인 사실]` The suite's slow case tests a server that never *starts*. The other half of the
docstring's own claim was untested.

## F6 — seven load-bearing rules whose removal the suite does not catch. **Major.**

The author ran three mutations and each went red. The reviewer found seven that stay green,
each applied to a copy and run against every test file importing `domain.outbound`,
`domain.transport`, or `addon_host.capabilities`, without `-x`.

| Mutation | Result |
|---|---|
| `_read_bounded`: `limit + 1` to `limit` | RED |
| Control: drop `_check_no_refusal_was_swallowed` | RED, 2 failed — reproduces the author's number |
| `resolve()` drops the absolute-path check | **GREEN** |
| `_advance_cursor` drops the null-cursor check | **GREEN** |
| `_UNBOUND_KINDS` drops `importer` | **GREEN** |
| `check_resolved_addresses` drops `is_reserved` | **GREEN** |
| `PROTECTED_HEADERS` drops three of its seven names | **GREEN** |
| `_check_outcome` drops the `isinstance` check | **GREEN** |
| `_hop` drops the explicit `Host` header | **GREEN** |

`[추론]` Two matter beyond the count. Dropping `importer` from `_UNBOUND_KINDS` silently
hands an importer add-on a `CollectContext` — that is, a `fetch` — and nothing notices; only
`normalizer` has a test. Dropping names from `PROTECTED_HEADERS` is a credential-into-Raw
mutation that nothing catches, because the test enumerates three of the seven names. The
`Host` one is benign — `http.client` supplies the same value — and is worth knowing
precisely because the line reads as load-bearing and is not.

## F7 — a swallowed refusal is masked whenever the run does not return normally. **Moderate.**

**Claimed.** *"A run that returns normally after one fails anyway, with the refusal's own
reason."*

**Why it is narrower than the claim.** `_check_no_refusal_was_swallowed` runs only on the
normal-return path and only after `_check_outcome`. Measured:

| Add-on | Outcome |
|---|---|
| swallows a refusal, then hits a timeout | `PLATFORM_TRANSIENT`, job to PENDING and **retried**; the refusal appears nowhere |
| swallows a refusal, also miscounts | the count error masks the refusal reason |
| swallows a refusal, returns `None` | the return-type error masks it |

`[추론]` The first is the bad one: a security refusal is downgraded to a retryable blip and
burns the attempt budget re-hitting it. Recording the refusal is done correctly; the check is
simply not in a `finally`.

`[측정]` Related: `_emit_raw` and `_advance_cursor` raise `AddonOutputInvalid`, which **is**
swallowable. A collector that catches its own `advance_cursor(..., None)` refusal completes
`SUCCEEDED` with no cursor — silent re-collection forever, which is the failure class OQ-010
was opened for.

## F8 — the address rule is a denylist, and CGNAT passes it. **Moderate.**

`[측정]` Reproduced directly. `check_resolved_addresses` enumerates blocked properties rather
than requiring `is_global`:

```
100.64.0.1   refused=False  is_global=False    # RFC 6598 CGNAT — also all of Tailscale
fec0::1      refused=False  is_global=True     # deprecated IPv6 site-local
```

`[측정]` The reviewer probed 16 addresses. IPv4-mapped (`::ffff:127.0.0.1`,
`::ffff:169.254.169.254`), NAT64, and 6to4 encodings of loopback and the metadata endpoint
are **all refused**, and `allow_loopback` widens none of them.

`[추론]` `100.64.0.0/10` is the one worth acting on: it is where container platforms and mesh
VPNs live.

## F9 — the `allow_loopback` scan is narrower than the claim it carries. **Moderate.**

**Claimed.** *"The flag exists for tests. If it ever appears elsewhere, this names the file."*

`[확인 사실]` The scan is `EXPERIMENT_ROOT.rglob("*.py")`. Measured against the tracked tree:
73 of 208 tracked files are visible to it; 7 tracked `.py` under `tests/` are not; **no
non-`.py` file is**, including every `.md`, `.json`, `.toml`, and `.sql`.

`[추론]` A source is a database row whose `outbound_profile` is JSON. The natural P0-B place
for a seeded source is a `.sql` migration or a `.json` fixture, and the scan can read
neither — including `domain/migrations/0002_domain.sql`, which sits beside it. The positive
control is real and proves `rglob` works; it cannot prove the root or the glob are right.

## F10 — `attempt_id` attribution is selected and then dropped. **Minor.**

`[확인 사실]` `test_capabilities.py` selects `attempt_id` from `raw_envelope` and the
assertion two lines later uses `row[1]`-`row[4]`. `row[5]` is never read. No test asserts
that the envelope's `attempt_id` is the attempt the runner claimed.

`[추론]` The risk is low — the `not null` and the foreign key make it hard to get wrong, and
every construction site passes the real value. But `27f712b` calls `attempt_id` one of its
three found defects, and the assertion for it was written and then not made.

---

## What the reviewer could not break

Recorded because a negative result from an adversary is evidence, and because these are the
claims that survived a real attempt rather than a reading.

- **The rebinding defence holds, tested positively.** The reviewer replaced
  `HTTPConnection.connect` and `HTTPSConnection.connect` with detonators after `_connect` had
  built its socket and ran a real request: 200, detonator never fired, and the only dial
  events were `socket.create_connection` to literal addresses from the checked set.
  `getaddrinfo` runs once per `send`; every address is checked; each redirect hop is a fresh
  `send` and therefore a fresh check. No path was found where the socket ends up somewhere
  the check never saw.
- **`resolve()` cannot be made to emit a foreign host or path from add-on input.**
  `endpoint_ref` is a mapping key; `urlencode` percent-encodes every key and value, so no
  parameter can inject `?`, `#`, `&`, `/`, CR, or LF; the connection uses
  `PreparedRequest.host` and never re-parses the URL.
- **`DomainStore` never commits** — verified rather than assumed.
- **CRLF injection into the request target is blocked**, by `http.client._validate_path`
  rather than by this code. `[추론]` Worth recording as a borrowed control: it is not ours
  and could change under us.
- **Redirect hop counting is correct**: `max_redirects=3` permits exactly 3 redirects and 4
  sends.

## Two smaller notes

`[추론]` A TLS verification failure is indistinguishable from a timeout: `_connect` catches
`ssl.SSLError` into `last` and raises `TransportUnavailable`, which `_fetch` classifies
transient. A host presenting a bad certificate burns the whole attempt budget retrying
instead of failing as the configuration problem it is.

`[추론]` A relative `Location` — ordinary server behaviour — is refused as
`SCHEME_NOT_ALLOWED` and, through F7's machinery, becomes a permanent job failure reported as
a security refusal.

---

## Work items

Ranked. Nothing here is done; this list is the handoff.

| # | Finding | Shape of the fix |
|---|---|---|
| 1 | F2 | Bring `_settle` inside `_execute`'s classification, without double-recording a completion |
| 2 | F3 | Wire `bind_capabilities` in `worker.py`, and make the shared-connection requirement a checked precondition rather than a fixture docstring |
| 3 | F1 | Count pages in `_fetch` and items in `_emit_raw`; refuse past the limit |
| 4 | F5 | A monotonic deadline across the whole of `_fetch`, replacing the per-`recv` socket timeout as the bound |
| 5 | F4 | Normalize or reject dot-segments before the prefix test, and compare path *segments* rather than string prefixes |
| 6 | F7 | Move `_check_no_refusal_was_swallowed` into a `finally`; decide whether `AddonOutputInvalid` should be unswallowable too |
| 7 | F8 | `if not address.is_global`, keeping `allow_loopback` as the one exception |
| 8 | F6 | A test per green mutation, starting with `importer` in `_UNBOUND_KINDS` and the full `PROTECTED_HEADERS` set |
| 9 | F9 | Scan every tracked file, not `*.py` under one subtree |
| 10 | F10 | Assert the envelope's `attempt_id` is the claimed attempt's |

## What was changed immediately

`[결정]` Only the false claims, and only to make them true statements about what exists:

- `addon_api/context.py::Limits` — no longer says the platform enforces these. It names which
  are enforced, which are not, and points here.
- `addon_host/capabilities.py::_limits_of` and its module docstring — the same correction.
- `platform_core/jobs/runner.py::_settle` — no longer says enlisted work is classified like
  any other handler failure. It says what happens instead, and names F2.
- `EXP-003`'s Interpretation — "every outbound obligation except credential attachment" was
  wrong; it is except credential attachment, page limit, and record limit.
