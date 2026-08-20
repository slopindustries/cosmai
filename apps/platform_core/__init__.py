"""Import root for the P1 platform core.

This is the reconstruction tree DP-032 and the P1 Entry Gate authorize:
production-track code under ``apps/``, not disposable experiment code. It is a
separate ``uv`` project with its own ``.venv`` (``cd apps && uv run ...``) and
imports nothing from ``experiments/`` — P0 code may be read, copied, and
adapted, never imported (``../README.md``).

Several modules here are copy-adapted from ``experiments/integrated-p0/`` and
say so at the top: the platform-config and secret-reader logic (SEC-001 through
SEC-003) and the numbered-SQL migrator (DP-006 D4) carry forward; the database
placement they serve has moved from a repository-local, passwordless, Unix-socket
cluster to a dedicated database on a shared server reached over loopback TCP with
a password (DP-032).
"""
