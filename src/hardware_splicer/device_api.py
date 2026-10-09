"""HTTP surface for whole-device assembly plans.

The plan is a proposal and a checklist. It is stateless: nothing is stored, no project, revision, pin or review is read or
written, and it approves nothing.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from .device_plan import DevicePlanError, build_device_plan, example_specs, module_library

MAX_BODY_BYTES = 64 * 1024


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"type": "invalid_device_spec", "message": message})


def create_device_router() -> APIRouter:
    router = APIRouter(prefix="/v1/devices", tags=["devices"])

    @router.get("/modules")
    def get_modules() -> Dict[str, Any]:
        return {"ok": True, "library": module_library()}

    @router.get("/examples")
    def get_examples() -> Dict[str, Any]:
        return {"ok": True, "examples": example_specs()}

    @router.get("/examples/{example_id}/plan")
    def get_example_plan(example_id: str) -> Dict[str, Any]:
        examples = example_specs()
        if example_id not in examples:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"type": "not_found", "message": "no such example"})
        return {"ok": True, "spec": examples[example_id], "plan": build_device_plan(examples[example_id])}

    @router.post("/plan")
    async def post_plan(request: Request) -> Dict[str, Any]:
        too_large = HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail={"type": "too_large", "message": f"the spec may be at most {MAX_BODY_BYTES} bytes"})
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
            raise too_large
        # Read the stream a piece at a time and stop as soon as it is too big, so a body with no declared length is never held whole.
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
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            plan = build_device_plan(spec)
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None
        return {"ok": True, "plan": plan}

    return router
