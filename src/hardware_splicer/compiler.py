from __future__ import annotations

import json
import shutil
import hashlib
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .runtime import (
    MECHA_ROOT,
    ROOT,
    ensure_circuit_import_path,
    free_port,
    health_ok,
    patched_env,
    runtime_status,
    start_splicer3d,
    stop_process,
    validate_app_roots,
    wait_for_health,
)
from .casefile import build_casefile, build_project_log, render_hardware_review
from .mechatronics_authority import build_mechatronics_authority
from .mechanical_authority import build_mechanical_authority
from .robotics_actuation import build_robotics_actuation_packet
from .robotics_platform_authority import build_robotics_platform_authority
from .robotics_platform_geometry import attach_robotics_platform_geometry
from .robotics_simulation import build_robotics_simulation_packet
from .schemas import HardwareCompileResult, HardwareCompileSpec
from .validation import raise_for_validation_errors, validate_compile_spec


def _resolve_board_design_files(board_design_files: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    resolved: Dict[str, Dict[str, Any]] = {}
    for board_id, meta in board_design_files.items():
        row = dict(meta)
        path = str(row.get("path") or "").strip()
        if path and not Path(path).is_absolute():
            candidates = [Path.cwd() / path, ROOT / path, ROOT / "examples" / path]
            selected = next((candidate for candidate in candidates if candidate.exists()), ROOT / path)
            row["path"] = str(selected.resolve())
        resolved[str(board_id)] = row
    return resolved


def _needs_splicer3d(spec: HardwareCompileSpec) -> bool:
    return bool(spec.run_mechanism_sim and spec.mechanism and spec.use_3d_splicer)


def _copy_mecha_bundle(engineering: Dict[str, Any], out_dir: Path) -> str | None:
    mechanism = ((engineering.get("analysis") or {}).get("mechanism") or {})
    bundle_file = mechanism.get("bundle_file")
    if not bundle_file:
        return None
    source_dir = Path(str(bundle_file)).parent
    if not source_dir.exists():
        return None
    target_dir = out_dir / "mecha_bundle"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)
    return str(target_dir)


