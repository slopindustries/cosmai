"""Synthetic handlers for the P1 platform core.

Copy-adapted from ``experiments/integrated-p0/platform_core/handlers/__init__.py``.
These exist to make platform behavior observable, and they are what T9's
scenario evidence runs against. A handler here succeeds, fails, halts its own
process, or leaves the single durable effect the contract permits. None of them
fetches anything, parses anything, or transforms anything — that boundary was
P0-A's, and this milestone reconstructs the platform core it proved, not a new
domain layer above it.

What is being tested is the platform around the handler: whether a claim is
exclusive, whether an interrupted attempt recovers, whether a repeated delivery
produces one effect. A handler that behaved plausibly would add nothing to any of
those and would make the evidence harder to trust.
"""
