"""Handler-neutral job execution for the disposable P0-A platform core.

This package is CONTRACT-JOB@0.1 expressed as code: the state machine
(``state``), the hand-written SQL that moves a job through it (``store``), the
name-to-callable table the platform dispatches through (``registry``), and the
single execution pass a worker process will later loop over (``runner``).

Nothing here knows what a job means. A handler receives an opaque payload and may
produce exactly one durable effect; where that payload came from, what it says,
and what the effect stands for are all outside P0-A by DP-005.

**This module deliberately imports nothing.** ``platform_core.obs.metrics`` reads
``jobs.state`` for the four job states, so an import in this file would close a
cycle between instrumentation and the state machine it labels.
"""
