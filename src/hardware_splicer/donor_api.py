"""HTTP surface for take-apart plans of boards a person has described.

Stateless: nothing is stored, no project, revision or review is read or written, and the plan is rule-of-thumb advice that
approves nothing.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from .donor_capture import DonorCaptureError, build_donor_salvage_plan, capture_options

MAX_BODY_BYTES = 128 * 1024


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"type": "invalid_donor_capture", "message": message})


def create_donor_router() -> APIRouter:
    router = APIRouter(prefix="/v1/donors", tags=["donors"])

    @router.get("/options")
    def get_options() -> Dict[str, Any]:
        return {"ok": True, "options": capture_options()}

    @router.post("/salvage-plan")
    async def post_salvage_plan(request: Request) -> Dict[str, Any]:
        too_large = HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail={"type": "too_large", "message": f"the description may be at most {MAX_BODY_BYTES} bytes"})
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            raise too_large
        received = bytearray()
        async for chunk in request.stream():
            received.extend(chunk)
            if len(received) > MAX_BODY_BYTES:
                raise too_large
        try:
            body = json.loads(bytes(received).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise _unprocessable("the body is not JSON") from None
        except RecursionError:
            raise _unprocessable("the body is nested too deeply") from None
        try:
            plan = build_donor_salvage_plan(body)
        except DonorCaptureError as exc:
            raise _unprocessable(str(exc)) from None
        return {"ok": True, "plan": plan}

    return router
