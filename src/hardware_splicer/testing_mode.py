"""Temporary simulation flag — re-enable safety when HARDWARE_SPLICER_TESTING_MODE is unset."""

from __future__ import annotations

import os

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def testing_mode_enabled() -> bool:
    return os.environ.get("HARDWARE_SPLICER_TESTING_MODE", "").strip().lower() in _TRUTHY
