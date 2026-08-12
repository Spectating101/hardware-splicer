"""Canonical execution router with revision-anchored evidence persistence.

The existing execution router owns preview, run, capabilities, and in-memory evidence
attachment. This wrapper preserves those routes, removes only the legacy persistence
endpoint, and installs a persistence endpoint that applies execution evidence to the
stored project revision instead of a caller-supplied replacement plan.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import APIRouter, HTTPException, status

from .engineering_execution_api import (
    ExecutionEvidenceSaveRequest,
    create_engineering_execution_router as create_legacy_execution_router,
)
from .engineering_execution_plan_update import apply_execution_evidence_to_plan
from .engineering_plan_store import (
    resolve_engineering_project_id,
    save_engineering_plan,
)
from .project_store import (
    ProjectNotFound,
    ProjectStore,
    ProjectStoreError,
    RevisionConflict,
)


_SAVE_PATH = "/v1/engineering/execution/evidence/save"


def _engineering_plan_from_envelope(envelope: Mapping[str, Any]) -> Dict[str, Any]:
    snapshot = envelope.get("snapshot")
    if not isinstance(snapshot, Mapping):
        raise ValueError("stored project revision does not contain a snapshot")
    plan = snapshot.get("engineeringPlan")
    if not isinstance(plan, Mapping):
        raise ValueError("stored project revision does not contain an engineeringPlan")
    return dict(plan)


def _anchored_base_plan(
    project_store: ProjectStore,
    supplied_plan: Mapping[str, Any],
    *,
    project_id: str | None,
    expected_revision: int | None,
) -> tuple[Dict[str, Any], str, str]:
    if expected_revision is None:
        raise RevisionConflict(
            "expected_revision is required for execution evidence persistence"
        )
    resolved_project_id = resolve_engineering_project_id(
        supplied_plan,
        project_id=project_id,
    )
    supplied_identity = resolve_engineering_project_id(supplied_plan)
    if supplied_identity != resolved_project_id:
        raise ValueError(
            "supplied plan project identity does not match requested project_id"
        )

    try:
        latest = project_store.load_latest_with_recovery(resolved_project_id)
    except ProjectNotFound:
        if int(expected_revision) != 0:
            raise RevisionConflict(
                f"project {resolved_project_id!r} does not exist; expected_revision must be 0"
            )
        return dict(supplied_plan), resolved_project_id, "new_plan"

    latest_revision = int(latest["revision"])
    if int(expected_revision) != latest_revision:
        raise RevisionConflict(
            f"project {resolved_project_id!r} is at revision {latest_revision}, "
            f"expected {expected_revision}"
        )
    stored_plan = _engineering_plan_from_envelope(latest)
    if resolve_engineering_project_id(stored_plan) != resolved_project_id:
        raise ValueError("stored engineering plan identity is inconsistent")
    return stored_plan, resolved_project_id, "stored_revision"


def create_engineering_execution_router(
    project_store: ProjectStore | None = None,
) -> APIRouter:
    """Return the execution surface with exactly one revision-anchored save endpoint."""

    # APIRouter stores prefix-expanded route paths, and FastAPI/Starlette versions differ
    # in how an existing prefixed router behaves when routes are added or copied later.
    # Build a prefix-free canonical wrapper instead: retain every safe legacy route through
    # include_router(), omit only the legacy save route, then register the anchored endpoint
    # at its full path. This makes the public path invariant across router composition.
    legacy = create_legacy_execution_router(project_store)
    legacy.routes[:] = [
        route
        for route in legacy.routes
        if getattr(route, "path", None) != _SAVE_PATH
    ]
    router = APIRouter()
    router.include_router(legacy)

    @router.post(
        _SAVE_PATH,
        tags=["engineering", "execution"],
    )
    def ingest_and_save_evidence(
        request: ExecutionEvidenceSaveRequest,
    ) -> Dict[str, Any]:
        if project_store is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"type": "engineering_plan_store_unavailable"},
            )
        try:
            base_plan, resolved_project_id, base_source = _anchored_base_plan(
                project_store,
                request.plan,
                project_id=request.project_id,
                expected_revision=request.expected_revision,
            )
            plan = apply_execution_evidence_to_plan(
                base_plan,
                request.execution,
                target_ids=request.target_ids,
                requirement_ids=request.requirement_ids,
            )
            envelope = save_engineering_plan(
                project_store,
                plan,
                project_id=resolved_project_id,
                expected_revision=request.expected_revision,
            )
        except ProjectStoreError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "type": "engineering_plan_revision_conflict",
                    "message": str(exc),
                },
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "type": "invalid_execution_evidence",
                    "message": str(exc),
                },
            ) from exc
        return {
            "ok": True,
            "project_id": envelope["project_id"],
            "revision": envelope["revision"],
            "saved_at": envelope["saved_at"],
            "base_plan_source": base_source,
            "plan": plan,
            "engineering_status": plan.get("engineering_status"),
            "engineering_readiness": plan.get("engineering_readiness"),
            "physical_authority_unchanged": True,
            "automatic_execution": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    return router
