# DP-023 — SEC-006 is waived for P0, deliberately and with the exposure stated

- Status: `ACCEPTED_FOR_POC`
- Date: 2026-08-19
- Owners: Project team
- Waives: [`p0-security.md`](../conventions/p0-security.md) `SEC-006`, for the duration of P0 only
- Raised by: [ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md](../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-19-MUTATION.md) B1, **Blocking**
- Must be closed before: P1 Entry Gate

## Decision question

`p0-security.md` `SEC-006` requires, in bold, that the agent sandbox's `allowedDomains` be
narrowed from P0-A's `["*"]` to the registered source hosts **before the first source probe
makes a real outbound request**, that `deniedDomains` be added, and that
`autoAllowBashIfSandboxed` be re-examined.

`[확인 사실]` It was not done. Three collectors have run against the real NAVER API Hub with
credentials while `.claude/settings.json` still holds `"allowedDomains": ["*"]`,
`"autoAllowBashIfSandboxed": true`, and no `deniedDomains`. The independent mutation review
found this and classified it Blocking.

So: narrow it now, or accept the exposure and say what is being accepted?

## Decision

`[결정]` **Accept the exposure for P0. Do not narrow the sandbox.** Recorded here rather
than left as an unperformed item, because an unperformed requirement and a waived one look
identical in a settings file and are completely different things to a reader.

## What is actually unprotected

`p0-security.md` describes the sandbox as the **second** enforcement point: *"application
검증에 결함이 있어도 샌드박스가 egress를 막는다."* Waiving it means outbound safety rests
entirely on the first point — the application's own outbound guard.

`[측정]` That guard is not hypothetical and it is not untested. The independent security
review of the same day attacked it directly and could not route a request anywhere the
profile did not grant: `resolve` builds host, port, and path only from the operator-approved
row; the transport dials an address it checked; every redirect is revalidated by the same
function; and mutations dropping the method allowlist, the protected-header precondition, and
the header stripping all went RED.

`[추론]` **But that is exactly the argument SEC-006 exists to distrust**, and this session is
the evidence against it. The application guard had, in one day: a byte bound that counted
elements instead of bytes and let 1 MiB through a 64 KiB grant; a request-write phase outside
its own deadline; a redirect path range bypassable by dot segments; and a page limit enforced
nowhere. Every one was found and repaired, and every one existed while the guard was believed
sound. A second line of defence is worth having precisely for the defects nobody has found
yet, and this decision gives it up.

## Why it is nonetheless acceptable for P0, and only for P0

- `[확인 사실]` **P0 is disposable and single-operator.** It runs on one developer machine,
  against sources one person registered, with a credential that person issued. There is no
  multi-tenant surface and no untrusted operator.
- `[확인 사실]` **The add-ons are trusted code.** DP-008 D10 already states that in-process
  add-ons are trusted and that isolation is contractual and test-enforced rather than
  enforced by the operating system. A sandbox that constrained egress would not change what
  an in-process add-on could attempt.
- `[추론]` **The narrowing has a cost that lands on the wrong activity.** The same sandbox
  governs the agent's own tooling — package installs, documentation fetches, `uv`. Narrowing
  `allowedDomains` to source hosts stops the work rather than the risk, and a control that
  gets switched off to make progress is a control nobody has.
- `[결정]` **The trade is time-boxed by the artifact's own lifecycle.** P0 code does not
  become P1, so nothing built under this waiver inherits it.

## Obligations this decision creates

1. **The P1 Entry Gate must not accept a plan that carries this forward.** P1 runs against
   real sources with real credentials and is not disposable; SEC-006 applies there in full
   and this packet expires at that boundary.
2. **`p0-security.md`'s `SEC-006` row is annotated to point here**, so a reader meets the
   waiver at the requirement rather than discovering the gap by measurement, as this review
   had to.
3. **The Architecture Synthesis records it as an accepted risk**, not as a completed control.
   `SEC-006` cannot appear in a list of satisfied acceptance evidence.

## Falsification

This decision is wrong if any of the following becomes true during P0:

| Claim | Falsified by |
|---|---|
| The exposure is bounded by P0's single-operator scope | A second operator, a shared machine, or a source registered by someone who did not read the profile |
| The application guard is the only thing that needed to hold | An outbound defect that reaches a host no profile granted — the class this session found four of, but reaching further |
| The narrowing would cost more than it protects | A configuration that narrows source egress without touching the agent's own tooling |
