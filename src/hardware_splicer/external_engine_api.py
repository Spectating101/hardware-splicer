"""Discover and preview external specialist engines; deliberately NO execution endpoint."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException
from .external_engine_orchestration import (
    EnginePlanError, discover_engines, preview_engine_plan,
)


def create_external_engine_router() -> APIRouter:
    router = APIRouter(prefix="/v1/external-engines", tags=["engineering", "integration"])

    @router.get("")
    def engine_catalog() -> dict[str, Any]:
        registry = discover_engines()
        # Executable filesystem paths need not be disclosed to API callers.
        for row in registry["engines"]:
            row.pop("executable", None)
        return {"ok": True, **registry, "execution_via_http": False}

    @router.post("/preview")
    def preview(plan: dict[str, Any]) -> dict[str, Any]:
        try:
            if len(str(plan)) > 32_000:
                raise EnginePlanError("preview request exceeds size limit")
            return {"ok": True, "preview": preview_engine_plan(plan)}
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail={
                "type": "invalid_external_engine_plan", "message": str(exc)[:300],
            }) from exc

    return router
