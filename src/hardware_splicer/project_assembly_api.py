"""HTTP surface for the visual build sequence of one retained PCB revision.

The plan is a view of retained bytes. It carries no engineering authority and never rewrites a snapshot, revision, pin,
review or thread.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from .artifact_retention import read_pinned_artifact
from .assembly_plan import AssemblyPlanError, build_assembly_plan
from .project_api import _project_error
from .project_store import ProjectStore


def create_project_assembly_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["projects", "assembly"])

    @router.get("/{project_id}/revisions/{revision}/assembly-plan")
    def get_project_revision_assembly_plan(project_id: str, revision: int) -> Dict[str, Any]:
        try:
            store.load(project_id, revision=int(revision))
            artifact = read_pinned_artifact(store, project_id, int(revision), "pcb")
        except Exception as exc:
            raise _project_error(exc) from exc
        if artifact is None:
            return {"ok": True, "revision": int(revision), "available": False, "reason": "no retained pcb"}
        text, entry = artifact
        try:
            plan = build_assembly_plan(text, pcb_sha256=entry.get("sha256"))
        except AssemblyPlanError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"type": "assembly_plan_unreadable", "message": str(exc)},
            ) from exc
        return {"ok": True, "revision": int(revision), "available": True, "plan": plan}

    return router
