"""Product API for runtime capability and project-use truth."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from .build_files import resolve_build_dir
from .capability_runtime import capability_report


def create_capability_router() -> APIRouter:
    router = APIRouter(prefix="/v1/capabilities", tags=["capabilities"])

    @router.get("")
    def capabilities(
        build_dir: str | None = Query(
            default=None,
            description=(
                "Optional Hardware Splicer build directory. When supplied, the report "
                "adds project-used and machine-tested evidence from real artifacts."
            ),
        ),
    ) -> Dict[str, Any]:
        try:
            resolved = resolve_build_dir(build_dir) if build_dir else None
            return capability_report(build_dir=resolved)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "invalid_capability_build_dir",
                        "message": str(exc),
                    }
                },
            ) from exc

    return router
