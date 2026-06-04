from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from .compiler import compile_hardware_bundle
from .robotics_platform_authority import LEVELS as ROBOTICS_PLATFORM_LEVELS
from .schemas import HardwareCompileResult, HardwareCompileSpec


SCHEMA_VERSION = "hardware_splicer.project_authority.v1"

PROJECT_LEVEL_SCORES = {
    "compile_failed": 0.0,
    "project_intake": 0.18,
    "architecture_project_package": 0.42,
    "control_safety_project_package": 0.62,
    "simulation_bench_project_package": 0.78,
    "field_validated_project_package": 0.90,
    "production_ready_project_package": 1.00,
}

MECHATRONICS_LEVELS = [
    "system_intake",
    "electrical_circuit_authority",
    "mechanical_robotics_authority",
    "packaging_authority",
    "integrated_bench_authority",
    "production_mechatronics_release",
]


def load_hardware_scenario(path: str | Path) -> Dict[str, Any]:
    source = Path(path).resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("scenario file must contain a JSON object")
    scenario = dict(data)
    scenario.setdefault("source_file", str(source))
    return scenario


def scenario_to_compile_spec(scenario: Mapping[str, Any], *, base_dir: str | Path | None = None) -> HardwareCompileSpec:
    body = _to_dict(scenario, "scenario")
    scenario_base = _scenario_base_dir(body, base_dir)
    if body.get("compile_spec_path"):
        spec_path = Path(str(body["compile_spec_path"]))
        if not spec_path.is_absolute():
            spec_path = scenario_base / spec_path
        spec = HardwareCompileSpec.from_json_file(spec_path)
        spec_data = spec.to_dict()
    elif isinstance(body.get("compile_spec"), Mapping):
        spec_data = dict(body["compile_spec"])
    else:
        raise ValueError("scenario must provide compile_spec_path or compile_spec")

    overrides = _to_dict(body.get("overrides") or {}, "scenario.overrides")
    if overrides:
        spec_data = _deep_merge(spec_data, overrides)
    spec = HardwareCompileSpec.from_dict(spec_data)
    if not body.get("compile_spec_path"):
        spec = replace(spec, board_design_files=_resolve_board_design_files(spec.board_design_files, scenario_base))
    return spec


def run_hardware_scenario(
    scenario: Mapping[str, Any],
    *,
    out_dir: str | Path,
    start_splicer: bool = True,
    splicer_port: int = 0,
    request_id: str | None = None,
) -> Dict[str, Any]:
    body = _to_dict(scenario, "scenario")
    spec = scenario_to_compile_spec(body)
    result = compile_hardware_bundle(
        spec,
        out_dir=out_dir,
        start_splicer=start_splicer,
        splicer_port=splicer_port,
        request_id=request_id or _request_id_from_scenario(body),
    )
    project_authority = build_project_authority_packet(body, result=result, spec=spec)
    out_path = Path(result.out_dir)
    project_authority_file = out_path / "PROJECT_AUTHORITY.json"
    scenario_summary_file = out_path / "SCENARIO_SUMMARY.md"
    scenario_result_file = out_path / "SCENARIO_RESULT.json"
    project_authority_file.write_text(json.dumps(project_authority, indent=2), encoding="utf-8")
    scenario_summary_file.write_text(render_scenario_summary(project_authority), encoding="utf-8")

    artifacts = {
        **result.artifacts,
        "project_authority": str(project_authority_file),
        "scenario_summary": str(scenario_summary_file),
        "scenario_result": str(scenario_result_file),
    }
    run_result = {
        "ok": bool(result.ok) and bool(project_authority.get("claimable")),
        "compile_ok": bool(result.ok),
        "schema_version": "hardware_splicer.scenario_result.v1",
        "scenario_name": _scenario_name(body, spec),
        "intent": _scenario_intent(body, spec),
        "project_name": result.project_name,
        "request_id": result.request_id,
        "out_dir": result.out_dir,
        "project_authority": project_authority,
        "compile_result": result.to_dict(),
        "artifacts": artifacts,
    }
    scenario_result_file.write_text(json.dumps(run_result, indent=2), encoding="utf-8")
    return run_result


