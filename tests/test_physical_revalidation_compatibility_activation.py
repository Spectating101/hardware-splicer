from __future__ import annotations

import hardware_splicer  # noqa: F401
from hardware_splicer import engineering_action, engineering_status


def test_status_and_action_revalidation_layers_are_active() -> None:
    assert getattr(
        engineering_status,
        "_physical_revalidation_installed",
        False,
    ) is True
    assert getattr(
        engineering_action,
        "_physical_action_revalidation_installed",
        False,
    ) is True
