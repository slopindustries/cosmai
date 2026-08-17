# `OPS` evidence — 2026-08-17, base revision `5b26d47`

Evidence for `OPS-001` … `OPS-004`, whose `Verification` sections all point at
`experiments/integrated-p0/evidence/<date>-<sha7>/`. Linked experiment record:
[EXP-001](../../EXP-001-platform-core.md).

## What is here

| File | What it is | Which scenario asked for it |
|---|---|---|
| `ENVIRONMENT.md` | code revision, versions, configuration with secrets removed, reproduction commands | all four; the template's `Environment` section |
| `platform.jsonl` | a real sample of the structured log, from four worker processes and one API process writing to one file | `OPS-003`'s transport, and the log shape `CONTRACT-JOB@0.1` requires |
| `ops-003-correlated-events.json` | the correlated event set exactly as the API returned it, with the job, its attempts, and the control job's identifiers beside it | `OPS-003` names this artefact explicitly, "since it is the artifact the gate reviewer would otherwise have to take on trust" |
| `sec-002-listeners.txt` | how many TCP sockets were listening and how many were PostgreSQL, plus the socket-versus-TCP readings from the session itself | `SEC-002` steps 4 and 5, re-captured because `OPS-001`'s preconditions rest on the loopback binding |

## What is deliberately not here yet

- **The full `pytest` output.** It belongs to the S6 run against the revision that
  lands this work, and a copy taken now would be evidence about a working tree
  nobody can check out. `ENVIRONMENT.md` records the counts and timings measured on
  2026-08-17 as `[측정]`; the transcript is S6's.
- **Dashboard screenshots.** No dashboard exists — it is T5b. Four assertions
  across the `OPS` and `SEC` families need one, and each is recorded as an unmet
  requirement in its scenario's `Result` section rather than waved through:
  `SEC-004` steps 3–4, and the `OPS` results' notes on where an operator would
  actually read these fields. A field that exists but is never rendered does not
  satisfy the charter's diagnosis criterion.
- **A `by which version` answer.** `OQ-005`'s evidence list asks it. P0-A has no
  versioned producer at all, so the question has no P0-A answer and is left absent
  rather than approximated by the code revision. It becomes answerable in P0-B.

## Data class

`public`, and committable — with one qualification worth reading before the
directory is treated as uniformly synthetic.

- `platform.jsonl` and `ops-003-correlated-events.json` are **entirely synthetic**.
  Every job was created by a synthetic handler, every payload is a literal from
  `tests/test_ops.py`, and no value came from outside this machine. They contain no
  credential, no personal data, and no `error_detail`: the API strips protected
  detail on the way out, and the log never carries it at `INFO`.
- **`sec-002-listeners.txt` was narrowed after its first capture.** It originally
  committed the whole `lsof` listing, on the reasoning that `SEC-002` says a claim in
  a document is not evidence and a filtered listing would be exactly that. The
  reasoning holds against a *filtered* listing and this is not one. The listing named
  unrelated processes on this machine, their pids, and their loopback ports — host
  state that is not this project's data, and `docs/conventions/data-handling.md`
  gives `public` as "재배포 가능", which committing someone's machine inventory is
  not. What the file now records is a narrower question answered in full: how many
  sockets were listening, and how many of them were PostgreSQL. Both counts are
  complete answers, and keeping the total is what stops a zero from reading as "the
  command failed". A reviewer who wants the enumeration runs the recorded command on
  their own host.
- The `worker_id` values in the log and the captured response are the platform's own
  `hostname-pid`, so they name this machine. That is inherent: `OPS-003` needs two
  distinguishable process identities and the platform has no other way to produce
  one.

## Integrity

```
a802c5f6dd64179f0a2d739cc02c23df8f85f9017f05b44a72f45dce210a392f  platform.jsonl
f65f4e55cbbefb2e5095d5f087d19231be253e279976017cc3d5837ee1141af1  ops-003-correlated-events.json
57a3d5ed8bda3c4e0bd47c856fdcf9f0acaefd2d66ee22efab38a69b7abf7d9c  sec-002-listeners.txt
```

Verify with `shasum -a 256 -c` against the list above, from inside this directory.

**These three files are not byte-reproducible.** They carry generated UUIDs, database
timestamps, process ids, and counts taken from a live host, so a second capture
produces a different file with the same structure. What is reproducible is the assertion set:
`./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k ops_003`
asserts every property these artefacts illustrate, and it is the authority if the two
ever disagree.

## Reading `ops-003-correlated-events.json`

The `response` object is the whole of `GET /events?correlation_id=…`. Nine events came
back for one identifier, and the four `OPS-003` names are all there:

1. `job.transition` to `RUNNING`, `attempt_no` 1, `worker_id` of the first process —
   the claim.
2. `job.effect_applied`, naming the `effect_key` — the work the first process
   finished before it died.
3. `job.attempt_abandoned`, `attempt_no` 1, `error_class` `LEASE_ABANDONED`,
   `reclaimed_by` the second process — the reclaim that closed the abandoned attempt.
4. `job.effect_suppressed`, same `effect_key` — the second process finding the effect
   already applied.
5. `job.transition` to `SUCCEEDED`, `attempt_no` 2 — how the job ended.

The two `worker_id` values differ and the `correlation_id` is identical across them,
which is invariant I5 observed across a boundary no in-memory context survives. The
`control` block records that an unrelated job's five events were in the same file and
reachable by their own identifier, and are absent from this response.
