"""Data access for the scheduler's one pass (M6 batch 6a; DP-033 D5).

The convention is `platform_core.jobs.store.JobStore`'s and `domain.store.
DomainStore`'s: the connection is the caller's, nothing here commits or opens a
transaction, and every method is one statement (`lock_schedule` is the one
whose whole point *is* the row lock it takes, held by whatever transaction the
caller already opened around it — see `apps/scheduler/__main__.py`'s
`_process_source`, the only caller that matters).

**Three statements, three jobs.** `due_source_ids` is a cheap, unlocked scan —
a *hint*, not a decision, because nothing stops its answer from being stale by
the time a caller acts on it. `lock_schedule` is the decision: it re-applies
the same due/enabled predicate under `for update of s`, so a schedule another
scheduler process (or a concurrent write) already handled, disabled, or
un-dued since the scan simply is not returned, and the caller's "nothing to
do" path and "the row changed under me" path collapse into the same `None`.
`non_terminal_job_exists` is the duplicate-suppression check the M6 brief asks
for by name: whether a `PENDING`/`RUNNING` job already carries this exact
handler and `source_id` in its payload — read inside the same transaction that
holds the schedule row locked, so nothing else claiming the same source can
race between the check and the job this pass may go on to create.

**Why the lock is only on `schedule`, not `source`.** `[가설]` A second scheduler
process (there is ordinarily one, but nothing here assumes exactly one) racing
this one should block on the schedule row it is about to act on, not on the
source row every other read of that source also touches — `domain.api`'s own
routes should stay unaffected by a scheduler pass in flight. This is
`for update of s`'s documented Postgres semantics, not a novel claim, but
`docs/p1/M6-RECORD.md` (M-C5, `docs/agent-workflow/reviews/REVIEW-M2-M7.md`)
is explicit that every scheduler test to date is a sequential `--once` run —
no test has actually run two scheduler processes against the same row
concurrently, so this paragraph describes the mechanism's design, not a
measured behavior.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

#: Unlocked candidate scan — see this module's docstring. Filters on both the
#: schedule's own `enabled` and the source's, so a schedule left enabled on a
#: source the operator has since disabled is not a candidate at all: a job
#: nothing can meaningfully run against is not a smaller version of "wake this
#: source up", it is a job that sits `PENDING` forever with no operator action
#: that explains why.
DUE_SOURCE_IDS = """
select s.source_id
from cosmai.schedule s
join cosmai.source src on src.source_id = s.source_id
where s.enabled and src.enabled and s.next_run_at <= now()
order by s.next_run_at
"""

#: The decision, re-applying `DUE_SOURCE_IDS`'s own predicate under a row lock
#: so a stale candidate (already handled, disabled, or advanced since the scan)
#: comes back `None` rather than being acted on twice. `addon_id` is read here
#: because it is what turns a locked, due source into the handler name a
#: collect job needs — see `apps/scheduler/__main__.py`'s `HANDLER_PREFIX`.
LOCK_SCHEDULE = """
select s.source_id, src.addon_id
from cosmai.schedule s
join cosmai.source src on src.source_id = s.source_id
where s.source_id = %(source_id)s
  and s.enabled
  and src.enabled
  and s.next_run_at <= now()
for update of s
"""

#: Whether a job with this exact handler and `source_id` payload field is still
#: `PENDING` or `RUNNING` — the duplicate the M6 brief asks this store to
#: suppress. `payload ->> %(source_id_field)s` reads `null` (never an error) on
#: a payload that is not a JSON object or does not carry the field, which is
#: the correct answer ("not this one") rather than a fault.
NON_TERMINAL_JOB_EXISTS = """
select exists (
    select 1
    from cosmai.job
    where handler = %(handler)s
      and state in ('PENDING', 'RUNNING')
      and payload ->> %(source_id_field)s = %(source_id)s
) as found
"""

#: `now()` here, not the schedule's own stale `next_run_at` plus the interval —
#: the same "the database owns every timestamp" rule `platform_core.jobs.store`
#: states for a job's lease and availability, applied to the same kind of
#: decision.
ADVANCE_SCHEDULE = """
update cosmai.schedule
set next_run_at = now() + make_interval(secs => interval_seconds),
    last_run_at = now()
where source_id = %(source_id)s
"""


class SchedulerStore:
    """Data access for one scheduler pass. One instance per connection, no commits."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    def due_source_ids(self) -> list[str]:
        """Every source that looks due right now. A hint — see this module's
        docstring — not a lock, and not a guarantee any of these still are by
        the time a caller reaches `lock_schedule`."""
        with self._cursor() as cursor:
            cursor.execute(DUE_SOURCE_IDS)
            return [str(row["source_id"]) for row in cursor.fetchall()]

    def lock_schedule(self, source_id: str) -> dict[str, Any] | None:
        """Lock and re-verify one schedule is still due and enabled, or return
        `None` if it no longer is. Must run inside the caller's own transaction —
        the lock this takes is released when that transaction ends, and a caller
        on an autocommit connection that did not open one holds it for exactly
        the duration of this one statement, which defeats the point."""
        with self._cursor() as cursor:
            cursor.execute(LOCK_SCHEDULE, {"source_id": source_id})
            return cursor.fetchone()

    def non_terminal_job_exists(self, handler: str, source_id_field: str, source_id: str) -> bool:
        with self._cursor() as cursor:
            cursor.execute(
                NON_TERMINAL_JOB_EXISTS,
                {"handler": handler, "source_id_field": source_id_field, "source_id": source_id},
            )
            row = cursor.fetchone()
        return bool(row is not None and row["found"])

    def advance(self, source_id: str) -> None:
        """Move this source's `next_run_at` forward by its own interval and
        record `last_run_at`. Called only after a job was actually created —
        see `apps/scheduler/__main__.py`'s `_process_source`."""
        with self._cursor() as cursor:
            cursor.execute(ADVANCE_SCHEDULE, {"source_id": source_id})

    def _cursor(self) -> psycopg.Cursor[dict[str, Any]]:
        return self._connection.cursor(row_factory=dict_row)
