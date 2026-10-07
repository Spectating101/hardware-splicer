"""HTTP surface for retained KiCad revision artifacts and redlines.

Retention and diff report evidence only. They never rewrite a snapshot, revision,
or authority field.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, Response, status

from .artifact_retention import (
    ARTIFACT_KINDS,
    ArtifactIntegrityError,
    ArtifactPinConflict,
    load_artifact_pin,
    read_pinned_artifact,
    retain_revision_artifacts,
)
from .kicad_diff import KicadDiffError, diff_kicad_text
from .project_api import _project_error
from .project_store import ProjectNotFound, ProjectStore


def _artifact_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ArtifactPinConflict):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"type": "artifact_pin_conflict", "message": str(exc)},
        )
    if isinstance(exc, ArtifactIntegrityError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "artifact_integrity_error", "message": str(exc)},
        )
    if isinstance(exc, KicadDiffError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "artifact_diff_error", "message": str(exc)},
        )
    return _project_error(exc)


def _parse_revision_query(raw: str, *, label: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if value < 1:
        raise ValueError(f"{label} must be >= 1")
    return value


def _side_meta_from_entry(entry: Any) -> dict[str, Any] | None:
    if not isinstance(entry, dict):
        return None
    return {
        "relative": entry.get("relative"),
        "sha256": entry.get("sha256"),
        "retention_basis": entry.get("retention_basis"),
    }


def create_project_artifact_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["projects", "artifacts"])

    @router.post("/{project_id}/revisions/{revision}/artifacts/retain")
    def retain_project_revision_artifacts(project_id: str, revision: int) -> Dict[str, Any]:
        try:
            store.load(project_id, revision=int(revision))
            pin = retain_revision_artifacts(
                store,
                project_id,
                int(revision),
                basis="after_save",
            )
        except Exception as exc:
            raise _artifact_error(exc) from exc
        if pin is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "type": "not_found",
                    "message": "revision has no usable build directory",
                },
            )
        return {
            "ok": True,
            "pin": pin,
            "retention_basis": "after_save",
            "note": (
                "after_save captures current build-dir bytes, which may differ "
                "from the bytes at save time because build directories are mutable."
            ),
        }

    @router.get("/{project_id}/revisions/{revision}/artifacts")
    def load_project_revision_artifacts(project_id: str, revision: int) -> Dict[str, Any]:
        try:
            store.load(project_id, revision=int(revision))
            pin = load_artifact_pin(store, project_id, revision)
        except Exception as exc:
            raise _artifact_error(exc) from exc
        return {"ok": True, "revision": int(revision), "pin": pin}

    @router.get("/{project_id}/revisions/{revision}/artifacts/{kind}/file")
    def load_project_revision_artifact_file(project_id: str, revision: int, kind: str) -> Response:
        """The retained KiCad file of a revision, as text, verified against its recorded hash.

        This is what the revision kept, not what the build folder holds now, so two revisions can be compared exactly.
        """

        try:
            if kind not in ARTIFACT_KINDS:
                raise ValueError("kind must be schematic or pcb")
            store.load(project_id, revision=int(revision))
            pinned = read_pinned_artifact(store, project_id, int(revision), kind)
        except Exception as exc:
            raise _artifact_error(exc) from exc
        if pinned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"type": "artifact_not_retained", "message": f"Revision {int(revision)} has no retained {kind}."},
            )
        text, entry = pinned
        digest = str(entry.get("sha256") or "")
        return Response(
            content=text.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"ETag": f'"{digest}"', "Cache-Control": "private, max-age=31536000, immutable"},
        )

    @router.get("/{project_id}/artifact-diff")
    def diff_project_revision_artifacts(
        project_id: str,
        base: str = Query(...),
        candidate: str = Query(...),
        kind: str = Query(...),
    ) -> Dict[str, Any]:
        try:
            base_revision = _parse_revision_query(base, label="base")
            candidate_revision = _parse_revision_query(candidate, label="candidate")
            if kind not in ARTIFACT_KINDS:
                raise ValueError("kind must be schematic or pcb")
            store.load(project_id, revision=base_revision)
            store.load(project_id, revision=candidate_revision)
            base_art = read_pinned_artifact(store, project_id, base_revision, kind)
            cand_art = read_pinned_artifact(store, project_id, candidate_revision, kind)
            missing_revision = None
            if base_art is None:
                missing_revision = base_revision
            elif cand_art is None:
                missing_revision = candidate_revision
            if missing_revision is not None:
                return {
                    "ok": True,
                    "project_id": project_id,
                    "available": False,
                    "reason": f"Revision {missing_revision} has no retained {kind} artifact.",
                }
            base_text, base_entry = base_art
            cand_text, cand_entry = cand_art
            report = diff_kicad_text(kind, base_text, cand_text)
        except Exception as exc:
            raise _artifact_error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "base_revision": base_revision,
            "candidate_revision": candidate_revision,
            "kind": kind,
            "available": True,
            "artifact": {
                "base": _side_meta_from_entry(base_entry),
                "candidate": _side_meta_from_entry(cand_entry),
            },
            "diff": report,
        }

    return router
