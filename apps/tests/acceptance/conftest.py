"""Fixtures shared by the `JOB` acceptance scenarios (Task 9).

Copy-adapted from ``experiments/integrated-p0/tests/conftest.py``'s
``registry``/``runner`` block. P0 built those against its per-test cloned
database; this package builds them against `job_store`, which is already wired
to the shared, row-reset ``cosmai_test`` schema (see
``../conftest.py``'s module docstring). The handler table is the real
``platform_core.handlers.synthetic`` registry the worker process itself uses
--- not a scenario-local stand-in --- so a `JOB-00N` test here exercises the
same handlers ``python -m platform_core.worker`` would.
"""

from __future__ import annotations

import pytest

from platform_core.handlers.synthetic import synthetic_registry
from platform_core.jobs.registry import HandlerRegistry
from platform_core.jobs.runner import JobRunner
from platform_core.jobs.store import JobStore
from tests.conftest import LEASE_SECONDS, WORKER


@pytest.fixture
def registry() -> HandlerRegistry:
    return synthetic_registry()


@pytest.fixture
def runner(job_store: JobStore, registry: HandlerRegistry) -> JobRunner:
    return JobRunner(job_store, registry, worker_id=WORKER, lease_seconds=LEASE_SECONDS)
