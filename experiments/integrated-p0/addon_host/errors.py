"""The boundary where an add-on's failure becomes the platform's.

``addon_api.errors`` says why this file has to exist: an add-on cannot import
``platform_core.errors`` — that is the dependency DP-008 D1 breaks — so the
contract carries its own taxonomy and the host maps it here. Without this
translation the decoupling would be nominal, because an add-on importing the
platform's error classes is an add-on that imports the platform.

Two kinds of failure meet in this module and they are kept apart, the way
``addon_api.manifest`` keeps its two hierarchies apart:

* **Job time.** An add-on raised something while running. :func:`translate` turns
  it into a ``PlatformError`` whose class decides retryability. The add-on says
  what kind of failure it hit and nothing more; the attempt budget, the retry
  schedule, and the operator-visible error code stay with the platform, which is
  the only party that knows them.
* **Process start.** The installed set itself is wrong — an add-on written against
  another contract version. :class:`AddonRefusedError` is a
  ``ConfigurationInvalidError``, so a supervisor restart fails identically instead
  of eventually succeeding, which is the rule SEC-003 already fixes for every
  other configuration refusal.

The unexpected case is the load-bearing one. An add-on that raises something
outside the contract's taxonomy has not thereby escaped classification: it becomes
a permanent failure and the exception's type is recorded, so "the add-on is
broken in a way nobody anticipated" is a stated outcome rather than a traceback
reaching the worker loop.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any, Final

from addon_api import (
    AddonConfigInvalid,
    AddonError,
    AddonManifest,
    AddonOutputInvalid,
    AddonPermanent,
    AddonTransient,
)
from platform_core.errors import (
    ConfigurationInvalidError,
    PlatformError,
    PlatformPermanentError,
    PlatformTransientError,
)

__all__ = [
    "TRANSLATIONS",
    "UNEXPECTED_TRANSLATION",
    "AddonRefusedError",
    "translate",
    "translated_failures",
]


class AddonRefusedError(ConfigurationInvalidError):
    """An installed add-on is refused before any job runs (DP-008 D3).

    A ``ConfigurationInvalidError`` because that is what it is: the add-on
    directory is the installed set (D8) and a member of it that this host cannot
    run is invalid configuration, fixed by an operator installing a compatible
    version — never by a retry.
    """


#: ``addon_api.errors`` to ``platform_core.errors``, tried in order.
#:
#: Matched with ``isinstance`` rather than by exact type so that an add-on
#: narrowing a contract error into its own subclass keeps the classification it
#: asked for. Every entry's left-hand side is a direct subclass of ``AddonError``,
#: so no entry can shadow another; a future entry that is a subclass of one
#: already listed must be placed above it.
TRANSLATIONS: Final[tuple[tuple[type[AddonError], type[PlatformError]], ...]] = (
    (AddonTransient, PlatformTransientError),
    (AddonConfigInvalid, ConfigurationInvalidError),
    (AddonOutputInvalid, PlatformPermanentError),
    (AddonPermanent, PlatformPermanentError),
)

#: Anything else an add-on lets escape, including a bare ``AddonError``. Permanent,
#: because a failure nobody classified is not a failure anyone can say will clear.
UNEXPECTED_TRANSLATION: Final[type[PlatformError]] = PlatformPermanentError


def translate(error: Exception, manifest: AddonManifest) -> PlatformError:
    """Return the ``PlatformError`` that ``error`` from this add-on amounts to."""
    identity = f"{manifest.addon_id}@{manifest.addon_version}"
    for addon_type, platform_type in TRANSLATIONS:
        if isinstance(error, addon_type):
            return platform_type(
                f"{identity}: {error.summary}", _detail(manifest, addon_detail=error.detail)
            )
    return UNEXPECTED_TRANSLATION(
        # The type is in the summary and the message is not. An add-on's own
        # summary is written for an operator; an arbitrary exception's message is
        # not, and `ProtectedDetail` is where text of unknown provenance belongs.
        f"{identity} raised an unexpected {type(error).__name__}",
        _detail(
            manifest,
            exception_type=_qualified_name(error),
            exception_message=str(error),
        ),
    )


@contextmanager
def translated_failures(manifest: AddonManifest) -> Iterator[None]:
    """Run add-on code, and let nothing but a ``PlatformError`` out of it.

    A ``PlatformError`` passes through untouched. An add-on cannot raise one, so
    reaching here means the host's own capability layer raised it — already
    classified, and re-classifying it would discard the class the platform chose.

    ``BaseException`` is deliberately not caught. ``KeyboardInterrupt`` and
    ``SystemExit`` are the worker process being stopped rather than the add-on
    failing, and the P0-A interruption scenarios depend on them not being turned
    into ordinary attempt failures.
    """
    try:
        yield
    except PlatformError:
        raise
    except Exception as error:
        raise translate(error, manifest) from error


def _detail(
    manifest: AddonManifest,
    addon_detail: Mapping[str, Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Protected detail for a translated failure: who failed, and what they said.

    The add-on's own ``detail`` is nested under one key rather than merged, so an
    add-on cannot overwrite the identity fields the platform recorded.
    ``ProtectedDetail`` redacts the nested mapping on the way in, so an add-on
    reporting a field named like a credential is masked here as it would be
    anywhere else.
    """
    detail: dict[str, Any] = {
        "addon_id": manifest.addon_id,
        "addon_version": manifest.addon_version,
        "kind": manifest.kind,
    }
    detail.update(fields)
    if addon_detail:
        detail["addon_detail"] = dict(addon_detail)
    return detail


def _qualified_name(error: Exception) -> str:
    kind = type(error)
    if kind.__module__ == "builtins":
        return kind.__qualname__
    return f"{kind.__module__}.{kind.__qualname__}"
