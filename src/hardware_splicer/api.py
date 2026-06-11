from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from .build_compiler import compile_catalog_build, resolve_build_id
from .compiler import _resolve_board_design_files, compile_hardware_bundle
from .design_quality import build_design_quality_gate
from .jobs import JobBackend, artifact_manifest, build_output_archive
from .mechatronics_authority import build_mechatronics_authority
from .mechanical_authority import build_mechanical_authority
from .project_intake import plan_project_from_intake, run_project_intake, splice_and_build_from_intake
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
    app = FastAPI(
        title="Hardware-Splicer Compiler",
        version="0.3.0",
        description="Top-level compiler API for Circuit-AI -> Mecha-Splicer -> 3D-Splicer build bundles.",
    )
    app.state.job_backend = job_backend

    @app.on_event("shutdown")
    def shutdown_jobs() -> None:
        job_backend.stop()

    @app.get("/health")
    def health() -> Dict[str, Any]:
        status = runtime_status()
        return {"ok": bool(status.get("ok")), "app_roots": status.get("app_roots")}

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
            return {
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
                },
            }
        except ValueError as exc:
            raise _error(422, "validation_error", str(exc), request_id=request_id) from exc
        except Exception as exc:
            raise _error(500, "compile_build_error", str(exc), request_id=request_id) from exc

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

    @app.get("/v1/jobs")
    def list_jobs(status: str | None = None, limit: int = 100) -> Dict[str, Any]:
        jobs = job_backend.store.list_jobs(status=status, limit=limit)
        return {
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

    return app


app = create_app()
