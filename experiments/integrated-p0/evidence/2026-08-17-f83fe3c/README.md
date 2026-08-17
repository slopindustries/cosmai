# P0-A evidence — 2026-08-17, revision `f83fe3c`

Evidence for the `OPS`, `SEC`, and `JOB` families, whose `Verification` sections all
point at `experiments/integrated-p0/evidence/<date>-<sha7>/`. Linked experiment
record: [EXP-001](../../EXP-001-platform-core.md).

**The directory is named for the revision whose code produced these artifacts, and the
name is checkable.** The commit adding this directory changes no code, so:

```sh
git diff 07b0688..HEAD -- experiments/integrated-p0/platform_core \
                        experiments/integrated-p0/tests \
                        experiments/integrated-p0/dashboard/src   # must be empty
```

Getting here took two corrections, both found by review. The directory was first named
`5b26d47`, the revision the work started from, which has no `/events` endpoint at all.
Renaming it to `60807cb` was no better: that tree could not produce these artifacts
either, and the tests that wrote them did not exist there. The defect was not the name
but the mechanism — a test that writes during a run cannot name the revision that
produced its output, because the name is only knowable afterwards.

So capture is now **opt-in**:

```sh
./scripts/with-database.sh uv run pytest -k "ops_003 or sec_004" \
    --capture-evidence=experiments/integrated-p0/evidence/2026-08-17-f83fe3c
```

An ordinary run writes nothing here. That is what makes the hashes below verifiable —
while the scenarios rewrote them on every run, three of four checksums failed against
their own recorded list, which reads as tampering rather than as freshness.

There is one directory rather than one per slice, for the same reason a gate reviews one
revision.

## What is here

| File | What it is | Which scenario asked for it |
|---|---|---|
| `ENVIRONMENT.md` | code revision, versions, configuration with secrets removed, reproduction commands | all four; the template's `Environment` section |
| `platform.jsonl` | a real sample of the structured log, from four worker processes and one API process writing to one file | `OPS-003`'s transport, and the log shape `CONTRACT-JOB@0.1` requires |
| `ops-003-correlated-events.json` | the correlated event set exactly as the API returned it, with the job, its attempts, and the control job's identifiers beside it | `OPS-003` names this artefact explicitly, "since it is the artifact the gate reviewer would otherwise have to take on trust" |
| `sec-004-detail-screen.txt` | every job-detail screen `SEC-004` asserts over, rendered from real API responses by the same component tree the browser mounts | `SEC-004` step 3's reading half |
| `sec-002-listeners.txt` | how many TCP sockets were listening and how many were PostgreSQL, plus the socket-versus-TCP readings from the session itself | `SEC-002` steps 4 and 5, re-captured because `OPS-001`'s preconditions rest on the loopback binding |

## What is deliberately not here yet

- Nothing further is withheld for timing reasons. `pytest-output.txt` is the full
  transcript at this revision.
- **A dashboard screenshot.** The dashboard now exists, and `sec-004-detail-screen.txt`
  holds the screens as rendered — that is `SEC-004` step 3, the reading half, and it
  runs on every `-k sec_004`. Step 4's screenshot is still absent: it needs a browser
  driver, and [DP-006](../../../../docs/decisions/DP-006-p0a-platform-foundation.md) D6
  puts the dashboard's dependency floor below one. The gap is narrow and real — a value
  hidden by CSS or parked in a DOM attribute would pass a text search and fail a
  person's eyes — and `SEC-004`'s `Result` states which half was executed how.
  `dashboard/README.md` records the manual capture procedure.
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
- `sec-004-detail-screen.txt` is synthetic on the same terms and is written by the
  scenario that asserts over it, so a capture cannot describe what the assertions did
  not check. It carries the
  redaction marker where each reserved value was removed, and the ordinary marker that
  proves the search would have found a leak.
- The `worker_id` values in the log and the captured response are the platform's own
  `hostname-pid`, so they name this machine. That is inherent: `OPS-003` needs two
  distinguishable process identities and the platform has no other way to produce
  one.

## Integrity

```
83d6e9daf7e922cddfd18dc4033fde6f24571993ddaee36726c95c89944d9e83  platform.jsonl
acecc1cad455a6ac435199b1557c82972bccfc2642c5d70f865706fa4e132fca  ops-003-correlated-events.json
57a3d5ed8bda3c4e0bd47c856fdcf9f0acaefd2d66ee22efab38a69b7abf7d9c  sec-002-listeners.txt
d9f73d2ad69d511b07ea0d8f6738bf342399f80e15a9f0946e37d0e234ab11ff  sec-004-detail-screen.txt
```

Verify with `shasum -a 256 -c` against the list above, from inside this directory.

**These four files are not byte-reproducible.** They carry generated UUIDs, database
timestamps, process ids, and counts taken from a live host, so a second capture produces
a different file with the same structure. The hashes therefore identify *this* capture;
they are not a checksum a future run reproduces. Verify them to confirm the committed
bytes are the ones the list describes — which is what they are for, and which was
impossible while an ordinary test run rewrote them. What is reproducible is the assertion set:
`./scripts/with-database.sh uv run pytest experiments/integrated-p0/tests -k "ops_003 or sec_004"`
asserts every property these artefacts illustrate, and rewrites them, and it is the authority if the two
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
