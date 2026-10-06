"""HTTP surface for parts intelligence on a retained schematic revision.

Reports the components and BOM groups a pinned schematic actually carries.
Provider enrichment is opt-in and never rewrites a snapshot, revision, or
authority field.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from .artifact_retention import ArtifactIntegrityError, read_pinned_artifact
from .kicad_diff import KicadDiffError
from .parts_intel import (
    PartsExtractError,
    build_bom,
    enrich_bom,
    extract_components,
    parts_providers_from_env,
)
from .project_api import _project_error
from .project_store import ProjectStore


def _parts_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (PartsExtractError, KicadDiffError)):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"type": "parts_extract_error", "message": str(exc)},
        )
    if isinstance(exc, ArtifactIntegrityError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"type": "artifact_integrity_error", "message": str(exc)},
        )
    return _project_error(exc)


def _source_from_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "relative": entry.get("relative"),
        "sha256": entry.get("sha256"),
        "retention_basis": entry.get("retention_basis"),
    }


def create_project_parts_router(store: ProjectStore) -> APIRouter:
    router = APIRouter(prefix="/v1/projects", tags=["projects", "parts"])

    @router.get("/{project_id}/revisions/{revision}/parts")
    async def load_project_revision_parts(
        project_id: str,
        revision: int,
        enrich: bool = Query(default=False),
    ) -> Dict[str, Any]:
        providers = parts_providers_from_env() if enrich else []
        provider_names = [str(getattr(provider, "name", "provider")) for provider in providers]
        enrichment: dict[str, Any] = {
            "requested": bool(enrich),
            "providers": provider_names,
            "performed": False,
        }
        try:
            store.load(project_id, revision=int(revision))
            pinned = read_pinned_artifact(store, project_id, int(revision), "schematic")
            if pinned is None:
                return {
                    "ok": True,
                    "project_id": project_id,
                    "revision": int(revision),
                    "available": False,
                    "reason": f"Revision {int(revision)} has no retained schematic artifact.",
                    "enrichment": enrichment,
                }
            text, entry = pinned
            components = extract_components(text)
            bom = build_bom(components)
            groups = list(bom["groups"])
            if enrich and providers:
                groups = await asyncio.to_thread(
                    enrich_bom,
                    groups,
                    providers,
                    timeout_s=5.0,
                )
                enrichment["performed"] = True
            elif enrich:
                enrichment["reason"] = "no providers enabled"
        except Exception as exc:
            raise _parts_error(exc) from exc
        return {
            "ok": True,
            "project_id": project_id,
            "revision": int(revision),
            "available": True,
            "source": _source_from_entry(entry),
            "summary": bom["summary"],
            "components": components,
            "bom_groups": groups,
            "enrichment": enrichment,
        }

    return router
