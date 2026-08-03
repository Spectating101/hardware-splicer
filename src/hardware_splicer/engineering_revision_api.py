"""Product API for canonical engineering revision comparison."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from .engineering_revision_diff import EngineeringRevisionDiff, diff_engineering_revisions
from .project_store import ProjectNotFound, ProjectStore, ProjectStoreError


class EngineeringRevisionDiffRequest(BaseModel):
    base_plan: Dict[str, Any] | None = None
    candidate_plan: Dict[str, Any] | None = None
    project_id: str | None = None
    base_revision: int | None = None
    candidate_revision: int | None = None


def _plan_from_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = envelope.get("snapshot") if isinstance(envelope.get("snapshot"), dict) else {}
    plan = snapshot.get("engineeringPlan")
    if not isinstance(plan, dict):
        raise ValueError("stored revision does not contain an engineeringPlan")
    return dict(plan)


def create_engineering_revision_router(project_store: ProjectStore | None = None) -> APIRouter:
    router = APIRouter(prefix="/v1/engineering/revisions", tags=["engineering", "revisions"])

    @router.get("/diff/schema")
    def revision_diff_schema() -> Dict[str, Any]:
        return {"ok": True, "schema": EngineeringRevisionDiff.model_json_schema()}

    @router.post("/diff")
    def revision_diff(request: EngineeringRevisionDiffRequest) -> Dict[str, Any]:
        try:
            if request.base_plan is not None and request.candidate_plan is not None:
                base_plan = request.base_plan
                candidate_plan = request.candidate_plan
                base_revision = request.base_revision
                candidate_revision = request.candidate_revision
            else:
                if project_store is None:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={"type": "engineering_plan_store_unavailable"},
                    )
                if not request.project_id:
                    raise ValueError("project_id is required when plans are not supplied")
                if request.candidate_revision is None:
                    candidate_envelope = project_store.load(request.project_id)
                    candidate_revision = int(candidate_envelope["revision"])
                else:
                    candidate_revision = request.candidate_revision
                    candidate_envelope = project_store.load(request.project_id, candidate_revision)
                base_revision = request.base_revision
                if base_revision is None:
                    base_revision = int(candidate_revision) - 1
                if int(base_revision) < 1:
                    raise ValueError("a prior base revision is required for stored diff")
                base_envelope = project_store.load(request.project_id, int(base_revision))
                base_plan = _plan_from_envelope(base_envelope)
                candidate_plan = _plan_from_envelope(candidate_envelope)
            report = diff_engineering_revisions(
                base_plan,
                candidate_plan,
                base_revision=base_revision,
                candidate_revision=candidate_revision,
            )
        except HTTPException:
            raise
        except ProjectNotFound as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"type": "engineering_revision_not_found", "message": str(exc)},
            ) from exc
        except ProjectStoreError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"type": "engineering_revision_store_error", "message": str(exc)},
            ) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "invalid_engineering_revision_diff", "message": str(exc)},
            ) from exc
        return {
            "ok": True,
            "project_id": report.project_id,
            "base_revision": report.base_revision,
            "candidate_revision": report.candidate_revision,
            "engineering_revision_diff": report.model_dump(mode="json"),
            "next_action": (
                report.candidate_status.next_actions[0].model_dump(mode="json")
                if report.candidate_status.next_actions
                else None
            ),
            "automatic_merge": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        }

    return router
