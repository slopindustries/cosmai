"""Synthetic handlers for the disposable P0-A platform core.

These exist to make platform behavior observable, and they are the whole of what
P0-A runs. A handler here succeeds, fails, halts its own process, or leaves the
single durable effect the contract permits. None of them fetches anything,
parses anything, or transforms anything, because DP-005 puts every one of those
after the P0-A Completion Gate and a test double that pretended to do them would
be the domain starting early under a different name.

What is being tested is the platform around the handler: whether a claim is
exclusive, whether an interrupted attempt recovers, whether a repeated delivery
produces one effect. A handler that behaved plausibly would add nothing to any of
those and would make the evidence harder to trust.
"""
