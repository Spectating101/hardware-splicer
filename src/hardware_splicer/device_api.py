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

from .device_plan import DevicePlanError, build_device_plan, device_catalog, device_spec_json_schema, example_specs, module_library
from .device_reclaim import DeviceReclaimError, match_reclaimed_parts
from .device_application import build_device_application
from .device_case import build_device_case
from .device_draft import draft_device_spec, draft_from_parts_text, parse_parts_text
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


def _spec_body(description: str) -> dict[str, Any]:
    """OpenAPI request body for the routes that take a device spec, so an agent reading the contract knows its shape."""

    return {"requestBody": {"required": True, "description": description, "content": {"application/json": {"schema": device_spec_json_schema()}}}}


def create_device_router() -> APIRouter:
    router = APIRouter(prefix="/v1/devices", tags=["devices"])
    body = _spec_body("A device spec, or {\"spec\": <device spec>}. Get the schema, module ids and pins from GET /v1/devices/spec-schema.")

    @router.get("/modules", summary="List the module library", description="Every module the planner knows, with its pins, roles, dimensions, sources and the figures the engineering review reads.")
    def get_modules() -> Dict[str, Any]:
        return {"ok": True, "library": module_library()}

    @router.get("/spec-schema", summary="JSON Schema and catalogue for writing a device spec", description="The schema a spec must satisfy (built from the library, so the module ids and ranges are the planner's), and a catalogue of each module's pins and roles. Use it to constrain or check a spec before planning.")
    def get_spec_schema() -> Dict[str, Any]:
        return {"ok": True, "schema": device_spec_json_schema(), "modules": device_catalog()}

    @router.get("/examples", summary="Example device specs", description="Complete specs that plan without errors; start from one.")
    def get_examples() -> Dict[str, Any]:
        return {"ok": True, "examples": example_specs()}

    @router.get("/examples/{example_id}/plan", summary="Plan an example", description="Returns a built-in example spec together with the plan the planner derives from it.")
    def get_example_plan(example_id: str) -> Dict[str, Any]:
        examples = example_specs()
        if example_id not in examples:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"type": "not_found", "message": "no such example"})
        return {"ok": True, "spec": examples[example_id], "plan": build_device_plan(examples[example_id])}

    @router.post("/draft", summary="Draft a wired spec from a controller and a list of parts", description="Takes {\"controller\": id, \"parts\": [id, ...]} with library ids, or {\"text\": a typed parts list}. The text form names modules from a small alias table and leaves unmatched lines unnamed; it does not guess. Wires each part to the controller's power, ground and default I2C pins. Returns the spec, what was assumed and the planner's findings for it. A draft is a starting point and approves nothing.")
    async def post_draft(request: Request) -> Dict[str, Any]:
        body = await _read_body(request, error_type="invalid_device_draft", label="draft request")
        try:
            if isinstance(body, dict) and "text" in body:
                return {"ok": True, **draft_from_parts_text(body)}
            return {"ok": True, **draft_device_spec(body)}
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None

    @router.post("/parts-reading", summary="Say how a typed parts list is read", description="Takes {\"text\": a typed parts list} and returns how each line was read: which library module it matched and on what basis, what matched nothing, and any part number left unread on a matched line. It reads and nothing else: no wiring, no plan, no approval. Unlike /draft it answers even when the list names no usable controller, which is when a person most needs to see why.")
    async def post_parts_reading(request: Request) -> Dict[str, Any]:
        body = await _read_body(request, error_type="invalid_device_draft", label="parts-reading request")
        try:
            if not isinstance(body, dict) or "text" not in body:
                raise DevicePlanError("text is required")
            return {"ok": True, "parsed": parse_parts_text(body["text"])}
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None

    @router.post("/plan", summary="Plan a device", description="Wiring checks, a case, assembly steps and a shopping list for a spec. Errors in `plan.findings` say what is wrong and, where there is an obvious way out, carry `suggestions` of candidate pins. A plan is a proposal and a checklist and approves nothing.", openapi_extra=body)
    async def post_plan(request: Request) -> Dict[str, Any]:
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            plan = build_device_plan(spec)
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None
        return {"ok": True, "plan": plan}

    @router.post("/reclaim-matches", summary="Match reclaimed part markings to the library", description="Advisory name matches only; a match is not proof of the part.")
    async def post_reclaim_matches(request: Request) -> Dict[str, Any]:
        body = await _read_body(request, error_type="invalid_reclaim_list", label="reclaim list")
        try:
            return {"ok": True, **match_reclaimed_parts(body)}
        except DeviceReclaimError as exc:
            raise HTTPException(status_code=422, detail={"type": "invalid_reclaim_list", "message": str(exc)}) from None

    @router.post("/firmware", summary="Compile-only diagnostic source for a device", description="A zip with an I2C diagnostic sketch for the planned wiring. ESP32-DevKitC V4 only. Compile-only: nothing is flashed.", openapi_extra=body)
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

    @router.post("/application", summary="Application source with host tests", description="A zip with an ESP32 sketch, its host fault scenarios and the part descriptor. Supported sensors: BME280, BH1750. Nothing is flashed.", openapi_extra=body)
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

    @router.post("/case", summary="Printable case files", description="A zip with STL and OpenSCAD files for the base and lid in print orientation. Not printed or test-fitted.", openapi_extra=body)
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

    @router.post("/engineering", summary="Engineering review of a plan", description="I2C loading, USB current, sealed-case temperature, antenna clearance, fit and printing, each figure sourced or assumed. Statuses are exceeds_limit, advisory, within_limit_under_assumptions and not_assessed; never a pass.", openapi_extra=body)
    async def post_engineering(request: Request) -> Dict[str, Any]:
        body = await _read_body(request, error_type="invalid_device_spec", label="spec")
        spec = body.get("spec") if isinstance(body, dict) and "spec" in body and "modules" not in body else body
        try:
            return {"ok": True, **build_engineering_review(spec)}
        except DevicePlanError as exc:
            raise _unprocessable(str(exc)) from None

    @router.post("/observations", summary="Compare bench serial output with a plan", description="Text you supply from a real board, checked against what the plan declares. It is a report, not proof.")
    async def post_observations(request: Request) -> Dict[str, Any]:
        """Compare a pasted diagnostic scan with the plan. Stateless; the text is operator-supplied."""

        body = await _read_body(request, error_type="invalid_device_observation", label="request")
        if not isinstance(body, dict) or "spec" not in body or "transcript" not in body:
            raise HTTPException(status_code=422, detail={"type": "invalid_device_observation", "message": "send {spec, transcript}"})
        try:
            return {"ok": True, "observation": check_device_observations(body["spec"], body["transcript"])}
        except DevicePlanError as exc:
            raise HTTPException(status_code=422, detail={"type": "invalid_device_observation", "message": str(exc)}) from None

    @router.post("/application/run", summary="Run the generated application off-hardware", description="Compiles and exercises the application against modelled buses. Server-enabled only. Not an emulator and not a physical result.", openapi_extra=_spec_body("{\"spec\": <device spec>} only."))
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
