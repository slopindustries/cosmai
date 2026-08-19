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
checks that an `ACCEPTED` packet has such a link and that the link resolves.

## What a report is

Create it from [`../ATTACK-REPORT-TEMPLATE.md`](../ATTACK-REPORT-TEMPLATE.md). Use a stable
name such as `REVIEW-TASK-007.md`.

The report records reproducible `PASS`, `FAIL`, or `BLOCKED` evidence. It does not contain
implementation repairs, credentials, private data, or private evaluation material.
