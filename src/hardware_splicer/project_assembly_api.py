"""HTTP surface for the visual build sequence of one retained PCB revision.

The plan is a view of retained bytes. It carries no engineering authority and never rewrites a snapshot, revision, pin,
review or thread.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from .artifact_retention import ArtifactIntegrityError, read_pinned_artifact
from .assembly_plan import AssemblyPlanError, build_assembly_plan
from .model3d import (
    BOARD_ONLY_GLB_FLAGS,
    Model3DError,
    Model3DUnavailable,
    capability_probe,
    load_or_build_cached_glb,
)
from .project_api import _project_error
from .project_store import ProjectStore


def _etag(digest: str) -> str:
    text = digest if digest.startswith("sha256:") else f"sha256:{digest}"
    return f'"{text}"'


def _not_found(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"type": "not_found", "message": message})


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

    @router.get("/{project_id}/revisions/{revision}/assembly-plan/board.glb")
    def get_project_revision_assembly_board(project_id: str, revision: int, request: Request) -> Response:
        """The bare board (copper, pads, silkscreen, mask) the build sequence draws its stand-in parts on."""

        try:
            store.load(project_id, revision=int(revision))
            artifact = read_pinned_artifact(store, project_id, int(revision), "pcb")
        except Exception as exc:
            raise _project_error(exc) from exc
        if artifact is None or not capability_probe().get("available"):
            raise _not_found("revision has no board model")
        text, entry = artifact
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise _project_error(ArtifactIntegrityError("artifact pin is corrupt"))
        try:
            built = load_or_build_cached_glb(store, project_id, text, digest.split(":", 1)[1], flags=BOARD_ONLY_GLB_FLAGS)
        except Model3DUnavailable:
            raise _not_found("revision has no board model") from None
        except Model3DError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"type": "model3d_error", "message": str(exc)},
            ) from exc
        etag = _etag(str(built["sha256"]))
        headers = {"ETag": etag, "Cache-Control": "private, max-age=3600"}
        if request.headers.get("if-none-match", "").strip().removeprefix("W/").strip() == etag:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)
        return Response(content=built["bytes"], media_type="model/gltf-binary", headers=headers)

    return router
