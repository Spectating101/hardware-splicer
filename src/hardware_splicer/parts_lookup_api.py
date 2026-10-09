"""HTTP surface for looking a marking up and finding teardowns. Read-only; nothing is stored or approved."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status

from .part_lookup import PartLookupError, libraries_available, lookup_part
from .parts_intel import enrich_bom, parts_providers_from_env
from .teardown_search import TeardownSearchError, search_teardowns


def _unprocessable(kind: str, message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"type": kind, "message": message})


def create_parts_lookup_router() -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["lookup"])

    @router.get("/parts/lookup")
    def get_lookup(marking: str = Query(default="", max_length=200), online: bool = False) -> Dict[str, Any]:
        try:
            found = lookup_part(marking)
        except PartLookupError as exc:
            raise _unprocessable("invalid_marking", str(exc)) from None
        found["libraries_available"] = libraries_available()
        found["search_links"] = {}
        text = found["query"]
        if not found["matches"] and 3 <= len(text) <= 8 and text.isalnum():
            # A short code that no chip library knows is probably a top mark, which community databases decode. A link, never a claim.
            found["search_links"]["smd_code"] = f"https://www.s-manuals.com/smd/{text.lower()}"
        if online and text:
            records = enrich_bom([{"mpn": text}], parts_providers_from_env(), timeout_s=5.0, max_lookups=1)
            availability = records[0].get("availability", {}) if records else {}
            found["online"] = {"status": availability.get("status", "not_checked"), "records": availability.get("records", [])}
        return {"ok": True, **found}

    @router.get("/teardowns/search")
    def get_teardowns(q: str = Query(default="", max_length=200)) -> Dict[str, Any]:
        try:
            return {"ok": True, **search_teardowns(q)}
        except TeardownSearchError as exc:
            raise _unprocessable("invalid_search", str(exc)) from None

    return router