def build_project_authority_packet(
    scenario: Mapping[str, Any],
    *,
    result: HardwareCompileResult,
    spec: HardwareCompileSpec | None = None,
) -> Dict[str, Any]:
    body = _to_dict(scenario, "scenario")
    compile_spec = spec or scenario_to_compile_spec(body)
    expected = _to_dict(body.get("expected") or body.get("expected_authority") or {}, "scenario.expected")
    acceptance = _to_dict(body.get("acceptance") or {}, "scenario.acceptance")
    mechanical = _to_dict(result.mechanical_authority or {}, "mechanical_authority")
    actuation = _to_dict(result.robotics_actuation or {}, "robotics_actuation")
    simulation = _to_dict(result.robotics_simulation or {}, "robotics_simulation")
    platform = _to_dict(result.robotics_platform_authority or {}, "robotics_platform_authority")
    mechatronics = _to_dict(result.mechatronics_authority or {}, "mechatronics_authority")

    artifact_status = _artifact_status(result, acceptance)
    source_blockers = _source_blockers(mechanical, actuation, simulation, platform, mechatronics)
    checks = _project_checks(
        result=result,
        expected=expected,
        acceptance=acceptance,
        artifact_status=artifact_status,
        source_blockers=source_blockers,
        mechanical=mechanical,
        actuation=actuation,
        simulation=simulation,
        platform=platform,
        mechatronics=mechatronics,
    )
    blocking_checks = [row for row in checks if row["severity"] == "block" and not row["passed"]]
    claimable = bool(result.ok) and not blocking_checks
    project_level = _project_level(result.ok, claimable, simulation, platform, mechatronics)
    component_scores = _component_scores(result, mechanical, actuation, simulation, platform, mechatronics)
    authority_score = PROJECT_LEVEL_SCORES.get(project_level, 0.0)
    if authority_score < 1.0:
        authority_score = round(min(authority_score, _weighted_score(component_scores)), 2)
    source_blockers_are_next_actions = bool(acceptance.get("source_blockers_are_next_actions"))
    blockers = _dedupe_strings([row["message"] for row in blocking_checks] + ([] if source_blockers_are_next_actions else source_blockers))
    next_actions = _next_actions(blockers, simulation, platform, mechatronics, mechanical, actuation)
    if source_blockers_are_next_actions:
        next_actions = _dedupe_strings(source_blockers + next_actions)[:12]

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_name": _scenario_name(body, compile_spec),
        "intent": _scenario_intent(body, compile_spec),
        "project_name": result.project_name,
        "request_id": result.request_id,
        "generated_at": result.generated_at,
        "project_authority_level": project_level,
        "authority_score": authority_score,
        "claimable": claimable,
        "release_decision": "authorized_scoped_project_package" if claimable else "evidence_required_before_project_claim",
        "dashboard": {
            "compile_ok": bool(result.ok),
            "simulation_ready": bool(simulation.get("simulation_ready")),
            "robotics_project_release": bool(platform.get("production_authorized")),
            "hardware_splicer_release": bool(mechatronics.get("production_authorized")),
            "blocking_findings": len(blockers),
            "required_artifacts_present": artifact_status["required_present"],
        },
        "component_scores": component_scores,
        "subsystem_authority": {
            "mechanical": _authority_summary(mechanical),
            "robotics_actuation": _authority_summary(actuation),
            "robotics_simulation": {
                "simulation_ready": bool(simulation.get("simulation_ready")),
                "blocking_finding_count": int(simulation.get("blocking_finding_count") or 0),
                "warning_count": int(simulation.get("warning_count") or 0),
                "coverage": simulation.get("coverage") or {},
            },
            "robotics_platform": _authority_summary(platform),
            "mechatronics": _authority_summary(mechatronics),
        },
        "checks": checks,
        "blockers": blockers,
        "source_blocker_count": len(source_blockers),
        "artifact_status": artifact_status,
        "expectations": expected,
        "acceptance": acceptance,
        "can": _capabilities(project_level, claimable, simulation, platform, mechatronics),
        "claim_boundary": {
            "scenario": _scenario_intent(body, compile_spec),
            "platform": platform.get("claim_boundary"),
            "mechatronics": mechatronics.get("claim_boundary"),
            "simulation": simulation.get("claim_boundary"),
        },
        "next_actions": next_actions,
    }


