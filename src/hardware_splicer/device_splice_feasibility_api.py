"""Read-only device splice feasibility endpoint; does not execute hardware."""
from __future__ import annotations
import json
from typing import Any
from fastapi import APIRouter, HTTPException
from .device_splice_feasibility import assess_device_splice

def create_device_splice_feasibility_router() -> APIRouter:
    router = APIRouter(prefix="/v1/splice", tags=["splice", "engineering"])

    @router.post("/feasibility")
    def evaluate_device_splice(candidate: dict[str, Any]) -> dict[str, Any]:
        try:
            if len(json.dumps(candidate, allow_nan=False)) > 256_000:
                raise HTTPException(status_code=413, detail={"type": "candidate_too_large"})
            return {"ok": True, "assessment": assess_device_splice(candidate)}
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail={
                "type": "invalid_splice_candidate", "message": str(exc)[:350]
            }) from exc

    return router
