"""The P1 platform operator HTTP API (DP-006 D1).

Copy-adapted from ``experiments/integrated-p0/platform_core/api/__init__.py``.
Deliberately the smallest surface that lets two security scenarios be executed
rather than asserted in prose:

* ``SEC-002`` needs a process that binds a socket, so that the address it bound to
  is a recorded observation instead of a claim in a document.
* ``SEC-004`` needs a default representation and a protected-debug
  representation of the same rows, so that "``error_detail`` is absent by default"
  and "protected does not mean unredacted" are both testable.

Everything an operator would actually want — a job list, log retrieval, safe
retry, metrics — belongs to the `OPS` scenarios and is not here. Adding it now
would mean shipping endpoints no scenario reads.
"""

from __future__ import annotations

from platform_core.api.app import create_app

__all__ = ["create_app"]
