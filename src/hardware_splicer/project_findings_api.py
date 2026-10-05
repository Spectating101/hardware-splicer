"""Read-only HTTP projection of persisted finding provenance."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from .finding_provenance import project_findings_payload
from .project_api import _project_error
from .project_store import ProjectStore


def create_project_findings_router(project_store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["projects", "findings"])

    @router.get("/{project_id}/findings")
    def load_project_findings(
        project_id: str,
        revision: str | None = Query(default=None),
    ) -> Dict[str, Any]:
        try:
            selected_revision: int | None = None
            if revision is not None:
                try:
                    selected_revision = int(revision)
                except (TypeError, ValueError) as exc:
                    raise ValueError("revision must be an integer") from exc
                if selected_revision < 1:
                    raise ValueError("revision must be >= 1")
            envelope = (
                project_store.load(project_id, revision=selected_revision)
                if selected_revision is not None
                else project_store.load(project_id)
            )
        except Exception as exc:
            raise _project_error(exc) from exc

        snapshot = envelope.get("snapshot")
        if not isinstance(snapshot, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "type": "invalid_request",
                    "message": "project envelope is missing a snapshot object",
                },
            )
        loaded_revision = int(envelope["revision"])
        projected = project_findings_payload(snapshot, loaded_revision)
        return {
            "ok": True,
            "project_id": project_id,
            "revision": loaded_revision,
            "findings": projected["findings"],
            "unmatched_links": projected["unmatched_links"],
        }

    return router
