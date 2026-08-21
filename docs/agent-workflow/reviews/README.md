# Agent Attack Reports

## Where a report goes

`[결정]` An attack report on **experiment work belongs beside that experiment**, not here.

The precedent and the reason are in `c0a266d`, which committed the 2026-08-18 review as
[`experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md`](../../../experiments/integrated-p0/ADVERSARIAL-REVIEW-2026-08-18.md)
"beside the work rather than summarised into it", because *a review whose findings survive
only as the conclusions its subject chose to adopt is not evidence of anything.*
`[추론]` A report filed away from the artifact it attacks is easier to summarize away
later, and the summary is always written by the side that lost.

This directory holds reports on work that has **no experiment record** — a convention, a
template, a repository guard, a document that claims something is in force. Link the report
from the reviewed packet in either case; `tests/environment/test_agent_packet_record.py`
checks that an `ACCEPTED` packet's `Attack report:` carries exactly one such link and that it
resolves to a file inside this repository. It does not read the file — whether what it points at
is a real review is not something a path check can know, and
[`REVIEW-TASK-001-R2`](REVIEW-TASK-001-R2.md) F8 records that `.git/config` would satisfy it.

## Who commits it

`[결정]` The attacker does not commit its own report: it returns the report body and **the
session under review commits it.** That is a convention, not a consequence of the tool denial —
an earlier revision of this sentence wrote "is denied `Write` and `Edit`, **so** it returns the
report body", which the next paragraph refutes
([`REVIEW-TASK-001-R2`](REVIEW-TASK-001-R2.md) F7).
That is the one place independence leaks, and the rule that closes it is the one `c0a266d`
followed: commit the body **verbatim**. A report paraphrased by its subject is the thing
`reviews/README.md` opens by rejecting.

`[추론]` The leak is real rather than theoretical, because the denial is not a write barrier —
[`REVIEW-TASK-001`](REVIEW-TASK-001.md) F1 measured an attacker writing through `Bash`. So
nothing prevents an attacker from filing its own report either. The reason to keep the
transcription convention is not that the attacker cannot write; it is that a report and its
repair should not arrive in the same hand.

## What a report is

Create it from [`../ATTACK-REPORT-TEMPLATE.md`](../ATTACK-REPORT-TEMPLATE.md). Use a stable
name such as `REVIEW-TASK-007.md`.

The report records reproducible `PASS`, `FAIL`, or `BLOCKED` evidence. It does not contain
implementation repairs, credentials, private data, or private evaluation material.
