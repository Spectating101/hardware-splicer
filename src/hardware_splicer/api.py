from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
import re
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .compose_dispatch import compose_dispatch
from .build_files import list_kicad_files, read_build_file, read_design_quality_summary, resolve_build_dir
from .build_compiler import CATALOG_BUILD_IDS, compile_catalog_build, resolve_build_id
from .circuit_synthesis import (
    compile_synthesis_candidate,
    plan_analog_conditioning,
    plan_battery_power,
    plan_circuit,
    plan_h_bridge,
    plan_level_shift,
    plan_motor_driver,
    plan_power_rail,
    plan_relay_switch,
    plan_sensor_interface,
    topology_library_card,
)
from .compiler import _resolve_board_design_files, compile_hardware_bundle
from .design_quality import build_design_quality_gate
from .material_modes import resolve_material_mode
from .jobs import JobBackend, artifact_manifest, build_output_archive
from .mechatronics_authority import build_mechatronics_authority
from .mechanical_authority import build_mechanical_authority
from .project_intake import plan_project_from_intake, run_project_intake, splice_and_build_from_intake
from .splice_bench import bench_status, submit_bench_measurements
from .robotics_actuation import build_robotics_actuation_packet
from .robotics_platform_authority import build_robotics_platform_authority
from .robotics_simulation import build_robotics_simulation_packet
from .runtime import ServiceStartError, runtime_status
from .scenario_runner import run_hardware_scenario, scenario_to_compile_spec
from .schemas import HardwareCompileSpec
from .validation import raise_for_validation_errors, validate_compile_spec, validation_errors


class CompileRequest(BaseModel):
    spec: Dict[str, Any]
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    start_splicer: bool = True
    splicer_port: int = 0


class ValidateRequest(BaseModel):
    spec: Dict[str, Any]


class ScenarioRunRequest(BaseModel):
    scenario: Dict[str, Any]
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    start_splicer: bool = True
    splicer_port: int = 0


class IntakeRunRequest(BaseModel):
    intake: Dict[str, Any]
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    start_splicer: bool = True
    splicer_port: int = 0


class CompileBuildRequest(BaseModel):
    build_id: str | None = None
    archetype: str | None = None
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    export_gerber: bool = True


class SpliceAndBuildRequest(BaseModel):
    intake: Dict[str, Any]
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    export_gerber: bool = True


class SpliceBenchStatusRequest(BaseModel):
    build_dir: str


class SpliceBenchSubmitRequest(BaseModel):
    build_dir: str
    measurements: list[Dict[str, Any]] = Field(default_factory=list)


class VisionEnrichRequest(BaseModel):
    intake: Dict[str, Any]
    apply: bool | None = None
    live: bool | None = None


class DonorBoardVisionRequest(BaseModel):
    intake: Dict[str, Any]


class SpliceBenchCaptureRequest(BaseModel):
    build_dir: str
    capture: Dict[str, Any]


class SpliceBenchTemplateRequest(BaseModel):
    build_dir: str


class BuildFilesListRequest(BaseModel):
    build_dir: str


class BuildFilesContentRequest(BaseModel):
    build_dir: str
    relative: str


class SpliceGoldenLoopRequest(BaseModel):
    intake: Dict[str, Any]
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    export_gerber: bool = False
    simulate_bench: bool = True


class ComposeRequest(BaseModel):
    phrase: str | None = None
    module_ids: list[str] | None = None
    netlist: Dict[str, Any] | None = None
    canvas_nodes: list[Dict[str, Any]] | None = None
    canvas_wires: list[Dict[str, Any]] | None = None
    constraints: Dict[str, Any] | None = None
    material_mode: str | None = Field(default=None, description="scratch | salvage (auto if omitted)")
    strategy_mode: str | None = Field(default=None, description="open | constrained")
    salvage_mode: bool = False
    allowed_purchases: list[str] | None = None
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    export_gerber: bool = True
    wire_only: bool = Field(
        default=False,
        description="Return wired graph only (skip KiCad compile). For editor auto-wire.",
    )


class ComposeCanvasRequest(BaseModel):
    nodes: list[Dict[str, Any]]
    wires: list[Dict[str, Any]] | None = None
    constraints: Dict[str, Any] | None = None
    material_mode: str | None = None
    strategy_mode: str | None = None
    salvage_mode: bool = False
    allowed_purchases: list[str] | None = None
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    export_gerber: bool = True
    wire_only: bool = False


class NetlistCompileRequest(BaseModel):
    netlist: Dict[str, Any] | None = None
    circuit_json: list[Dict[str, Any]] | None = None
    kicad_netlist_text: str | None = None
    build_id: str = "generic_low_voltage_build"
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    export_gerber: bool = True


class ComposeJobRequest(ComposeRequest):
    pass


class SpliceBuildJobRequest(SpliceAndBuildRequest):
    pass


