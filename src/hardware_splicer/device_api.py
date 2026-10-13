"""HTTP surface for whole-device assembly plans.

The plan is a proposal and a checklist. It is stateless: nothing is stored, no project, revision, pin or review is read or
written, and it approves nothing.
"""

from __future__ import annotations

import json
import os
import secrets
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, Response, status
from starlette.concurrency import run_in_threadpool

from .device_plan import DevicePlanError, build_device_plan, example_specs, module_library
from .device_reclaim import DeviceReclaimError, match_reclaimed_parts
from .device_application import build_device_application
from .device_case import build_device_case
from .device_engineering import build_engineering_review
from .device_firmware import build_device_firmware
from .device_observations import check_device_observations
from .device_application_runtime import DeviceRuntimeError, run_device_application

MAX_BODY_BYTES = 64 * 1024


def _unprocessable(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"type": "invalid_device_spec", "message": message})


async def _read_body(request: Request, *, error_type: str, label: str) -> Any:
    """Bound even a request with no declared length before parsing JSON."""

    def invalid(message: str) -> HTTPException:
        return HTTPException(status_code=422, detail={"type": error_type, "message": message})

    too_large = HTTPException(status_code=413, detail={"type": "too_large", "message": f"the {label} may be at most {MAX_BODY_BYTES} bytes"})
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        raise too_large
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > MAX_BODY_BYTES:
            raise too_large
    try:
        return json.loads(bytes(received).decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise invalid("the body is not JSON") from None
    except RecursionError:
        raise invalid("the body is nested too deeply") from None


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
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            plan = build_device_plan(spec)
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None
        return {"ok": True, "plan": plan}

    @router.post("/reclaim-matches")
    async def post_reclaim_matches(request: Request) -> Dict[str, Any]:
        body = await _read_body(request, error_type="invalid_reclaim_list", label="reclaim list")
        try:
            return {"ok": True, **match_reclaimed_parts(body)}
        except DeviceReclaimError as exc:
            raise HTTPException(status_code=422, detail={"type": "invalid_reclaim_list", "message": str(exc)}) from None

    @router.post("/firmware")
    async def post_firmware(request: Request) -> Response:
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            _metadata, archive = build_device_firmware(spec)
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None
        return Response(archive, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="device-diagnostic-proposal.zip"',
            "Cache-Control": "no-store",
        })

    @router.post("/application")
    async def post_application(request: Request) -> Response:
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            _metadata, archive = build_device_application(spec)
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None
        return Response(archive, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="device-application-proposal.zip"',
            "Cache-Control": "no-store",
        })

    @router.post("/case")
    async def post_case(request: Request) -> Response:
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            _metadata, archive = build_device_case(spec)
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None
        return Response(archive, media_type="application/zip", headers={
            "Content-Disposition": 'attachment; filename="device-case-proposal.zip"',
            "Cache-Control": "no-store",
        })

    @router.post("/engineering")
    async def post_engineering(request: Request) -> Dict[str, Any]:
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            return {"ok": True, **build_engineering_review(spec)}
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None

    @router.post("/observations")
    async def post_observations(request: Request) -> Dict[str, Any]:
        """Compare a pasted diagnostic scan with the plan. Stateless; the text is operator-supplied."""

        body = await _read_body(request, error_type="invalid_device_observation", label="request")
        if not isinstance(body, dict) or "spec" not in body or "transcript" not in body:
            raise HTTPException(status_code=422, detail={"type": "invalid_device_observation", "message": "send {spec, transcript}"})
        try:
            return {"ok": True, "observation": check_device_observations(body["spec"], body["transcript"])}
        except DevicePlanError as exc:
            raise HTTPException(status_code=422, detail={"type": "invalid_device_observation", "message": str(exc)}) from None

    @router.post("/application/run")
    async def post_application_run(request: Request) -> Dict[str, Any]:
        # This credential permits bounded software execution, never operator or physical authority.
        key = (os.environ.get("HARDWARE_SPLICER_API_KEY") or os.environ.get("CIRCUIT_AI_API_KEY", "")).strip()
        if key:
            if not secrets.compare_digest(request.headers.get("authorization", "").encode("utf-8"), f"Bearer {key}".encode("utf-8")):
                raise HTTPException(status_code=401, detail={"type": "unauthorized", "message": "Modeled execution requires the configured app API key."})
        elif request.client is None or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            raise HTTPException(status_code=403, detail={"type": "local_execution_only", "message": "Configure the app API key before allowing remote modeled execution."})
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        if not isinstance(body, dict) or set(body) != {"spec"}:
            raise _unprocessable("send only {spec}; code, tools, paths and authority flags are not accepted")
        try:
            result = await run_in_threadpool(run_device_application, body["spec"])
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None
        except DeviceRuntimeError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"type": "modeled_run_unavailable", "message": str(exc)}) from None
        return {"ok": True, "result": result}

    return router
