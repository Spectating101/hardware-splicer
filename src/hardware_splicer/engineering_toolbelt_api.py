"""REST surface for the engineering toolbelt: the same tools and envelope as the MCP server."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from . import engineering_toolbelt


def create_engineering_toolbelt_router() -> APIRouter:
    router = APIRouter(prefix="/v1/toolbelt", tags=["engineering-toolbelt"])

    @router.get("/tools")
    def list_tools() -> list[dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "input_schema": t.schema} for t in engineering_toolbelt.tool_specs()]

    @router.post("/{tool}")
    def call_tool(tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        if tool not in engineering_toolbelt.TOOLS:
            raise HTTPException(status_code=404, detail=f"unknown tool {tool}")
        try:
            return engineering_toolbelt.call(tool, arguments or {})
        except (FileNotFoundError, ValueError) as exc:  # bad project id
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router