class EngineVerifyRequest(BaseModel):
    build_ids: list[str] | None = None
    max_kicad_drc_warnings: int = 500


class MechanicalAuthorityRequest(BaseModel):
    spec: Dict[str, Any]
    engineering: Dict[str, Any] | None = None


class RoboticsActuationRequest(BaseModel):
    spec: Dict[str, Any]
    engineering: Dict[str, Any] | None = None


class MechatronicsAuthorityRequest(BaseModel):
    spec: Dict[str, Any]
    engineering: Dict[str, Any] | None = None
    mechanical_authority: Dict[str, Any] | None = None
    robotics_actuation: Dict[str, Any] | None = None


class RoboticsPlatformAuthorityRequest(BaseModel):
    spec: Dict[str, Any]
    engineering: Dict[str, Any] | None = None
    mechanical_authority: Dict[str, Any] | None = None
    robotics_actuation: Dict[str, Any] | None = None
    mechatronics_authority: Dict[str, Any] | None = None
    robotics_simulation: Dict[str, Any] | None = None


class RoboticsSimulationRequest(BaseModel):
    spec: Dict[str, Any]
    engineering: Dict[str, Any] | None = None
    robotics_actuation: Dict[str, Any] | None = None
    mechatronics_authority: Dict[str, Any] | None = None


class CircuitMotorDriverPlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitPowerRailPlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitLevelShiftPlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitSensorInterfacePlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitHBridgePlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitRelaySwitchPlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitAnalogConditioningPlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitBatteryPowerPlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitSynthesisPlanRequest(BaseModel):
    intent: Dict[str, Any]


class CircuitSynthesisCompileRequest(BaseModel):
    intent: Dict[str, Any]
    out_dir: str | None = Field(default=None)
    request_id: str | None = None
    export_gerber: bool = False


class IntentClarifyRequest(BaseModel):
    intent: Dict[str, Any]


class ProjectPackageRequest(BaseModel):
    build_dir: str
    source: str = "api"


def _compose_constraints(request: ComposeRequest | ComposeCanvasRequest) -> Dict[str, Any]:
    body = dict(getattr(request, "constraints", None) or {})
    if getattr(request, "strategy_mode", None):
        body["strategy_mode"] = request.strategy_mode
    if getattr(request, "allowed_purchases", None):
        body["allowed_purchases"] = list(request.allowed_purchases or [])
    if isinstance(request, ComposeCanvasRequest) or getattr(request, "canvas_nodes", None):
        body.setdefault("graph_mode", "canvas")
    else:
        body.setdefault("graph_mode", "scratch")
    return body


def _netlist_from_request(request: NetlistCompileRequest):
    from .netlist.import_kicad import parse_kicad_netlist
    from .netlist.ingest import load_netlist_payload

    if request.kicad_netlist_text:
        return parse_kicad_netlist(request.kicad_netlist_text)
    if request.circuit_json is not None:
        return load_netlist_payload({"documents": request.circuit_json}, netlist_format="circuit_json")
    if request.netlist is not None:
        return load_netlist_payload(request.netlist, netlist_format="ir_json")
    raise ValueError("netlist, circuit_json, or kicad_netlist_text is required")


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-._")
    return slug[:80] or "hardware-splicer-build"


def _api_output_root() -> Path:
    return Path(os.getenv("HARDWARE_SPLICER_OUTPUT_ROOT", "/tmp/hardware_splicer_api")).resolve()


def _allow_arbitrary_out_dir() -> bool:
    return os.getenv("HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR", "").lower() in {"1", "true", "yes"}


def _request_id(value: str | None) -> str:
    if value is None or not value.strip():
        return uuid.uuid4().hex
    request_id = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", request_id):
        raise ValueError("request_id must contain only letters, numbers, dot, underscore, or dash and be at most 96 characters")
    return request_id


