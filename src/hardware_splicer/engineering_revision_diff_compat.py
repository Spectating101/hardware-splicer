"""Compatibility correction for stale cached engineering status in revision diffs."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_revision_diff as _target
from .engineering_status import build_engineering_status


def install_revision_status_compatibility() -> None:
    if getattr(_target, "_canonical_status_rebuild_installed", False):
        return

    def _status(plan: Mapping[str, Any]):
        return build_engineering_status(plan)

    _target._status = _status
    _target._canonical_status_rebuild_installed = True


install_revision_status_compatibility()
