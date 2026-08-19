# Adversarial review of DP-018 and DP-020 — 2026-08-19

- Reviewed: the credential-attachment (DP-018) and request-method/body (DP-020) work as it
  stands in the working tree at HEAD `c0a266d`, uncommitted.
- Date: 2026-08-19
- Reviewer: an independent agent with no write access to the code, working from a copy under
  `/tmp`. It authored none of the code under review.
- Method: read the claims first; then mutation (29 guards deleted or weakened in the copy,
  suite re-run) plus direct end-to-end probes over the real TLS stub and a live PostgreSQL
  cluster.
- Outcome: **1 major finding, 1 moderate, 3 minor, plus a set of green-mutation coverage
  gaps.** The two decisions' central claims — DP-020 D2 (a body cannot change the
  destination) and DP-018 D3/D6 (no credential value reaches a recorded artefact) — **held
  under real attack.** The gap is in DP-020 D3 (the body's byte-bound) and in the *breadth*
  of DP-018 D5.

## Why this exists

`[결정]` The same reason [ADVERSARIAL-REVIEW-2026-08-18.md](ADVERSARIAL-REVIEW-2026-08-18.md)
gives: the implementer and the author of every claim under review were the same party, so
this work had no independent axis. This is that axis, and it is committed **before any
repair**, for that document's stated reason — *"a review whose findings survive only as the
conclusions its subject chose to adopt is not evidence of anything."*

`[추론]` The 2026-08-18 review found its blocking defects in the *code*. This one found its
major defect in a **quantity**: a bound that counts the wrong thing. That is the same shape
as that review's own F1 — a limit stated in a contract with no counter behind it — reappearing
one level down, where the counter exists and measures something else.

## Verification by the author

`[측정]` Both load-bearing findings were reproduced independently by the author, with
different commands than the reviewer's, before this document was written:

| Finding | How it was independently confirmed |
|---|---|
| F1, byte count | `resolve('t', profile, body=[big])` against `max_request_bytes=64`: returned `PreparedRequest`, `len()` saw `1`, real body **100,011 bytes** — 1,562× the grant. The same payload as `bytes` was refused. |
| F1, deadline | Reading `domain/transport.py`: `connection.request(...)` is line 242 and `_arm(connection.sock, ...)` is line 244. The write precedes the deadline check. |
| F2, no cross-check | `grep -rn needs_credential` over `addon_host/` and `domain/`: two hits, both in prose comments in `outbound.py`. Nothing in `capabilities.py` reads it. |
| F2, no status gate | `grep -n status` over `capabilities.py`: `sent.status` is read only at line 438 to decide redirect-following, then passed to `_record_response` unexamined. |

`[측정]` F3 and F4 rest on the reviewer's measurements, quoted with the numbers it reported.
They have not been independently reproduced.

## Environment

`[측정]` Baseline for mutation testing was the scoped battery (`test_credentials`,
`test_outbound_policy`, `test_outbound_transport`, `test_capabilities`,
`test_normalizer_capability`, `test_domain_api`, `test_domain_store`, the four Naver add-on
test files, `test_secret_store_guard`, `test_redaction`, `test_addon_*`, plus
`tests/environment`): **510 passed, 12 skipped, 1 failed**. The one failure is environmental
— `test_secret_store_guard.py::test_sec_001_...` fails with `FileNotFoundError` /
`ssl.SSLContext.load_verify_locations` under the agent sandbox, which spawns a subprocess API
server; it is unrelated to DP-018/DP-020 and the reviewer treated `1 failed, 510 passed` as
the passing baseline. The running cluster socket was reachable from the sandbox, so the
socket-level claims were exercised, not reasoned about.

---

## F1 — DP-020 D3's body byte-bound counts elements, not bytes. **Major.**

**Claimed.** DP-020 D3: *"A body is bounded, and the bound is the platform's.
`max_request_bytes` … enforced in `resolve` before anything is sent."*
`addon_api.context.Limits`: *"An add-on that ignores these is still bounded — the platform
enforces every one of them whatever the add-on believes."* The packet cites
`ADVERSARIAL-REVIEW-2026-08-18.md` F1 by name as the reason the limit is stated *with a
counter* rather than in prose.

**Why it is false.** Both enforcement points — `domain/outbound.py:451`
(`if len(body) > limit`) and `addon_host/capabilities.py:389`
(`if body is not None and len(body) > limits.max_request_bytes`) — measure `len(body)`, which
equals the byte count only when `body` is exactly `bytes`. `CollectContext.fetch`'s `body` is
typed `bytes | None` and **nothing checks the type at runtime**. `http.client` accepts any
bytes-like or any iterable-of-bytes as a body: for a `list[bytes]` it emits
`Transfer-Encoding: chunked` and streams every chunk. So `len([big])` is `1`, both guards
pass, and the whole payload goes on the wire.

**Measured.** Through `domain.outbound.resolve` + `SocketTransport` into the TLS stub,
`max_request_bytes = 65536`, body `[json_blob]` of ~1 MiB (one list element):

```
resolve() saw len(body)=1 against a grant of 65536; real size 1048576
BYTES ON THE WIRE = 1049375   (16.0x grant)
REQUEST HEAD: POST /search-trend/v1/search / Transfer-Encoding: chunked / Content-Type: application/json
```

`[측정]` Reachable from actual add-on code through the full `JobRunner` → capability layer
path (not just `resolve`): an add-on calling `context.fetch("trend", {}, body=[PAD])` against
`max_request_bytes=65536` **succeeded** with `real bytes=1048576` recorded in
`transport.sent[0].body`. The positive control holds: the identical payload as `bytes`
(`b"A"*LIMIT*16`) is refused `REQUEST_TOO_LARGE`.

`[측정]` **Compounding consequence — the request budget does not bound the send.** `_arm`
(the monotonic-deadline check F5 added) is called *after* `connection.request(...)`, so the
request-write phase runs under the plain connect-time socket timeout, not the deadline. Once
the byte cap is evaded, the write of a large body is bounded by neither `max_request_bytes`
nor `max_request_seconds`. Against a server that drains slowly:

```
body 16 x 1 MiB, budget max_request_seconds = 0.5s  ->  send() occupied 18.83s   (38x the budget)
body  8 MiB list, budget 0.5s, server stalls 4s     ->  send() occupied  4.02s   ( 8x the budget)
```

This is exactly the F5 shape (occupancy linear in the payload, ~38×) reappearing on the
**write** side, which F5's read-side deadline never covered.

`[추론]` mypy tempers, but does not close, the hole. `--strict` flags `list[bytes]`,
`bytearray`, and `memoryview` bodies (`incompatible type … expected "bytes | None"`), so a
clean-typed add-on cannot pass the obvious forms. But `bytearray` is the natural way to
assemble a body incrementally, and a helper annotated `-> bytes` that returns a bytes-like,
or any value typed `Any`, slips past both mypy and the runtime. The claim under review is
specifically that *"the platform enforces … whatever the add-on believes"* — enforcement
delegated to the add-on's own static-analysis discipline is precisely not that. It re-opens
the F1 lesson the packet quotes: a limit whose counter counts the wrong quantity is not a
limit.

`[측정]` The redundant second check (`_fetch`, `capabilities.py:389`) is not defence in depth:
mutation **M7** (delete it entirely) left the baseline green, because it is
`len(body) > limit` identical to `resolve`'s and shares the identical flaw.

**Severity: Major, not blocking.** Reachability needs a loosely-typed bytes-like body; the
destination is never affected (see "what held"). But it falsifies a stated platform guarantee
and re-introduces a named prior finding's shape.

---

## F2 — DP-018 D5's "no anonymous request, no error-body-as-Raw" is narrower than stated. **Moderate.**

**Claimed.** DP-018 D5 / `secret-setup.md` invariant 4: *"An unresolvable credential is
`CONFIGURATION_INVALID`, never a retry and never an anonymous request … a source might answer
with a `200` and an error body"* — which a collector would store as Raw and a normalizer read
as data.

**Why it is narrower.** The protection is delivered only for a credential that is *named in
the profile but unresolvable* (missing store key). It does **not** cover two adjacent doors,
and the platform applies no status gate on responses at all (`_fetch` inspects `status` only
to decide redirect-following, `capabilities.py:438`; `_record_response` stores whatever came
back).

**Measured (a) — declared need, no grant.** `needs_credential` is the add-on's request and the
profile is the grant, but nothing cross-checks them (`grep`: `needs_credential` appears
nowhere in `capabilities.py`). Running the real `collector.naver.blog` (which declares
`needs_credential = true`) against a source whose profile has `credentials: []`, with the
secret store present and correct:

```
gateway saw credentials: []          # an anonymous request WAS sent
outcome.error = ...blog search rejected the configured credential (401)
```

The add-on here happens to police the 401. A collector that does not:

**Measured (b) — any non-2xx stored as Raw + SUCCEEDED.** A collector that emits from
`response.body` without checking status, run anonymously:

```
job state = SUCCEEDED   accepted = True   error = None
raw_envelope: [(401, '{"errorCode": "SE01", "errorMessage": "unauthenticated"}')]
raw_item:     [('page-1', '{"errorCode": "SE01", "errorMessage": "unauthenticated"}')]
```

The platform stored a 401 error body as a Raw *item* and reported success. This is the exact
outcome D5 names, reached not through an unresolvable named credential but through a
mis-granted profile plus the platform's unconditional storage of any status.

`[추론]` The invariant's protection rests entirely on the add-on policing status codes. The
"add-on trust boundary" section says the design guards against *accidental* exposure; a
collector that forgets a status check, or an operator who declares a need without a grant,
are accidents, and the platform does not catch either. Moderate: no credential value leaks,
but the stated Raw-integrity guarantee has an ungated path.

---

## F3 — `exception_message` is stored without value-level redaction. **Minor.**

**Claimed.** `platform_core/errors.py`: `ProtectedDetail` *"is redacted the way SEC-004
requires"*; the store comment: *"This column only stores what they already redacted."*

**Why it is unproven as a full guarantee.** `redact_mapping` masks a value only when its
**key** matches a sensitive name; string values under non-sensitive keys are returned verbatim
(`_redact` treats `str` as a leaf and never applies `redact_text` to it). `redact_text` is
applied only to the top-level `summary`, not to detail values. `translate` records
`exception_message=str(error)` for any unexpected exception (`errors.py:107`).

**Measured.**
```
redact_mapping({"exception_message": "Invalid header value b'X-Api-Key: super-secret-token-42'", "token": "…"})
  -> exception_message = Invalid header value b'X-Api-Key: super-secret-token-42'   (verbatim)
     token = [REDACTED]
```
So any exception whose `str()` embeds credential material lands unredacted in
`job_attempt.error_detail`.

`[추론]` End-to-end reachability with a *well-formed* credential is effectively nil: the store
parser (`splitlines()` + `.strip()`) cannot produce a value containing CR/LF or edge
whitespace, which are the only characters `http.client` rejects with a value-quoting
`ValueError`. The one reachable path is a non-Latin-1 credential (e.g. a Korean character),
which yields `UnicodeEncodeError` whose message escapes a single codepoint and its position —
a one-character partial disclosure of a credential that could never authenticate over HTTP
anyway. Minor, and recorded as measured-mechanism / inferred-reachability rather than a
demonstrated end-to-end leak. Worth naming because the redaction is key-based and the column's
docstring implies it is value-safe.

---

## F4 — Green mutations in DP-018/DP-020 scope: claims the suite does not defend. **Minor each.**

Each mutation was applied to the copy and the whole battery re-run without `-x`. RED = a test
caught it; GREEN = baseline unchanged.

| Mutation | Result | What it means |
|---|---|---|
| M16 `check_redirect` re-attaches the original method and body to the next hop | **GREEN** | DP-020's *"a redirect is followed as GET and the body is not carried"* is asserted nowhere. The runtime behaviour **is** correct (probe: hop 2 after a `307` POST is `method=GET, body=None`), so the code is right and the claim is untested. |
| M15 `resolve`: `if params and method == "GET"` → `if params` | **GREEN** | No test passes `params` **and** a POST `body` together, so nothing pins that a POST's query string stays empty when params are present. Behaviour-only (destination unaffected). |
| M7 `_fetch` drops its `max_request_bytes` check | **GREEN** | The redundant byte check adds no independent enforcement (see F1). |
| M19 `secret_store_path`: `path.resolve()` → `path.absolute()` | **GREEN** | Nothing pins symlink resolution. Related divergence measured below. |
| M23 `resolve_credential`: drop `value.strip()` | **GREEN** | The value-trimming is untested. |
| M18 `secret_store_path`: `is_file()` → `exists()` | **GREEN** | The regular-file requirement (which rejects FIFOs/dirs/devices — all three confirmed refused today) is untested. |

`[측정]` **Symlink divergence between the two store guards.** The launcher
(`scripts/with-secret-source.sh`) judges a store by its **link** location
(`dirname | pwd -P`); the application guard (`domain/secrets.py`) judges by `path.resolve()`,
its **target**. A symlink placed *inside* the working tree pointing at a store outside it is
**rejected by the launcher** but **accepted by the application guard** (`RESOLVED`). A symlink
*outside* the tree pointing at a file *inside* it is the reverse. `[추론]` The invariant ("no
credential file inside the working tree") is arguably satisfied either way — a committed
symlink carries no secret bytes — but the two guards do not agree on what the rule is, and M19
shows no test would notice if `secrets.py` stopped following the link. Minor.

`[측정]` **Recorded response headers are lossy for repeated names.**
`dict(response.getheaders())` keeps only the last of a repeated header (`Link: a` + `Link: b`
→ `{"Link": "b"}`). Not a credential issue — protected headers are still stripped correctly —
but a Raw-fidelity note against the losslessness Raw claims. Minor / `[추론]`.

---

## What the reviewer could not break

Recorded because a negative result from an adversary is evidence, and these survived a real
attempt rather than a reading.

- **DP-020 D2 holds: a body cannot change where a request goes.** `resolve` builds
  host/port/path only from the profile; `PreparedRequest.host`/`url` are what the transport
  dials; the body is placed only in the HTTP body. Mutations dropping the method allowlist
  (M8, M9) both went **RED**. A `307` redirect after a POST comes back **GET with no body**
  and re-validates host/port/path through `check_redirect` (measured); a cross-host `Location`
  is refused before the second hop is sent. The add-on supplies no header input to `fetch` at
  all, so there is no CRLF/`Content-Length`/`Transfer-Encoding` smuggling surface from add-on
  data. No request could be routed anywhere the profile did not grant, through the body or
  otherwise.

- **DP-018 D3/D6 holds: no well-formed credential value reaches a recorded artefact.** Request
  headers carrying the credential are **never recorded** — only `{url, host}` goes into
  `request_summary` (`capabilities.py:473`), and response headers pass through
  `strip_protected_headers`. Mutations that would leak: strip nothing (M2), drop 5 of 7
  `PROTECTED_HEADERS` (M1), drop the `PROTECTED_HEADERS` precondition on `credentials` (M10),
  stop sending the credential (M25) — **all RED**. End-to-end over the real socket into
  PostgreSQL, no `request_summary`, `response_headers`, `raw_item`, or log line carried the
  value; the `INSPECTING` add-on that reports everything reachable from its context found
  neither the value nor the ref.

- **`SecretValue` withholds under `repr`, `str`, f-string, and traceback** (measured;
  `__slots__`, no `__dict__`). The `repr`-reveal mutation (C2) went RED.

- **The method is unreachable from add-on input.** `PreparedRequest.method` is set only from
  `profile.method_of(...)`; `fetch` has no method parameter; the redirect path hardcodes GET
  via the dataclass defaults. Confirmed by reading every construction site.

- **CR/LF header injection through a credential is impossible from the store.** The store
  format (`splitlines()` + `.strip()`) cannot produce a value containing CR or LF, which are
  the characters `http.client` would reject while quoting the value.

- **The store location and mode guards hold** for the file itself. Mutations dropping the
  working-tree check (M12) and the mode check (M13) went RED; measured directly, modes
  `640/644/660/700/777` are refused and only `600/400` pass; a FIFO, a directory, and
  `/dev/null` are all refused. (Known limit, not a finding: a `600` store inside a
  world-writable *directory* is accepted — the launcher has the same limit, so this is
  consistent, not a regression.)

- **The two documented control mutations still fire.** `PROTECTED_HEADERS` dropping names →
  RED (6 failed); dropping `_check_no_refusal_was_swallowed` → RED (6 failed) — reproducing
  the author's own numbers and confirming the battery is actually exercising these paths.

## Carried from the prior review, still open and out of scope here

`[확인 사실]` M26 (`check_resolved_addresses` drops `is_reserved`) and the importer/`is_global`
items are `ADVERSARIAL-REVIEW-2026-08-18.md` F8/F6, already logged open. M26 went GREEN here
as it did there; it is an address-range matter, not DP-018/DP-020, and the reviewer did not
re-litigate it.

---

## Work items

Ranked. Nothing here is done; this list is the handoff.

| # | Finding | Severity | Shape of the fix | Status |
|---|---|---|---|---|
| 1 | F1 | Major | Count bytes, not `len`; and move `_arm` before `connection.request` | **DONE** |
| 2 | F2 | Moderate | Refuse a source whose add-on declares `needs_credential` and whose profile grants none; decide whether the platform gates response status before Raw | **DONE**, and narrower than it sounds — see below |
| 3 | F3 | Minor | Apply `redact_text` to string *values* in `redact_mapping`, or stop storing `exception_message` | open |
| 4 | F4 | Minor | A test per green mutation, starting with the redirect dropping its body (M16) | open |

### F1, repaired 2026-08-19

`[측정]` Both halves, test-first, each watched to fail for the stated reason before the code
changed.

**The byte count.** `domain.outbound._as_bytes` now converts the body to the bytes that will
actually be sent — `bytes` straight through, `bytearray`/`memoryview` copied, a sequence of
chunks joined — and **refuses a body it cannot measure**, because a generator cannot be sized
without consuming it and an unmeasured body is not a bounded one. The measured bytes are what
goes downstream, so the thing counted and the thing sent cannot differ. Seven cases went red
first: `list`, `tuple`, `iterator`, an arbitrary object, and the size the refusal reports.
Two positive controls guard the other direction — a `bytes` body under the grant and a
`bytearray` under the grant are both still accepted.

**The write-side deadline.** `_arm` now runs before `connection.request(...)` and again after
it, since the read is a fresh wait against the same deadline. `[측정]` The first version of
the test for this **passed against the defect** — it asserted only that the socket timeout was
re-armed, and `_connect` arms it too. Rewritten to record the sequence, it produced
`['write', 'arm', 'arm', 'arm']` and failed correctly. That is this review's own lesson
applied to its own repair: a test that checks presence where the defect is an *ordering*
proves nothing.

`[추론]` The redundant check in `capabilities.py` is left in place and still shares `resolve`'s
measurement — it is now correct because `resolve`'s is, and M7 would presumably still go
green. Whether a check that cannot fail independently should exist at all is F4's question,
not F1's.

### F2, repaired 2026-08-19 — and what the repair does not reach

`[결정]` The two halves needed different answers, because only one of them is a judgement.

**F2(a) — a declared need with no grant — is refused before any request.** An add-on whose
manifest says `needs_credential` running against a profile with no `credentials` entry is
`CONFIGURATION_INVALID` at the start of the run. `needs_credential` is the add-on's request
and the profile is the operator's grant; nothing had ever compared them. No judgement was
required and none was made.

**F2(b) — a non-success status — is the add-on's to judge, and the platform enforces that it
judged.** A `404` is "no results" to one source and "wrong endpoint" to another; the platform
cannot know, and putting that knowledge in it is source semantics in `platform_core`. So
every non-2xx response is recorded and a run that returns normally without either raising or
calling the new `accept_status(response, reason)` fails. Contract `1.1 → 1.2`, additive.
`reason` is required and logged, because an operator reading Raw six weeks later needs to see
*why* someone treated a `404` as data.

**`[측정]` The repair is narrower than "the platform now enforces this", and saying so is the
point.** Three limits, none of them closable:

1. **It is not unswallowable the way a refusal is.** Swallowing a refusal fails; calling
   `accept_status` on every response succeeds, and restores the pre-check behaviour exactly.
   The platform cannot separate a considered acceptance from a reflexive one without knowing
   the source. What changed is the *default* — silence used to succeed — and the price of
   buying the old behaviour back is a call and a written reason per response, both logged.
2. **It sees nothing of a source that answers `200` with an error body.** The platform reads
   a status, not a meaning. `collector.naver.blog`'s first `[가설]` is about exactly that case
   and it remains the add-on's alone.
3. **`[추론]` The useful successor is a signal, not a stronger check.** A run that accepted
   many statuses, or a normalization whose `skipped` equals its `item_count`, is anomalous
   without any source knowledge — and both numbers already exist and are simply not surfaced.

**`[측정]` Cost of the contract addition, measured.** A required field on `CollectContext`
broke **70 tests** across **four** context-construction sites — the host, the `addon_kit`
harness, and two test modules. **Zero add-ons changed**, because an add-on consumes a context
and never builds one. `[추론]` So the cost of evolving this contract is proportional to the
number of *construction* sites and not to the number of add-ons, which is the opposite of
N1's finding about duplication and belongs beside it in the Architecture Synthesis. Given a
default the field would have cost nothing and said nothing; the 70 failures were the contract
announcing that it had changed.

## What was changed immediately

`[결정]` Only the false claims, and only to make them true statements about what exists.
`AGENTS.md` names a claim stated in the present tense that the code does not deliver as a
failure mode of its own, and a false claim left standing while a fix is scheduled is a claim
someone will act on in the meantime:

- `addon_api/context.py::Limits` — no longer says the platform enforces **every** limit
  whatever the add-on believes. It names the exception and points here.
- `domain/outbound.py::resolve`'s body-limit refusal and `addon_host/capabilities.py::_fetch`
  — both now say what they measure, and that it is `len` rather than a byte count.
- `domain/transport.py::_hop` — no longer implies the deadline bounds the whole request. It
  says the write is outside it and names F1.
- `DP-018`'s D5 and `DP-020`'s D3 — the two decisions gain a measured note recording that the
  claim as written is broader than the code delivers.
