"""Product route for resolving external findings to canonical identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .electrical_design import ElectricalDesign
from .engineering_review_identity import (
    resolve_engineering_review,
    write_resolved_engineering_review,
)
from .integrations.engineering_review import read_latest_engineering_review
from .machine_project import MachineProject


class EngineeringReviewResolveRequest(BaseModel):
    build_dir: str
    electrical_design: Dict[str, Any]
    machine_project: Dict[str, Any] | None = None


def create_engineering_review_identity_router() -> APIRouter:
    router = APIRouter(
        prefix="/v1/build-files/engineering-review",
        tags=["engineering-review"],
    )

    @router.post("/resolve-identities")
    def resolve_identities(request: EngineeringReviewResolveRequest) -> Dict[str, Any]:
        try:
            review = read_latest_engineering_review(request.build_dir)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "engineering_review_identity_validation_error",
                        "message": str(exc),
                    }
                },
            ) from exc
        if review is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "engineering_review_missing",
                        "message": "Run engineering review before resolving findings to project identity.",
                    }
                },
            )

        try:
            electrical = ElectricalDesign.model_validate(request.electrical_design)
            machine = (
                MachineProject.model_validate(request.machine_project)
                if request.machine_project is not None
                else None
            )
            resolved = resolve_engineering_review(review, electrical, machine)
            source_bytes = json.dumps(
                review,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            resolved["source_review"]["sha256"] = hashlib.sha256(source_bytes).hexdigest()
            path = write_resolved_engineering_review(request.build_dir, resolved)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "engineering_review_identity_error",
                        "message": str(exc),
                    }
                },
            ) from exc

        return {
            "ok": True,
            "schema_version": "hardware_splicer.engineering_review_identity_api.v1",
            "artifact": str(path),
            "identity_resolution": resolved["identity_resolution"],
            "review": resolved,
        }

    return router
