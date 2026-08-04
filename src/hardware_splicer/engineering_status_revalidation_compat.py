"""Install fresh physical-authorization revalidation before status compilation."""

from __future__ import annotations

from typing import Any, Mapping

from . import engineering_status as _target
from .physical_authorization_revalidation import (
    revalidate_physical_authorization_state,
)


def install_physical_revalidation_compatibility() -> None:
    if getattr(_target, "_physical_revalidation_installed", False):
        return
    original = _target.build_engineering_status

    def build_engineering_status(plan: Mapping[str, Any]):
        revalidated = revalidate_physical_authorization_state(plan)
        report = original(revalidated)
        metadata = dict(report.metadata)
        revalidation = revalidated.get("physical_authorization_revalidation")
        metadata.update(
            {
                "physical_authorization_revalidated": bool(revalidation),
                "physical_authorization_revalidation": revalidation,
                "automatic_authorization": False,
            }
        )
        return report.model_copy(update={"metadata": metadata}, deep=True)

    _target.build_engineering_status = build_engineering_status
    _target._physical_revalidation_installed = True


install_physical_revalidation_compatibility()
