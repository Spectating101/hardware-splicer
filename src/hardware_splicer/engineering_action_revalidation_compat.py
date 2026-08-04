"""Ensure engineering action payloads use freshly revalidated physical state."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_action as _target
from .physical_authorization_revalidation import (
    revalidate_physical_authorization_state,
)


def install_action_revalidation_compatibility() -> None:
    if getattr(_target, "_physical_action_revalidation_installed", False):
        return
    original = _target._release_payload

    def _release_payload(plan: Mapping[str, Any]):
        return original(revalidate_physical_authorization_state(plan))

    _target._release_payload = _release_payload
    _target._physical_action_revalidation_installed = True


install_action_revalidation_compatibility()