def render_scenario_summary(packet: Mapping[str, Any]) -> str:
    body = _to_dict(packet, "project_authority")
    dashboard = _to_dict(body.get("dashboard") or {}, "dashboard")
    lines = [
        f"# Project Authority: {body.get('scenario_name') or body.get('project_name') or 'Hardware-Splicer Scenario'}",
        "",
        f"- Intent: {body.get('intent') or 'not declared'}",
        f"- Authority level: `{body.get('project_authority_level')}`",
        f"- Authority score: `{body.get('authority_score')}`",
        f"- Claimable: `{bool(body.get('claimable'))}`",
        f"- Compile OK: `{bool(dashboard.get('compile_ok'))}`",
        f"- Simulation ready: `{bool(dashboard.get('simulation_ready'))}`",
        f"- Robotics project release: `{bool(dashboard.get('robotics_project_release'))}`",
        f"- Hardware-Splicer release: `{bool(dashboard.get('hardware_splicer_release'))}`",
        f"- Required artifacts present: `{bool(dashboard.get('required_artifacts_present'))}`",
        "",
        "## Checks",
    ]
    for row in _list_dicts(body.get("checks")):
        status = "pass" if row.get("passed") else "block"
        lines.append(f"- `{status}` {row.get('id')}: {row.get('message')}")
    blockers = _string_list(body.get("blockers"))
    if blockers:
        lines.extend(["", "## Blockers"])
        for blocker in blockers[:16]:
            lines.append(f"- {blocker}")
    next_actions = _string_list(body.get("next_actions"))
    if next_actions:
        lines.extend(["", "## Next Actions"])
        for action in next_actions[:16]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def _project_checks(
    *,
    result: HardwareCompileResult,
    expected: Dict[str, Any],
    acceptance: Dict[str, Any],
    artifact_status: Dict[str, Any],
    source_blockers: List[str],
    mechanical: Dict[str, Any],
    actuation: Dict[str, Any],
    simulation: Dict[str, Any],
    platform: Dict[str, Any],
    mechatronics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    _check(checks, "compile_ok", bool(result.ok), "Compiler generated a complete build bundle.", "Compiler did not generate a complete build bundle.")
    if "mechanical_release" in expected:
        _check(
            checks,
            "mechanical_release",
            bool(mechanical.get("production_authorized")) == bool(expected.get("mechanical_release")),
            "Mechanical release matches scenario expectation.",
            f"Mechanical release expected {bool(expected.get('mechanical_release'))}, observed {bool(mechanical.get('production_authorized'))}.",
        )
    if "robotics_release" in expected:
        _check(
            checks,
            "robotics_release",
            bool(actuation.get("production_authorized")) == bool(expected.get("robotics_release")),
            "Robotics actuation release matches scenario expectation.",
            f"Robotics actuation release expected {bool(expected.get('robotics_release'))}, observed {bool(actuation.get('production_authorized'))}.",
        )
    if "simulation_ready" in expected:
        _check(
            checks,
            "simulation_ready",
            bool(simulation.get("simulation_ready")) == bool(expected.get("simulation_ready")),
            "Simulation readiness matches scenario expectation.",
            f"Simulation readiness expected {bool(expected.get('simulation_ready'))}, observed {bool(simulation.get('simulation_ready'))}.",
        )
    if "mechatronics_release" in expected:
        _check(
            checks,
            "mechatronics_release",
            bool(mechatronics.get("production_authorized")) == bool(expected.get("mechatronics_release")),
            "Hardware-Splicer release matches scenario expectation.",
            f"Hardware-Splicer release expected {bool(expected.get('mechatronics_release'))}, observed {bool(mechatronics.get('production_authorized'))}.",
        )
    if "robotics_project_release" in expected:
        _check(
            checks,
            "robotics_project_release",
            bool(platform.get("production_authorized")) == bool(expected.get("robotics_project_release")),
            "Robotics project release matches scenario expectation.",
            f"Robotics project release expected {bool(expected.get('robotics_project_release'))}, observed {bool(platform.get('production_authorized'))}.",
        )
    minimum = str(expected.get("minimum_authority_level") or "").strip()
    if minimum:
        platform_level = str(platform.get("current_authority_level") or "")
        _check(
            checks,
            "minimum_robotics_platform_authority",
            _level_at_least(platform_level, minimum, ROBOTICS_PLATFORM_LEVELS),
            f"Robotics platform reached required level `{minimum}`.",
            f"Robotics platform is `{platform_level or 'none'}`, below required `{minimum}`.",
        )
    _check(
        checks,
        "required_artifacts",
        bool(artifact_status["required_present"]),
        "Required scenario artifacts are present.",
        "Required scenario artifacts are missing: " + ", ".join(artifact_status["missing_required"]),
    )
    if "allowed_blockers" in acceptance:
        allowed = max(_int(acceptance.get("allowed_blockers"), 0), 0)
        _check(
            checks,
            "allowed_blockers",
            len(source_blockers) <= allowed,
            f"Source blocker count {len(source_blockers)} is within allowed limit {allowed}.",
            f"Source blocker count {len(source_blockers)} exceeds allowed limit {allowed}.",
        )
    return checks


def _project_level(
    compile_ok: bool,
    claimable: bool,
    simulation: Dict[str, Any],
    platform: Dict[str, Any],
    mechatronics: Dict[str, Any],
) -> str:
    if not compile_ok:
        return "compile_failed"
    platform_level = str(platform.get("current_authority_level") or "")
    mecha_level = str(mechatronics.get("current_authority_level") or "")
    if claimable and bool(platform.get("production_authorized")) and bool(mechatronics.get("production_authorized")) and bool(simulation.get("simulation_ready")):
        return "production_ready_project_package"
    if _level_at_least(platform_level, "field_validation_authority", ROBOTICS_PLATFORM_LEVELS):
        return "field_validated_project_package"
    if bool(simulation.get("simulation_ready")) and _level_at_least(platform_level, "simulation_bench_authority", ROBOTICS_PLATFORM_LEVELS):
        return "simulation_bench_project_package"
    if _level_at_least(platform_level, "control_safety_architecture", ROBOTICS_PLATFORM_LEVELS) or _level_at_least(mecha_level, "integrated_bench_authority", MECHATRONICS_LEVELS):
        return "control_safety_project_package"
    if _level_at_least(platform_level, "power_drive_architecture", ROBOTICS_PLATFORM_LEVELS) or _level_at_least(mecha_level, "mechanical_robotics_authority", MECHATRONICS_LEVELS):
        return "architecture_project_package"
    return "project_intake"


def _component_scores(
    result: HardwareCompileResult,
    mechanical: Dict[str, Any],
    actuation: Dict[str, Any],
    simulation: Dict[str, Any],
    platform: Dict[str, Any],
    mechatronics: Dict[str, Any],
) -> Dict[str, float]:
    sim_score = 1.0 if simulation.get("simulation_ready") else max(0.0, 0.7 - int(simulation.get("blocking_finding_count") or 0) * 0.15)
    return {
        "compile": 1.0 if result.ok else 0.0,
        "mechanical": _float(mechanical.get("authority_score"), 0.0),
        "robotics_actuation": _float(actuation.get("authority_score"), 0.0),
        "robotics_simulation": round(sim_score, 2),
        "robotics_platform": _float(platform.get("authority_score"), 0.0),
        "mechatronics": _float(mechatronics.get("authority_score"), 0.0),
    }


def _weighted_score(scores: Dict[str, float]) -> float:
    weights = {
        "compile": 0.08,
        "mechanical": 0.14,
        "robotics_actuation": 0.14,
        "robotics_simulation": 0.18,
        "robotics_platform": 0.24,
        "mechatronics": 0.22,
    }
    return round(sum(scores.get(key, 0.0) * weight for key, weight in weights.items()), 2)


def _source_blockers(
    mechanical: Dict[str, Any],
    actuation: Dict[str, Any],
    simulation: Dict[str, Any],
    platform: Dict[str, Any],
    mechatronics: Dict[str, Any],
) -> List[str]:
    blockers: List[str] = []
    for packet_name, packet in [
        ("mechanical", mechanical),
        ("robotics actuation", actuation),
        ("robotics simulation", simulation),
        ("robotics platform", platform),
        ("mechatronics", mechatronics),
    ]:
        for row in _list_dicts(packet.get("stages")):
            if row.get("passed") is False:
                blockers.extend(f"{packet_name}: {msg}" for msg in _string_list(row.get("blockers")))
                break
    for row in _list_dicts(simulation.get("blocking_findings")):
        msg = str(row.get("message") or "").strip()
        if msg:
            blockers.append(f"robotics simulation: {msg}")
    return _dedupe_strings(blockers)


def _artifact_status(result: HardwareCompileResult, acceptance: Dict[str, Any]) -> Dict[str, Any]:
    index = {
        "bundle_file": result.bundle_file,
        "report_file": result.report_file,
        "summary_file": result.summary_file,
        "manifest_file": result.manifest_file,
        "metadata_file": result.metadata_file,
        **result.artifacts,
    }
    required = _string_list(acceptance.get("must_have_artifacts"))
    rows = []
    missing = []
    for required_name in required:
        matched = _match_artifact(required_name, index)
        exists = bool(matched and Path(matched).exists())
        rows.append({"required": required_name, "path": matched, "exists": exists})
        if not exists:
            missing.append(required_name)
    return {
        "required": required,
        "required_present": not missing,
        "missing_required": missing,
        "checks": rows,
        "available": {key: value for key, value in sorted(index.items())},
    }


def _match_artifact(required: str, index: Dict[str, str]) -> str | None:
    target = required.strip()
    for key, path in index.items():
        if key == target or Path(path).name == target:
            return path
    lowered = target.lower()
    for key, path in index.items():
        if key.lower() == lowered or Path(path).name.lower() == lowered:
            return path
    return None


def _authority_summary(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "authority_level": packet.get("current_authority_level"),
        "authority_score": packet.get("authority_score"),
        "production_authorized": bool(packet.get("production_authorized")),
        "release_decision": packet.get("release_decision"),
        "next_action_id": packet.get("next_action_id"),
    }


def _capabilities(
    project_level: str,
    claimable: bool,
    simulation: Dict[str, Any],
    platform: Dict[str, Any],
    mechatronics: Dict[str, Any],
) -> List[str]:
    capabilities = [
        "Compile one unified project artifact bundle from circuit, mechanism, robotics, and packaging inputs.",
        "Show a single project authority dashboard instead of separate subsystem fragments.",
    ]
    if simulation.get("simulation_ready"):
        capabilities.append("Use deterministic margins for current, runtime, drive speed, traction, servo load, and safety gates.")
    if _level_at_least(str(platform.get("current_authority_level") or ""), "simulation_bench_authority", ROBOTICS_PLATFORM_LEVELS):
        capabilities.append("Defend a bench-ready robotics/mechatronics project claim with traceable evidence.")
    if bool(mechatronics.get("production_authorized")):
        capabilities.append("Defend scoped Hardware-Splicer release across circuit, mechanism, packaging, and integrated bench evidence.")
    if claimable:
        capabilities.append("Claim scoped project package readiness for the declared scenario boundary.")
    else:
        capabilities.append(f"Present current project state as `{project_level}` with explicit missing evidence.")
    return capabilities


def _next_actions(
    blockers: List[str],
    simulation: Dict[str, Any],
    platform: Dict[str, Any],
    mechatronics: Dict[str, Any],
    mechanical: Dict[str, Any],
    actuation: Dict[str, Any],
) -> List[str]:
    if blockers:
        return blockers[:12]
    actions: List[str] = []
    for packet in [simulation, platform, mechatronics, mechanical, actuation]:
        actions.extend(_string_list(packet.get("next_engineering_actions")))
    for row in _list_dicts(simulation.get("findings")):
        if str(row.get("severity") or "").lower() in {"warn", "warning"}:
            actions.append(str(row.get("message") or "").strip())
    return _dedupe_strings([row for row in actions if row])[:12]


def _check(checks: List[Dict[str, Any]], check_id: str, passed: bool, pass_message: str, fail_message: str) -> None:
    checks.append(
        {
            "id": check_id,
            "passed": bool(passed),
            "severity": "info" if passed else "block",
            "message": pass_message if passed else fail_message,
        }
    )


def _scenario_base_dir(body: Dict[str, Any], base_dir: str | Path | None) -> Path:
    if base_dir is not None:
        return Path(base_dir).resolve()
    source_file = str(body.get("source_file") or "").strip()
    if source_file:
        return Path(source_file).resolve().parent
    return Path.cwd()


def _scenario_name(body: Dict[str, Any], spec: HardwareCompileSpec) -> str:
    return str(body.get("scenario_name") or body.get("name") or spec.project_name).strip() or spec.project_name


def _scenario_intent(body: Dict[str, Any], spec: HardwareCompileSpec) -> str:
    machine = _to_dict(spec.machine or {}, "machine")
    return str(body.get("intent") or machine.get("design_intent") or spec.project_name).strip()


def _request_id_from_scenario(body: Dict[str, Any]) -> str | None:
    value = str(body.get("request_id") or body.get("scenario_name") or body.get("name") or "").strip()
    if not value:
        return None
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-._")
    return slug[:96] or None


def _resolve_board_design_files(board_design_files: Dict[str, Dict[str, Any]], base_dir: Path) -> Dict[str, Dict[str, Any]]:
    resolved: Dict[str, Dict[str, Any]] = {}
    for board_id, meta in board_design_files.items():
        row = dict(meta)
        path = str(row.get("path") or "").strip()
        if path and not Path(path).is_absolute():
            row["path"] = str((base_dir / path).resolve())
        resolved[str(board_id)] = row
    return resolved


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(dict(merged[key]), dict(value))
        else:
            merged[key] = value
    return merged


def _level_at_least(observed: str, minimum: str, ordered: List[str]) -> bool:
    if observed not in ordered or minimum not in ordered:
        return observed == minimum
    return ordered.index(observed) >= ordered.index(minimum)


def _to_dict(data: Any, name: str) -> Dict[str, Any]:
    if data is None:
        return {}
    if not isinstance(data, Mapping):
        raise ValueError(f"{name} must be an object")
    return dict(data)


def _list_dicts(data: Any) -> List[Dict[str, Any]]:
    if not isinstance(data, list):
        return []
    return [dict(row) for row in data if isinstance(row, Mapping)]


def _string_list(data: Any) -> List[str]:
    if data is None:
        return []
    if isinstance(data, str):
        return [data] if data.strip() else []
    if isinstance(data, Iterable) and not isinstance(data, (Mapping, bytes)):
        values = []
        for row in data:
            text = str(row).strip()
            if text:
                values.append(text)
        return values
    return [str(data)]


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    seen = set()
    deduped = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
