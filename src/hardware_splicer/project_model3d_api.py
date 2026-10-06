"""HTTP surface for GLB views of retained PCB revision bytes.

A rendered model is a view of retained bytes. It carries no engineering
authority and never rewrites a snapshot, revision, pin, review, or thread.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from .artifact_retention import ArtifactIntegrityError, read_pinned_artifact
from .model3d import (
    INSTALL_HINT,
    Model3DError,
    Model3DUnavailable,
    capability_probe,
    load_or_build_cached_glb,
)
from .project_api import _project_error
from .project_store import ProjectStore


def _model3d_error(exc: Exception) -> HTTPException:
    if isinstance(exc, Model3DError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"type": "model3d_error", "message": str(exc)},
        )
    return _project_error(exc)


def _etag(digest: str) -> str:
    text = digest if digest.startswith("sha256:") else f"sha256:{digest}"
    return f'"{text}"'


def _if_none_match_hits(header: str | None, etag: str) -> bool:
    if not header:
        return False
    wanted = {etag, etag.strip('"')}
    for part in header.split(","):
        token = part.strip()
        if token.startswith("W/"):
            token = token[2:].strip()
        if token in wanted or token.strip('"') in wanted:
            return True
    return False


def _pcb_artifact(store: ProjectStore, project_id: str, revision: int):
    store.load(project_id, revision=int(revision))
    return read_pinned_artifact(store, project_id, int(revision), "pcb")


def _model_payload(
    store: ProjectStore,
    project_id: str,
    revision: int,
    pcb_text: str,
    pcb_entry: dict[str, Any],
) -> dict[str, Any]:
    digest = pcb_entry.get("sha256")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise ArtifactIntegrityError("artifact pin is corrupt")
    pcb_hex = digest.split(":", 1)[1]
    built = load_or_build_cached_glb(store, project_id, pcb_text, pcb_hex)
    return {
        "format": "glb",
        "sha256": built["sha256"],
        "size_bytes": built["size_bytes"],
        "pcb_sha256": built["pcb_sha256"],
        "generated_with": built["generated_with"],
        "url": f"/v1/projects/{project_id}/revisions/{int(revision)}/model3d/glb",
        "bytes": built["bytes"],
    }


def create_project_model3d_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["projects", "model3d"])

    @router.get("/{project_id}/revisions/{revision}/model3d")
    def get_project_revision_model3d(project_id: str, revision: int) -> Dict[str, Any]:
        try:
            artifact = _pcb_artifact(store, project_id, revision)
        except Exception as exc:
            raise _model3d_error(exc) from exc
        if artifact is None:
            return {
                "ok": True,
                "revision": int(revision),
                "available": False,
                "reason": "no retained pcb",
            }
        probe = capability_probe()
        if not probe.get("available"):
            return {
                "ok": True,
                "revision": int(revision),
                "available": False,
                "reason": str(probe.get("reason") or INSTALL_HINT),
            }
        pcb_text, pcb_entry = artifact
        try:
            model = _model_payload(store, project_id, revision, pcb_text, pcb_entry)
        except Model3DUnavailable as exc:
            return {
                "ok": True,
                "revision": int(revision),
                "available": False,
                "reason": str(exc),
            }
        except Exception as exc:
            raise _model3d_error(exc) from exc
        model.pop("bytes", None)
        return {
            "ok": True,
            "revision": int(revision),
            "available": True,
            "model": model,
        }

    @router.get("/{project_id}/revisions/{revision}/model3d/glb")
    def get_project_revision_model3d_glb(
        project_id: str,
        revision: int,
        request: Request,
    ) -> Response:
        try:
            artifact = _pcb_artifact(store, project_id, revision)
        except Exception as exc:
            raise _model3d_error(exc) from exc
        if artifact is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"type": "not_found", "message": "revision has no 3D model"},
            )
        probe = capability_probe()
        if not probe.get("available"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"type": "not_found", "message": "revision has no 3D model"},
            )
        pcb_text, pcb_entry = artifact
        try:
            model = _model_payload(store, project_id, revision, pcb_text, pcb_entry)
        except Model3DUnavailable:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"type": "not_found", "message": "revision has no 3D model"},
            ) from None
        except Exception as exc:
            raise _model3d_error(exc) from exc
        etag = _etag(str(model["sha256"]))
        if _if_none_match_hits(request.headers.get("if-none-match"), etag):
            return Response(
                status_code=status.HTTP_304_NOT_MODIFIED,
                headers={
                    "ETag": etag,
                    "Cache-Control": "private, max-age=3600",
                },
            )
        return Response(
            content=model["bytes"],
            media_type="model/gltf-binary",
            headers={
                "ETag": etag,
                "Cache-Control": "private, max-age=3600",
            },
        )

    return router
