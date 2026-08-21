"""The scheduler: polls `cosmai.schedule` and wakes due sources (M6 batch 6a).

See `apps/scheduler/store.py` for the data access and `apps/scheduler/__main__.py`
(`python -m scheduler`) for the process. DP-033 D5.
"""

from __future__ import annotations