def _attach_inline_graph(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Include build_graph.json inline for editor clients (gate 1.5)."""
    graph_path = payload.get("build_graph_file")
    if not graph_path:
        paths = payload.get("paths") or {}
        if isinstance(paths, dict):
            graph_path = paths.get("build_graph")
    if not graph_path or payload.get("graph"):
        return payload
    path = Path(str(graph_path))
    if not path.is_file():
        return payload
    try:
        body = dict(payload)
        body["graph"] = json.loads(path.read_text(encoding="utf-8"))
        return body
    except (OSError, json.JSONDecodeError):
        return payload


def _resolve_api_out_dir(request: CompileRequest, spec: HardwareCompileSpec, request_id: str) -> Path:
    root = _api_output_root()
    root.mkdir(parents=True, exist_ok=True)
    if request.out_dir:
        target = Path(request.out_dir)
        if not target.is_absolute():
            target = root / target
    else:
        target = root / _slug(spec.project_name) / request_id
    resolved = target.resolve()
    if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
        raise ValueError(
            f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
            "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
        )
    return resolved


def _error(status_code: int, error_type: str, message: str, *, request_id: str | None = None) -> HTTPException:
    payload: Dict[str, Any] = {"type": error_type, "message": message}
    if request_id:
        payload["request_id"] = request_id
    return HTTPException(status_code=status_code, detail={"error": payload})


def create_app() -> FastAPI:
    job_backend = JobBackend.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            job_backend.stop()

    from ._version import __version__

    app = FastAPI(
        title="Hardware-Splicer Splice Agent",
        version=__version__,
        description="Splice agent API: donor intake → KiCad carrier → bench gates → project package.",
        lifespan=lifespan,
    )
    app.state.job_backend = job_backend

    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5178",
            "http://localhost:5178",
            "http://127.0.0.1:5177",
            "http://localhost:5177",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> Dict[str, Any]:
        from ._version import __version__

        status = runtime_status()
        return {
            "ok": bool(status.get("ok")),
            "version": __version__,
            "app_roots": status.get("app_roots"),
        }

    @app.get("/v1/examples/splice-intakes")
    def splice_intake_examples() -> Dict[str, Any]:
        root = Path(__file__).resolve().parents[2] / "examples" / "intakes"
        examples: List[Dict[str, Any]] = []
        for path in sorted(root.glob("splice_*.json")):
            try:
                intake = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(intake, dict):
                continue
            examples.append(
                {
                    "id": path.stem,
                    "label": str(intake.get("project_name") or path.stem),
                    "goal": str(intake.get("goal") or ""),
                    "intake": intake,
                }
            )
        return {"ok": True, "examples": examples}

    @app.get("/v1/examples/donor-fixtures")
    def donor_fixture_examples() -> Dict[str, Any]:
        root = Path(__file__).resolve().parents[2] / "examples" / "fixtures"
        fixtures: List[Dict[str, Any]] = []
        for path in sorted(root.glob("splice_donor_*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            blocks = payload.get("reusable_blocks") or []
            headline = ""
            if blocks and isinstance(blocks[0], dict):
                headline = str(blocks[0].get("name") or blocks[0].get("block_id") or "")
            fixtures.append(
                {
                    "id": path.stem,
                    "board_id": str(payload.get("board_id") or path.stem),
                    "label": str(payload.get("board_role") or payload.get("board_id") or path.stem).replace("_", " "),
                    "headline": headline,
                    "verdict": str(payload.get("verdict") or ""),
                    "intake_path": f"@examples/fixtures/{path.name}",
                    "suggested_uses": list(blocks[0].get("suggested_uses") or [])[:4]
                    if blocks and isinstance(blocks[0], dict)
                    else [],
                }
            )
        return {"ok": True, "fixtures": fixtures}

    @app.get("/v1/examples/netlist-fixtures")
    def netlist_fixture_catalog() -> Dict[str, Any]:
        manifest = Path(__file__).resolve().parents[2] / "examples" / "netlist_fixtures" / "manifest.json"
        if not manifest.is_file():
            return {"ok": True, "fixtures": []}
        data = json.loads(manifest.read_text(encoding="utf-8"))
        fixtures = [
            {
                "id": row.get("id"),
                "type": row.get("type"),
                "description": row.get("description"),
                "module_ids": list(row.get("module_ids") or []),
            }
            for row in data.get("fixtures") or []
            if isinstance(row, dict) and row.get("id")
        ]
        return {"ok": True, "fixtures": fixtures}

    @app.get("/v1/examples/netlist-fixtures/{fixture_id}")
    def netlist_fixture_payload(fixture_id: str) -> Dict[str, Any]:
        from .integrations.circuit_json_adapter import netlist_to_circuit_json
        from .netlist.ir import CircuitNetlist

        manifest = Path(__file__).resolve().parents[2] / "examples" / "netlist_fixtures" / "manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        row = next((f for f in data.get("fixtures") or [] if f.get("id") == fixture_id), None)
        if not row:
            raise _error(404, "fixture_not_found", f"Unknown netlist fixture: {fixture_id}")
        rel = str(row.get("path") or "")
        path = Path(__file__).resolve().parents[2] / "examples" / "netlist_fixtures" / rel
        if not path.is_file():
            raise _error(404, "fixture_file_missing", f"Fixture file missing: {rel}")
        if row.get("type") == "kicad_netlist":
            from .netlist.import_kicad import parse_kicad_netlist

            netlist = parse_kicad_netlist(path.read_text(encoding="utf-8"))
        else:
            netlist = CircuitNetlist.from_dict(json.loads(path.read_text(encoding="utf-8")))
        circuit_json = netlist_to_circuit_json(netlist, source_build_id=fixture_id)
        return {
            "ok": True,
            "fixture_id": fixture_id,
            "description": row.get("description"),
            "module_ids": list(row.get("module_ids") or []),
            "netlist": netlist.to_dict(),
            "circuit_json": circuit_json,
        }

    @app.post("/v1/build-files/list")
    def build_files_list(request: BuildFilesListRequest) -> Dict[str, Any]:
        try:
            files = list_kicad_files(request.build_dir)
            return {"ok": True, "build_dir": str(resolve_build_dir(request.build_dir)), "files": files}
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/build-files/content")
    def build_files_content(request: BuildFilesContentRequest) -> Dict[str, Any]:
        try:
            payload = read_build_file(request.build_dir, request.relative)
            return {"ok": True, **payload}
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/build-files/design-quality")
    def build_files_design_quality(request: BuildFilesListRequest) -> Dict[str, Any]:
        try:
            return read_design_quality_summary(request.build_dir)
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.get("/v1/status")
    def status() -> Dict[str, Any]:
        return {**runtime_status(), "jobs": job_backend.store.stats()}

    @app.post("/v1/validate")
    def validate_spec(request: ValidateRequest) -> Dict[str, Any]:
        try:
            spec = HardwareCompileSpec.from_dict(request.spec)
            resolved = replace(spec, board_design_files=_resolve_board_design_files(spec.board_design_files))
            issues = validate_compile_spec(resolved)
            errors = validation_errors(issues)
            return {"ok": not errors, "issue_count": len(issues), "issues": issues}
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/mechanical-authority")
    def mechanical_authority(request: MechanicalAuthorityRequest) -> Dict[str, Any]:
        try:
            spec = HardwareCompileSpec.from_dict(request.spec)
            return build_mechanical_authority(spec.to_dict(), engineering=request.engineering or {})
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/robotics-actuation")
    def robotics_actuation(request: RoboticsActuationRequest) -> Dict[str, Any]:
        try:
            spec = HardwareCompileSpec.from_dict(request.spec)
            return build_robotics_actuation_packet(spec.to_dict(), engineering=request.engineering or {})
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/robotics-simulation")
    def robotics_simulation(request: RoboticsSimulationRequest) -> Dict[str, Any]:
        try:
            spec = HardwareCompileSpec.from_dict(request.spec)
            return build_robotics_simulation_packet(
                spec.to_dict(),
                engineering=request.engineering or {},
                robotics_actuation=request.robotics_actuation,
                mechatronics_authority=request.mechatronics_authority,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/mechatronics-authority")
    def mechatronics_authority(request: MechatronicsAuthorityRequest) -> Dict[str, Any]:
        try:
            spec = HardwareCompileSpec.from_dict(request.spec)
            return build_mechatronics_authority(
                spec.to_dict(),
                engineering=request.engineering or {},
                mechanical_authority=request.mechanical_authority,
                robotics_actuation=request.robotics_actuation,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/robotics-platform-authority")
    def robotics_platform_authority(request: RoboticsPlatformAuthorityRequest) -> Dict[str, Any]:
        try:
            spec = HardwareCompileSpec.from_dict(request.spec)
            return build_robotics_platform_authority(
                spec.to_dict(),
                engineering=request.engineering or {},
                mechanical_authority=request.mechanical_authority,
                robotics_actuation=request.robotics_actuation,
                mechatronics_authority=request.mechatronics_authority,
                robotics_simulation=request.robotics_simulation,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/motor-driver")
    def circuit_synthesis_motor_driver(request: CircuitMotorDriverPlanRequest) -> Dict[str, Any]:
        try:
            return plan_motor_driver(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/power-rail")
    def circuit_synthesis_power_rail(request: CircuitPowerRailPlanRequest) -> Dict[str, Any]:
        try:
            return plan_power_rail(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/level-shift")
    def circuit_synthesis_level_shift(request: CircuitLevelShiftPlanRequest) -> Dict[str, Any]:
        try:
            return plan_level_shift(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/sensor-interface")
    def circuit_synthesis_sensor_interface(request: CircuitSensorInterfacePlanRequest) -> Dict[str, Any]:
        try:
            return plan_sensor_interface(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/h-bridge")
    def circuit_synthesis_h_bridge(request: CircuitHBridgePlanRequest) -> Dict[str, Any]:
        try:
            return plan_h_bridge(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/relay-switch")
    def circuit_synthesis_relay_switch(request: CircuitRelaySwitchPlanRequest) -> Dict[str, Any]:
        try:
            return plan_relay_switch(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/analog-conditioning")
    def circuit_synthesis_analog_conditioning(request: CircuitAnalogConditioningPlanRequest) -> Dict[str, Any]:
        try:
            return plan_analog_conditioning(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/circuit-synthesis/battery-power")
    def circuit_synthesis_battery_power(request: CircuitBatteryPowerPlanRequest) -> Dict[str, Any]:
        try:
            return plan_battery_power(request.intent).to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.get("/v1/circuit-synthesis/capability")
    def circuit_synthesis_capability() -> Dict[str, Any]:
        return topology_library_card()

    @app.post("/v1/circuit-synthesis/plan")
    def circuit_synthesis_plan(request: CircuitSynthesisPlanRequest) -> Dict[str, Any]:
        try:
            from .sdk import plan_circuit_synthesis

            return plan_circuit_synthesis(request.intent)
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc

    @app.post("/v1/intent/clarify")
    def intent_clarify(request: IntentClarifyRequest) -> Dict[str, Any]:
        from .sdk import clarify_hardware_intent

        return clarify_hardware_intent(request.intent)

    @app.post("/v1/project-package/render")
    def project_package_render(request: ProjectPackageRequest) -> Dict[str, Any]:
        from .sdk import render_project_package

        return render_project_package(request.build_dir, source=request.source)

    @app.post("/v1/circuit-synthesis/compile")
    def circuit_synthesis_compile(request: CircuitSynthesisCompileRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            request_id = _request_id(request.request_id)
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                target = root / "circuit-synthesis" / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )
            candidate = plan_circuit(request.intent)
            return compile_synthesis_candidate(
                candidate,
                out_dir=resolved,
                export_gerber=bool(request.export_gerber),
                request_id=request_id,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/compile")
    def compile_bundle(request: CompileRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            request_id = _request_id(request.request_id)
            spec = HardwareCompileSpec.from_dict(request.spec)
            out_dir = _resolve_api_out_dir(request, spec, request_id)
            result = compile_hardware_bundle(
                spec,
                out_dir=out_dir,
                start_splicer=bool(request.start_splicer),
                splicer_port=int(request.splicer_port or 0),
                request_id=request_id,
            )
            return result.to_dict()
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except (TimeoutError, ConnectionError, ServiceStartError) as exc:
            raise _error(503, "dependency_unavailable", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "compile_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/scenario-run")
    def scenario_run(request: ScenarioRunRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            request_id = _request_id(request.request_id)
            scenario = dict(request.scenario)
            spec = scenario_to_compile_spec(scenario)
            out_dir = _resolve_api_out_dir(request, spec, request_id)
            return run_hardware_scenario(
                scenario,
                out_dir=out_dir,
                start_splicer=bool(request.start_splicer),
                splicer_port=int(request.splicer_port or 0),
                request_id=request_id,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except (TimeoutError, ConnectionError, ServiceStartError) as exc:
            raise _error(503, "dependency_unavailable", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "scenario_run_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/compile-build")
    def compile_build(request: CompileBuildRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            request_id = _request_id(request.request_id)
            build_id = resolve_build_id(archetype=request.archetype, explicit=request.build_id)
            if not build_id:
                raise ValueError("build_id or archetype mapping to a catalog build is required")
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                target = root / "builds" / _slug(build_id) / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )
            result = compile_catalog_build(build_id, resolved, export_gerber=bool(request.export_gerber))
            gate = build_design_quality_gate(result.design_quality)
            gate_path = resolved / "DESIGN_QUALITY_GATE.json"
            gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")
            fd_path = resolved / "FUNCTIONAL_DELIVERY.json"
            insp_path = resolved / "FABRICATION_INSPECTION.json"
            return _attach_inline_graph(
                {
                    "ok": bool(result.ok and gate.get("build_ready")),
                    "request_id": request_id,
                    "build_id": build_id,
                    **result.to_dict(),
                    "design_quality_gate": gate,
                    "artifacts": {
                        "design_quality": result.design_quality_file,
                        "design_quality_gate": str(gate_path),
                        "kicad_pcb": result.kicad_pcb_file,
                        "gerber_package_dir": result.gerber_package_dir,
                        "functional_delivery": str(fd_path) if fd_path.is_file() else None,
                        "fabrication_inspection": str(insp_path) if insp_path.is_file() else None,
                    },
                }
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "compile_build_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/compose")
    def compose(request: ComposeRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
            request_id = _request_id(request.request_id)
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                target = root / "compose" / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )

            constraints = _compose_constraints(request)
            material_mode = request.material_mode or resolve_material_mode(
                constraints=constraints,
                salvage_mode=bool(request.salvage_mode),
            )

            payload = compose_dispatch(
                out_dir=str(resolved),
                phrase=request.phrase,
                module_ids=request.module_ids,
                canvas_nodes=request.canvas_nodes,
                canvas_wires=request.canvas_wires,
                netlist=request.netlist,
                constraints=constraints,
                material_mode=material_mode,
                salvage_mode=bool(request.salvage_mode),
                export_gerber=bool(request.export_gerber),
                wire_only=bool(request.wire_only),
                allow_llm_first=False,
                request_id=request_id,
            )
            if payload.get("wire_only"):
                return payload
            return _attach_inline_graph(payload)
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "compose_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/compose-canvas")
    def compose_canvas(request: ComposeCanvasRequest) -> Dict[str, Any]:
        """Editor/canvas nodes → same compile engine (material_mode explicit)."""
        wrapped = ComposeRequest(
            canvas_nodes=request.nodes,
            canvas_wires=request.wires,
            constraints=request.constraints,
            material_mode=request.material_mode,
            strategy_mode=request.strategy_mode,
            salvage_mode=request.salvage_mode,
            allowed_purchases=request.allowed_purchases,
            out_dir=request.out_dir,
            request_id=request.request_id,
            export_gerber=request.export_gerber,
            wire_only=request.wire_only,
        )
        return compose(wrapped)

    @app.post("/v1/netlist-compile")
    def netlist_compile(request: NetlistCompileRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
            request_id = _request_id(request.request_id)
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                target = root / "netlist" / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )
            netlist = _netlist_from_request(request)
            payload = compose_dispatch(
                out_dir=str(resolved),
                netlist=netlist.to_dict(),
                export_gerber=bool(request.export_gerber),
                allow_llm_first=False,
                request_id=request_id,
                build_id=request.build_id,
            )
            return _attach_inline_graph(payload)
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "netlist_compile_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/engine-verify")
    def engine_verify(request: EngineVerifyRequest) -> Dict[str, Any]:
        """Compile catalog builds headlessly (no FreeRouting) for agent/CI verify backends."""
        request_id = _request_id(None)
        os.environ["HARDWARE_SPLICER_AUTOROUTE"] = "0"
        os.environ["HARDWARE_SPLICER_JLC_ENRICH"] = "0"
        build_ids = list(request.build_ids or CATALOG_BUILD_IDS)
        root = _api_output_root() / "engine_verify" / request_id
        rows = []
        for build_id in build_ids:
            out = root / build_id
            result = compile_catalog_build(build_id, str(out), export_gerber=False)
            q = result.design_quality or {}
            warn = int(q.get("kicad_drc_warnings") or 0)
            rows.append(
                {
                    "build_id": build_id,
                    "ok": bool(result.ok),
                    "kicad_drc_errors": int(q.get("kicad_drc_errors") or 0),
                    "kicad_drc_warnings": warn,
                    "copper_tier": q.get("copper_tier"),
                    "fab_recommendation": q.get("fab_recommendation"),
                    "warnings_over_budget": warn > int(request.max_kicad_drc_warnings),
                    "error": result.error,
                }
            )
        clean = [r for r in rows if r.get("ok") and r.get("kicad_drc_errors", 1) == 0]
        return {
            "ok": len(clean) == len(rows),
            "request_id": request_id,
            "autoroute": False,
            "verified": len(clean),
            "total": len(rows),
            "rows": rows,
        }

    @app.post("/v1/splice-and-build")
    def splice_and_build(request: SpliceAndBuildRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            request_id = _request_id(request.request_id)
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                project_slug = _slug(
                    str(
                        request.intake.get("project_name")
                        or request.intake.get("goal")
                        or request.intake.get("name")
                        or "splice_build"
                    )
                )
                target = root / "splice_builds" / project_slug / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )
            return splice_and_build_from_intake(
                request.intake,
                out_dir=resolved,
                export_gerber=bool(request.export_gerber),
                request_id=request_id,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "splice_and_build_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/splice-bench/status")
    def splice_bench_status_route(request: SpliceBenchStatusRequest) -> Dict[str, Any]:
        try:
            build_dir = Path(request.build_dir).resolve()
            if not build_dir.is_dir():
                raise ValueError(f"build_dir not found: {build_dir}")
            session = bench_status(build_dir)
            return {"ok": True, **session}
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "splice_bench_status_error", str(exc)) from exc

    @app.post("/v1/splice-bench/submit")
    def splice_bench_submit_route(request: SpliceBenchSubmitRequest) -> Dict[str, Any]:
        try:
            build_dir = Path(request.build_dir).resolve()
            if not build_dir.is_dir():
                raise ValueError(f"build_dir not found: {build_dir}")
            session = submit_bench_measurements(build_dir, request.measurements)
            return {"ok": True, **session}
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "splice_bench_submit_error", str(exc)) from exc

    @app.get("/v1/vision/capabilities")
    def vision_capabilities_route() -> Dict[str, Any]:
        from .sdk import vision_capabilities

        return vision_capabilities()

    @app.post("/v1/vision/enrich-intake")
    def vision_enrich_intake_route(request: VisionEnrichRequest) -> Dict[str, Any]:
        from .sdk import vision_enrich_intake

        try:
            return vision_enrich_intake(
                request.intake,
                apply=request.apply,
                live=request.live,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "vision_enrich_error", str(exc)) from exc

    @app.post("/v1/donor-board-vision")
    def donor_board_vision_route(request: DonorBoardVisionRequest) -> Dict[str, Any]:
        from .sdk import donor_board_vision_enrich

        try:
            return donor_board_vision_enrich(request.intake)
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "donor_board_vision_error", str(exc)) from exc

    @app.post("/v1/splice-bench/submit-capture")
    def splice_bench_submit_capture_route(request: SpliceBenchCaptureRequest) -> Dict[str, Any]:
        from .sdk import splice_bench_submit_capture

        try:
            build_dir = Path(request.build_dir).resolve()
            if not build_dir.is_dir():
                raise ValueError(f"build_dir not found: {build_dir}")
            return splice_bench_submit_capture(build_dir, request.capture)
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "splice_bench_capture_error", str(exc)) from exc

    @app.post("/v1/splice-bench/capture-template")
    def splice_bench_capture_template_route(request: SpliceBenchTemplateRequest) -> Dict[str, Any]:
        from .sdk import splice_bench_capture_template

        try:
            build_dir = Path(request.build_dir).resolve()
            if not build_dir.is_dir():
                raise ValueError(f"build_dir not found: {build_dir}")
            return splice_bench_capture_template(build_dir)
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "splice_bench_template_error", str(exc)) from exc

    @app.post("/v1/splice-golden-loop")
    def splice_golden_loop_route(request: SpliceGoldenLoopRequest) -> Dict[str, Any]:
        from .sdk import splice_golden_loop

        request_id: str | None = None
        try:
            request_id = _request_id(request.request_id)
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                project_slug = _slug(
                    str(
                        request.intake.get("project_name")
                        or request.intake.get("goal")
                        or request.intake.get("name")
                        or "splice_golden_loop"
                    )
                )
                target = root / "splice_golden_loops" / project_slug / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )
            return splice_golden_loop(
                request.intake,
                out_dir=resolved,
                export_gerber=bool(request.export_gerber),
                simulate_bench=bool(request.simulate_bench),
                request_id=request_id,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "splice_golden_loop_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/intake-run")
    def intake_run(request: IntakeRunRequest) -> Dict[str, Any]:
        request_id: str | None = None
        try:
            request_id = _request_id(request.request_id)
            intake = dict(request.intake)
            plan = plan_project_from_intake(intake)
            spec = HardwareCompileSpec.from_dict(plan["scenario"]["compile_spec"])
            out_dir = _resolve_api_out_dir(request, spec, request_id)
            return run_project_intake(
                intake,
                out_dir=out_dir,
                start_splicer=bool(request.start_splicer),
                splicer_port=int(request.splicer_port or 0),
                request_id=request_id,
            )
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except (TimeoutError, ConnectionError, ServiceStartError) as exc:
            raise _error(503, "dependency_unavailable", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "intake_run_error", str(exc), request_id=request_id) from exc

    @app.post("/v1/jobs", status_code=202)
    def submit_job(request: CompileRequest) -> Dict[str, Any]:
        try:
            request_id = _request_id(request.request_id)
            spec = HardwareCompileSpec.from_dict(request.spec)
            spec = replace(spec, board_design_files=_resolve_board_design_files(spec.board_design_files))
            raise_for_validation_errors(validate_compile_spec(spec))
            out_dir = _resolve_api_out_dir(request, spec, request_id)
            job = job_backend.submit(
                job_id=request_id,
                request_id=request_id,
                spec=spec,
                output_dir=out_dir,
                start_splicer=bool(request.start_splicer),
                splicer_port=int(request.splicer_port or 0),
            )
            status_code = 200 if job.status != "queued" else 202
            return JSONResponse(status_code=status_code, content=job.to_dict(include_result=False))
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "job_submit_error", str(exc)) from exc

    @app.post("/v1/jobs/compose", status_code=202)
    def submit_compose_job(request: ComposeJobRequest) -> Dict[str, Any]:
        try:
            request_id = _request_id(request.request_id)
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                target = root / "compose" / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )
            constraints = _compose_constraints(request)
            material_mode = request.material_mode or resolve_material_mode(
                constraints=constraints,
                salvage_mode=bool(request.salvage_mode),
            )
            payload = {
                "phrase": request.phrase,
                "module_ids": request.module_ids,
                "canvas_nodes": request.canvas_nodes,
                "canvas_wires": request.canvas_wires,
                "netlist": request.netlist,
                "constraints": constraints,
                "material_mode": material_mode,
                "salvage_mode": bool(request.salvage_mode),
                "export_gerber": bool(request.export_gerber),
                "wire_only": bool(request.wire_only),
            }
            project_name = request.phrase or "-".join(request.module_ids or []) or "compose"
            job = job_backend.submit_task(
                job_id=request_id,
                request_id=request_id,
                project_name=_slug(project_name)[:80],
                output_dir=resolved,
                job_type="compose",
                payload=payload,
            )
            status_code = 200 if job.status != "queued" else 202
            return JSONResponse(status_code=status_code, content=job.to_dict(include_result=False))
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "job_submit_error", str(exc)) from exc

    @app.post("/v1/jobs/splice-build", status_code=202)
    def submit_splice_build_job(request: SpliceBuildJobRequest) -> Dict[str, Any]:
        try:
            request_id = _request_id(request.request_id)
            root = _api_output_root()
            root.mkdir(parents=True, exist_ok=True)
            if request.out_dir:
                target = Path(request.out_dir)
                if not target.is_absolute():
                    target = root / target
            else:
                target = root / "splice" / request_id
            resolved = target.resolve()
            if not _allow_arbitrary_out_dir() and resolved != root and root not in resolved.parents:
                raise ValueError(
                    f"out_dir must be inside HARDWARE_SPLICER_OUTPUT_ROOT ({root}); "
                    "set HARDWARE_SPLICER_ALLOW_ARBITRARY_OUT_DIR=1 for trusted local development"
                )
            intake = dict(request.intake)
            project_name = str(intake.get("project_name") or intake.get("goal") or "splice-build")
            job = job_backend.submit_task(
                job_id=request_id,
                request_id=request_id,
                project_name=_slug(project_name)[:80],
                output_dir=resolved,
                job_type="splice_build",
                payload={"intake": intake, "export_gerber": bool(request.export_gerber)},
            )
            status_code = 200 if job.status != "queued" else 202
            return JSONResponse(status_code=status_code, content=job.to_dict(include_result=False))
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc)) from exc
        except Exception as exc:
            raise _error(500, "job_submit_error", str(exc)) from exc

    @app.get("/v1/jobs")
    def list_jobs(status: str | None = None, limit: int = 100) -> Dict[str, Any]:
        jobs = job_backend.store.list_jobs(status=status, limit=limit)
        return {
            "ok": True,
            "jobs": [job.to_dict(include_result=False) for job in jobs],
            "stats": job_backend.store.stats(),
        }

    @app.get("/v1/jobs/{job_id}")
    def get_job(job_id: str) -> Dict[str, Any]:
        job = job_backend.store.get_job(job_id)
        if not job:
            raise _error(404, "job_not_found", f"Job not found: {job_id}")
        return job.to_dict(include_result=False)

    @app.get("/v1/jobs/{job_id}/result")
    def get_job_result(job_id: str) -> Dict[str, Any]:
        job = job_backend.store.get_job(job_id)
        if not job:
            raise _error(404, "job_not_found", f"Job not found: {job_id}")
        if job.status != "succeeded" or not job.result:
            return {"ok": False, "job": job.to_dict(include_result=False)}
        return {"ok": True, "job_id": job.job_id, "result": job.result}

    @app.get("/v1/jobs/{job_id}/artifacts")
    def get_job_artifacts(job_id: str) -> Dict[str, Any]:
        job = job_backend.store.get_job(job_id)
        if not job:
            raise _error(404, "job_not_found", f"Job not found: {job_id}")
        return artifact_manifest(job)

    @app.get("/v1/jobs/{job_id}/bundle")
    def get_job_bundle(job_id: str) -> FileResponse:
        job = job_backend.store.get_job(job_id)
        if not job:
            raise _error(404, "job_not_found", f"Job not found: {job_id}")
        try:
            archive = build_output_archive(job)
        except FileNotFoundError as exc:
            raise _error(409, "bundle_not_available", str(exc)) from exc
        return FileResponse(
            archive,
            media_type="application/zip",
            filename=f"{job.project_name}-{job.request_id}.zip",
        )

    @app.post("/v1/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> Dict[str, Any]:
        if not job_backend.store.get_job(job_id):
            raise _error(404, "job_not_found", f"Job not found: {job_id}")
        cancelled = job_backend.store.cancel_job(job_id)
        job = job_backend.store.get_job(job_id)
        return {"ok": cancelled, "job": job.to_dict(include_result=False) if job else None}

    @app.post("/v1/jobs/{job_id}/retry")
    def retry_job(job_id: str) -> Dict[str, Any]:
        if not job_backend.store.get_job(job_id):
            raise _error(404, "job_not_found", f"Job not found: {job_id}")
        retried = job_backend.store.retry_job(job_id)
        if not retried:
            raise _error(409, "job_not_retryable", f"Job {job_id} is not in a terminal status.")
        job_backend.start()
        job = job_backend.store.get_job(job_id)
        return {"ok": True, "job": job.to_dict(include_result=False) if job else None}

    _maybe_mount_splice_ui(app)
    return app


def _maybe_mount_splice_ui(app: FastAPI) -> None:
    flag = os.environ.get("HARDWARE_SPLICER_SERVE_UI", "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return

    ui_dist = Path(__file__).resolve().parents[2] / "apps" / "splice-ui" / "dist"
    index_path = ui_dist / "index.html"
    if not index_path.is_file():
        return

    assets_dir = ui_dist / "assets"
    if assets_dir.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=assets_dir), name="splice-ui-assets")

    reserved = ("v1", "health", "openapi.json", "docs", "redoc")

    @app.get("/", include_in_schema=False)
    def splice_ui_root() -> FileResponse:
        return FileResponse(index_path)

    @app.get("/{spa_path:path}", include_in_schema=False)
    def splice_ui_spa(spa_path: str) -> FileResponse:
        if spa_path.split("/", 1)[0] in reserved:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = ui_dist / spa_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)


app = create_app()