def _write_text_artifacts(engineering: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    artifacts: Dict[str, str] = {}
    analysis = engineering.get("analysis") or {}
    mechanism = analysis.get("mechanism") or {}
    splicer3d = mechanism.get("splicer3d") or {}
    if splicer3d:
        response_path = out_dir / "splicer3d_response.json"
        response_path.write_text(json.dumps(splicer3d, indent=2), encoding="utf-8")
        artifacts["splicer3d_response"] = str(response_path)
    script = splicer3d.get("script") if isinstance(splicer3d, dict) else None
    if isinstance(script, str) and script.strip():
        script_path = out_dir / "splicer3d_script.py"
        script_path.write_text(script, encoding="utf-8")
        artifacts["splicer3d_script"] = str(script_path)
    return artifacts


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _readiness(engineering: Dict[str, Any]) -> str:
    analysis = engineering.get("analysis") or {}
    verdict = analysis.get("verdict") or {}
    return verdict.get("status") if isinstance(verdict, dict) else str(verdict or "unknown")


def _manifest(out_dir: Path, result: HardwareCompileResult) -> Dict[str, Any]:
    files = []
    for path in sorted(p for p in out_dir.rglob("*") if p.is_file()):
        files.append(
            {
                "path": str(path.relative_to(out_dir)),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return {
        "schema": "hardware_splicer.manifest.v1",
        "project_name": result.project_name,
        "request_id": result.request_id,
        "ok": result.ok,
        "readiness": _readiness(result.engineering),
        "generated_at": result.generated_at,
        "validation_issues": result.validation_issues,
        "files": files,
    }


def _render_summary(result: HardwareCompileResult) -> str:
    analysis = result.engineering.get("analysis") or {}
    mechanism = analysis.get("mechanism") or {}
    verdict = analysis.get("verdict") or {}
    readiness = verdict.get("status") if isinstance(verdict, dict) else str(verdict or "unknown")
    splicer3d = mechanism.get("splicer3d") or {}
    trace = (result.mechatronics_authority or {}).get("integration_trace") or {}
    coverage = trace.get("coverage_summary") or {}
    if splicer3d.get("ok"):
        splicer_status = str(splicer3d.get("mode") or "ok")
    elif splicer3d.get("script"):
        splicer_status = str(splicer3d.get("mode") or "script_fallback")
    elif splicer3d:
        splicer_status = "failed"
    else:
        splicer_status = "not used"
    lines = [
        f"# Hardware-Splicer Build: {result.project_name}",
        "",
        f"- Request ID: `{result.request_id}`",
        f"- Status: `{'ok' if result.ok else 'failed'}`",
        f"- Readiness: `{readiness or 'unknown'}`",
        f"- Mechanical authority: `{(result.mechanical_authority or {}).get('current_authority_level') or 'not available'}`",
        f"- Mechanical authority score: `{(result.mechanical_authority or {}).get('authority_score', 0)}`",
        f"- Mechanical production release: `{bool((result.mechanical_authority or {}).get('production_authorized'))}`",
        f"- Robotics actuation: `{(result.robotics_actuation or {}).get('current_authority_level') or 'not available'}`",
        f"- Robotics actuation score: `{(result.robotics_actuation or {}).get('authority_score', 0)}`",
        f"- Robotics simulation ready: `{bool((result.robotics_simulation or {}).get('simulation_ready'))}`",
        f"- Robotics simulation blockers: `{(result.robotics_simulation or {}).get('blocking_finding_count', 0)}`",
        f"- Robotics platform authority: `{(result.robotics_platform_authority or {}).get('current_authority_level') or 'not available'}`",
        f"- Robotics platform score: `{(result.robotics_platform_authority or {}).get('authority_score', 0)}`",
        f"- Robotics project release: `{bool((result.robotics_platform_authority or {}).get('production_authorized'))}`",
        f"- Hardware-Splicer authority: `{(result.mechatronics_authority or {}).get('current_authority_level') or 'not available'}`",
        f"- Hardware-Splicer authority score: `{(result.mechatronics_authority or {}).get('authority_score', 0)}`",
        f"- Hardware-Splicer production release: `{bool((result.mechatronics_authority or {}).get('production_authorized'))}`",
        f"- Integration trace quality: `{trace.get('quality_band') or 'not available'}` (`{trace.get('quality_score', 0)}`)",
        f"- Weakest open layer: `{trace.get('weakest_open_layer') or 'none'}`",
        f"- Splicer URL: `{result.splicer_url or 'not used'}`",
        f"- Mecha root: `{mechanism.get('mecha_root') or 'not resolved'}`",
        f"- Mecha bundle: `{result.mecha_bundle_dir or mechanism.get('bundle_file') or 'not generated'}`",
        f"- 3D-Splicer: `{splicer_status}`",
        f"- Mechanism primitives traced: `{coverage.get('mechanism_primitive_count', 0)}`",
        f"- Actuators traced: `{coverage.get('actuator_count', 0)}`",
        f"- DFM findings: `{len(mechanism.get('dfm') or [])}`",
        f"- Simulation findings: `{len(mechanism.get('simulation') or [])}`",
        "",
        "## Outputs",
        f"- `{Path(result.bundle_file).name}`",
        f"- `{Path(result.report_file).name}`",
        f"- `{Path(result.summary_file).name}`",
        f"- `{Path(result.manifest_file).name}`",
        f"- `{Path(result.metadata_file).name}`",
    ]
    if result.artifacts.get("casefile"):
        lines.append(f"- `{Path(result.artifacts['casefile']).name}`")
    if result.artifacts.get("project_log"):
        lines.append(f"- `{Path(result.artifacts['project_log']).name}`")
    if result.artifacts.get("hardware_review"):
        lines.append(f"- `{Path(result.artifacts['hardware_review']).name}`")
    if result.mecha_bundle_dir:
        lines.append("- `mecha_bundle/`")
    if result.artifacts:
        lines.extend(["", "## Extracted Artifacts"])
        for name, path in sorted(result.artifacts.items()):
            lines.append(f"- `{name}`: `{Path(path).name}`")
    open_gaps = trace.get("open_gaps") or []
    if open_gaps:
        lines.extend(["", "## Integration Gaps"])
        for gap in open_gaps[:12]:
            lines.append(f"- {gap}")
    return "\n".join(lines).rstrip() + "\n"


def _build_metadata(result: HardwareCompileResult, spec: HardwareCompileSpec) -> Dict[str, Any]:
    return {
        "schema": "hardware_splicer.build_metadata.v1",
        "request_id": result.request_id,
        "project_name": result.project_name,
        "generated_at": result.generated_at,
        "ok": result.ok,
        "readiness": _readiness(result.engineering),
        "runtime": runtime_status(),
        "splicer_url": result.splicer_url,
        "mechanical_authority": result.mechanical_authority,
        "robotics_actuation": result.robotics_actuation,
        "robotics_simulation": result.robotics_simulation,
        "robotics_platform_authority": result.robotics_platform_authority,
        "mechatronics_authority": result.mechatronics_authority,
        "input": spec.to_dict(),
        "outputs": {
            "bundle_file": result.bundle_file,
            "report_file": result.report_file,
            "summary_file": result.summary_file,
            "manifest_file": result.manifest_file,
            "mecha_bundle_dir": result.mecha_bundle_dir,
            "artifacts": result.artifacts,
        },
        "validation_issues": result.validation_issues,
    }


def compile_hardware_bundle(
    spec: HardwareCompileSpec,
    *,
    out_dir: str | Path,
    start_splicer: bool = True,
    splicer_port: int = 0,
    request_id: str | None = None,
) -> HardwareCompileResult:
    validate_app_roots()
    board_design_files = _resolve_board_design_files(spec.board_design_files)
    run_spec = replace(spec, board_design_files=board_design_files)
    validation_issues = validate_compile_spec(run_spec)
    raise_for_validation_errors(validation_issues)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()
    build_request_id = str(request_id or uuid.uuid4().hex).strip()
    if not build_request_id:
        build_request_id = uuid.uuid4().hex

    proc = None
    splicer_url = None
    if _needs_splicer3d(run_spec):
        port = splicer_port or free_port()
        splicer_url = f"http://127.0.0.1:{port}"
        if start_splicer and not health_ok(splicer_url):
            proc = start_splicer3d(port)
            wait_for_health(splicer_url, proc=proc)
        elif not health_ok(splicer_url):
            raise ConnectionError(f"3D-Splicer is not healthy at {splicer_url}")

    env_values = {"MECHA_SPLICER_ROOT": str(MECHA_ROOT)}
    if splicer_url:
        env_values["SPLICER_API_URL"] = splicer_url

    try:
        with patched_env(env_values):
            ensure_circuit_import_path()
            from src.engines.machine_system_engineering import engineer_machine_system

            engineering = engineer_machine_system(
                run_spec.machine,
                run_mechanism_sim=run_spec.run_mechanism_sim,
                mechanism_spec=run_spec.mechanism,
                simulation_fidelity=run_spec.simulation_fidelity,
                board_design_files=board_design_files,
                use_3d_splicer=run_spec.use_3d_splicer,
                render_stl=run_spec.render_stl,
            )
    finally:
        stop_process(proc)

    mecha_bundle_dir = _copy_mecha_bundle(engineering, out_path)
    robotics_platform_geometry = attach_robotics_platform_geometry(run_spec.to_dict(), engineering=engineering, out_dir=out_path)
    mechanism = ((engineering.get("analysis") or {}).get("mechanism") or {})
    ok = bool(engineering.get("compiled")) and (not run_spec.run_mechanism_sim or not run_spec.mechanism or bool(mechanism.get("ok")))
    if _needs_splicer3d(run_spec):
        splicer3d = mechanism.get("splicer3d") or {}
        ok = ok and bool(splicer3d.get("ok") or splicer3d.get("script"))

    mechanical_authority = build_mechanical_authority(run_spec.to_dict(), engineering=engineering)
    robotics_actuation = build_robotics_actuation_packet(run_spec.to_dict(), engineering=engineering)
    mechatronics_authority = build_mechatronics_authority(
        run_spec.to_dict(),
        engineering=engineering,
        mechanical_authority=mechanical_authority,
        robotics_actuation=robotics_actuation,
    )
    robotics_simulation = build_robotics_simulation_packet(
        run_spec.to_dict(),
        engineering=engineering,
        robotics_actuation=robotics_actuation,
        mechatronics_authority=mechatronics_authority,
    )
    robotics_platform_authority = build_robotics_platform_authority(
        run_spec.to_dict(),
        engineering=engineering,
        mechanical_authority=mechanical_authority,
        robotics_actuation=robotics_actuation,
        mechatronics_authority=mechatronics_authority,
        robotics_simulation=robotics_simulation,
    )

    bundle_file = out_path / "hardware_splicer.bundle.json"
    report_file = out_path / "ENGINEERING_REPORT.md"
    summary_file = out_path / "SUMMARY.md"
    manifest_file = out_path / "MANIFEST.json"
    metadata_file = out_path / "BUILD_METADATA.json"
    artifacts = _write_text_artifacts(engineering, out_path)
    artifacts.update(robotics_platform_geometry.get("artifacts") or {})
    mechanical_authority_file = out_path / "MECHANICAL_AUTHORITY.json"
    mechanical_authority_file.write_text(json.dumps(mechanical_authority, indent=2), encoding="utf-8")
    artifacts["mechanical_authority"] = str(mechanical_authority_file)
    robotics_actuation_file = out_path / "ROBOTICS_ACTUATION.json"
    robotics_actuation_file.write_text(json.dumps(robotics_actuation, indent=2), encoding="utf-8")
    artifacts["robotics_actuation"] = str(robotics_actuation_file)
    robotics_simulation_file = out_path / "ROBOTICS_SIMULATION.json"
    robotics_simulation_file.write_text(json.dumps(robotics_simulation, indent=2), encoding="utf-8")
    artifacts["robotics_simulation"] = str(robotics_simulation_file)
    robotics_platform_file = out_path / "ROBOTICS_PLATFORM_AUTHORITY.json"
    robotics_platform_file.write_text(json.dumps(robotics_platform_authority, indent=2), encoding="utf-8")
    artifacts["robotics_platform_authority"] = str(robotics_platform_file)
    mechatronics_authority_file = out_path / "MECHATRONICS_AUTHORITY.json"
    mechatronics_authority_file.write_text(json.dumps(mechatronics_authority, indent=2), encoding="utf-8")
    artifacts["mechatronics_authority"] = str(mechatronics_authority_file)
    casefile_file = out_path / "CASEFILE.json"
    project_log_file = out_path / "PROJECT_LOG.json"
    hardware_review_file = out_path / "HARDWARE_REVIEW.md"
    indexed_artifacts = {
        **artifacts,
        "casefile": str(casefile_file),
        "project_log": str(project_log_file),
        "hardware_review": str(hardware_review_file),
    }
    casefile = build_casefile(
        spec=run_spec.to_dict(),
        engineering=engineering,
        mechanical_authority=mechanical_authority,
        robotics_actuation=robotics_actuation,
        robotics_simulation=robotics_simulation,
        robotics_platform_authority=robotics_platform_authority,
        mechatronics_authority=mechatronics_authority,
        artifacts=indexed_artifacts,
        generated_at=generated_at,
        request_id=build_request_id,
        out_dir=str(out_path),
        mecha_bundle_dir=mecha_bundle_dir,
        splicer_url=splicer_url,
        ok=ok,
    )
    project_log = build_project_log(casefile)
    casefile_file.write_text(json.dumps(casefile, indent=2), encoding="utf-8")
    project_log_file.write_text(json.dumps(project_log, indent=2), encoding="utf-8")
    hardware_review_file.write_text(render_hardware_review(casefile, project_log), encoding="utf-8")
    artifacts.update(
        {
            "casefile": str(casefile_file),
            "project_log": str(project_log_file),
            "hardware_review": str(hardware_review_file),
        }
    )

    result = HardwareCompileResult(
        ok=ok,
        project_name=run_spec.project_name,
        request_id=build_request_id,
        generated_at=generated_at,
        out_dir=str(out_path),
        bundle_file=str(bundle_file),
        report_file=str(report_file),
        summary_file=str(summary_file),
        manifest_file=str(manifest_file),
        metadata_file=str(metadata_file),
        artifacts=artifacts,
        validation_issues=validation_issues,
        mecha_bundle_dir=mecha_bundle_dir,
        splicer_url=splicer_url,
        engineering=engineering,
        mechanical_authority=mechanical_authority,
        robotics_actuation=robotics_actuation,
        robotics_simulation=robotics_simulation,
        robotics_platform_authority=robotics_platform_authority,
        mechatronics_authority=mechatronics_authority,
    )

    bundle_file.write_text(
        json.dumps(
            {
                "schema": "hardware_splicer.bundle.v1",
                "input": run_spec.to_dict(),
                "casefile": casefile,
                "project_log": project_log,
                **result.to_dict(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report_file.write_text(str(engineering.get("report_md") or ""), encoding="utf-8")
    summary_file.write_text(_render_summary(result), encoding="utf-8")
    metadata_file.write_text(json.dumps(_build_metadata(result, run_spec), indent=2), encoding="utf-8")
    manifest_file.write_text(json.dumps(_manifest(out_path, result), indent=2), encoding="utf-8")
    return result
