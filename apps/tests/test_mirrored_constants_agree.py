"""M-X4 (`docs/agent-workflow/reviews/REVIEW-M2-M7.md`): `HANDLER_PREFIX` and
`SOURCE_ID_FIELD` are each mirrored — not imported — across several modules, for the
same layer-direction reason `domain/api.py`'s own module docstring gives:
``domain`` may not import ``addon_host`` (DP-008 D1,
``tests/environment/test_p1_isolation.py``), and ``scheduler`` was brought under that
same guard in this fix wave (M-C3). A payload key or a job-handler prefix is a
contract between these modules, and every one of them spells it out rather than
importing a shared home that does not exist. `HANDLER_PREFIX` has three copies,
`SOURCE_ID_FIELD` four; before this test, nothing asserted any two of them stayed
equal — a drift would surface only as a job nothing can claim, not as a test failure.
"""

from __future__ import annotations

from addon_host.api import SOURCE_ID_FIELD as ADDON_HOST_API_SOURCE_ID_FIELD
from addon_host.capabilities import SOURCE_ID_FIELD as CAPABILITIES_SOURCE_ID_FIELD
from addon_host.registration import HANDLER_PREFIX as REGISTRATION_HANDLER_PREFIX
from domain.api import HANDLER_PREFIX as DOMAIN_API_HANDLER_PREFIX
from domain.api import SOURCE_ID_FIELD as DOMAIN_API_SOURCE_ID_FIELD
from scheduler.__main__ import HANDLER_PREFIX as SCHEDULER_HANDLER_PREFIX
from scheduler.__main__ import SOURCE_ID_FIELD as SCHEDULER_SOURCE_ID_FIELD


def test_every_handler_prefix_copy_agrees() -> None:
    copies = {
        "addon_host.registration.HANDLER_PREFIX": REGISTRATION_HANDLER_PREFIX,
        "domain.api.HANDLER_PREFIX": DOMAIN_API_HANDLER_PREFIX,
        "scheduler.__main__.HANDLER_PREFIX": SCHEDULER_HANDLER_PREFIX,
    }
    assert len(set(copies.values())) == 1, copies


def test_every_source_id_field_copy_agrees() -> None:
    copies = {
        "addon_host.api.SOURCE_ID_FIELD": ADDON_HOST_API_SOURCE_ID_FIELD,
        "addon_host.capabilities.SOURCE_ID_FIELD": CAPABILITIES_SOURCE_ID_FIELD,
        "domain.api.SOURCE_ID_FIELD": DOMAIN_API_SOURCE_ID_FIELD,
        "scheduler.__main__.SOURCE_ID_FIELD": SCHEDULER_SOURCE_ID_FIELD,
    }
    assert len(set(copies.values())) == 1, copies


def test_the_two_constants_are_actually_different_values() -> None:
    """The control: a bug that collapsed both constants to the same string in every
    module would pass the two assertions above for the wrong reason."""
    assert REGISTRATION_HANDLER_PREFIX != ADDON_HOST_API_SOURCE_ID_FIELD
