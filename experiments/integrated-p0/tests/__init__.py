"""Marks this directory as a package so its ``conftest`` has a qualified name.

Nothing here is imported for its contents. The file exists because two
``conftest.py`` files now live in the repository — one for the whole session under
``tests/``, one for the P0-A database fixtures here — and a type checker walking
the tree resolves both to the bare module name ``conftest`` unless one of them
sits inside a package. With this file, ``mypy .`` sees ``tests.conftest`` here and
``conftest`` at the repository root, and checks both instead of refusing to check
either.

pytest is unaffected: ``experiments/integrated-p0`` is already on the path, so the
modules beside this one are imported as ``tests.*`` rather than as bare names, and
fixtures resolve exactly as before.
"""
