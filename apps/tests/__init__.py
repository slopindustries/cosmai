"""Makes ``tests`` an importable package.

Needed so ``from tests.conftest import ...`` (Task 7/8's process helpers,
shared between ``test_worker.py`` and ``test_api.py``) resolves to one
unambiguous module under mypy instead of colliding with pytest's own
``conftest`` discovery — the same reason
``experiments/integrated-p0/tests/__init__.py`` exists.
"""
