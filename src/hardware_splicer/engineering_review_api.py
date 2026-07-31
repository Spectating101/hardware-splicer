"""Product routes for optional external engineering review adapters."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .integrations.engineering_review import (
    engineering_review_status,
    run_engineering_review,
)


class EngineeringReviewBuildRequest(BaseModel):
    build_dir: str


class EngineeringReviewRunRequest(EngineeringReviewBuildRequest):
    timeout_s: float = Field(default=180.0, ge=1.0, le=1800.0)
    force: bool = False


def _validation_error(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "error": {
                "code": "engineering_review_validation_error",
                "message": str(exc),
            }
        },
    )


def create_engineering_review_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/build-files/engineering-review",
        tags=["engineering-review"],
    )

    @router.post("/status")
    def status(request: EngineeringReviewBuildRequest) -> dict[str, Any]:
        try:
            return engineering_review_status(request.build_dir)
        except ValueError as exc:
            raise _validation_error(exc) from exc

    @router.post("/run")
    def run(request: EngineeringReviewRunRequest) -> dict[str, Any]:
        try:
            return run_engineering_review(
                request.build_dir,
                timeout_s=request.timeout_s,
                force=request.force,
            )
        except ValueError as exc:
            raise _validation_error(exc) from exc

    return router
