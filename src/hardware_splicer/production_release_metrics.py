from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from .schemas import HardwareCompileResult


SCHEMA_VERSION = "hardware_splicer.production_release_metrics.v1"

GATE_WEIGHTS = {
    "compile_artifacts": 0.08,
    "circuit_release": 0.10,
    "mechanical_release": 0.14,
    "robotics_actuation_release": 0.12,
    "deterministic_simulation": 0.14,
    "packaging_trace": 0.08,
    "integrated_bench": 0.14,
    "field_validation": 0.10,
    "release_review": 0.10,
}


def build_production_release_metrics(
    *,
    result: HardwareCompileResult | Mapping[str, Any],
    project_authority: Mapping[str, Any],
) -> Dict[str, Any]:
    """Normalize the project-level gap between current authority and production release."""

    result_dict = result.to_dict() if isinstance(result, HardwareCompileResult) else _to_dict(result)
    authority = _to_dict(project_authority)
    mechanical = _to_dict(result_dict.get("mechanical_authority"))
    actuation = _to_dict(result_dict.get("robotics_actuation"))
    simulation = _to_dict(result_dict.get("robotics_simulation"))
    platform = _to_dict(result_dict.get("robotics_platform_authority"))
    mechatronics = _to_dict(result_dict.get("mechatronics_authority"))
    integration_trace = _to_dict(mechatronics.get("integration_trace"))
    layer_closure = _to_dict(integration_trace.get("layer_closure"))
    validation = _to_dict(platform.get("validation_status"))
    platform_release = _to_dict(platform.get("release_status"))
    mechatronics_release = _to_dict(mechatronics.get("release_status"))
    dashboard = _to_dict(authority.get("dashboard"))

    gates = [
        _gate(
            "compile_artifacts",
            "Compile and artifacts",
            bool(result_dict.get("ok")) and bool(dashboard.get("required_artifacts_present", True)),
            1.0 if result_dict.get("ok") else 0.0,
            "compiler bundle",
            _missing_compile(result_dict, dashboard),
            "compile a complete Hardware-Splicer bundle with required artifacts present",
        ),
        _gate(
            "circuit_release",
            "Circuit release evidence",
            bool(layer_closure.get("circuit_release_ready")),
            1.0 if layer_closure.get("circuit_release_ready") else 0.55 if layer_closure.get("electrical_integration_ready") else 0.0,
            _observed_circuit(mechatronics),
            _release_blockers(_to_dict(_to_dict(mechatronics.get("subsystems")).get("circuit")), "circuit/electrical release is not closed"),
            "attach board design files plus reviewed circuit release scope",
        ),
        _gate(
            "mechanical_release",
            "Mechanical measured release",
            bool(mechanical.get("production_authorized")),
            _float(mechanical.get("authority_score"), 0.0),
            str(mechanical.get("current_authority_level") or "unknown"),
            _stage_blockers(mechanical) or _string_list(mechanical.get("next_engineering_actions")),
            "close measured geometry, fit/load bench evidence, and mechanical release review",
        ),
        _gate(
            "robotics_actuation_release",
            "Actuation bench release",
            bool(actuation.get("production_authorized")),
            _float(actuation.get("authority_score"), 0.0),
            str(actuation.get("current_authority_level") or "unknown"),
            _stage_blockers(actuation) or _string_list(actuation.get("next_engineering_actions")),
            "close controlled motion/current bench evidence for actuators",
        ),
        _gate(
            "deterministic_simulation",
            "Deterministic simulation gate",
            bool(simulation.get("simulation_ready")),
            _simulation_partial_score(simulation),
            _observed_simulation(simulation),
            _simulation_blockers(simulation),
            "clear current, runtime, motion, safety, and integration simulation blockers",
        ),
        _gate(
            "packaging_trace",
            "Packaging and integration trace",
            bool(layer_closure.get("packaging_ready")),
            1.0 if layer_closure.get("packaging_ready") else max(0.0, _float(integration_trace.get("quality_score"), 0.0)),
            str(integration_trace.get("quality_band") or "unknown"),
            _integration_gap_blockers(integration_trace, ["packaging_ready"]),
            "generate package/CAD artifacts and close trace gaps",
        ),
        _gate(
            "integrated_bench",
            "Integrated bench evidence",
            bool(layer_closure.get("integrated_bench_ready")),
            _integrated_bench_partial_score(mechatronics, validation),
            _observed_integrated_bench(mechatronics, validation),
            _integration_gap_blockers(integration_trace, ["integrated_bench_ready"]) or _stage_blockers(mechatronics, "integrated_bench_authority"),
            "run integrated electrical, motion, packaging, thermal, or cycle checks with artifacts",
        ),
        _gate(
            "field_validation",
            "Field or mission validation",
            bool(validation.get("field_ready")),
            1.0 if validation.get("field_ready") else 0.0,
            f"{int(validation.get('field_pass_count') or 0)} field passes",
            _field_validation_blockers(validation),
            "record field/mission validation in the declared operating environment",
        ),
        _gate(
            "release_review",
            "Reviewed scoped release",
            bool(platform_release.get("release_ready")) and bool(mechatronics_release.get("release_ready")),
            _release_review_partial_score(platform_release, mechatronics_release),
            _observed_release(platform_release, mechatronics_release),
            _string_list(platform_release.get("blockers")) + _string_list(mechatronics_release.get("blockers")),
            "attach accepted robotics project and Hardware-Splicer release scopes with artifact URIs",
        ),
    ]

    weighted_score = round(sum(row["weighted_score"] for row in gates), 3)
    production_ready = bool(
        authority.get("project_authority_level") == "production_ready_project_package"
        and authority.get("claimable")
        and all(row["passed"] for row in gates)
    )
    blockers = _dedupe_strings([item for row in gates if not row["passed"] for item in row["blockers"]])
    evidence_gap_ids = [row["id"] for row in gates if not row["passed"]]
    deterministic = _deterministic_metrics(simulation)
    return {
        "schema_version": SCHEMA_VERSION,
        "project_name": result_dict.get("project_name") or authority.get("project_name"),
        "request_id": result_dict.get("request_id") or authority.get("request_id"),
        "current_project_level": authority.get("project_authority_level"),
        "production_ready": production_ready,
        "production_readiness_score": weighted_score,
        "production_gap_score": round(max(0.0, 1.0 - weighted_score), 3),
        "readiness_band": _readiness_band(weighted_score, production_ready),
        "gates_passed": len([row for row in gates if row["passed"]]),
        "gates_total": len(gates),
        "weighted_gates": gates,
        "evidence_gap_ids": evidence_gap_ids,
        "top_blockers": blockers[:16],
        "deterministic_margins": deterministic,
        "subsystem_scores": {
            "project_authority": _float(authority.get("authority_score"), 0.0),
            "mechanical": _float(mechanical.get("authority_score"), 0.0),
            "robotics_actuation": _float(actuation.get("authority_score"), 0.0),
            "robotics_platform": _float(platform.get("authority_score"), 0.0),
            "mechatronics": _float(mechatronics.get("authority_score"), 0.0),
            "integration_trace": _float(integration_trace.get("quality_score"), 0.0),
        },
        "what_this_can_claim": _claim_text(authority, production_ready),
        "what_blocks_production": blockers[:8],
    }


def _gate(
    gate_id: str,
    label: str,
    passed: bool,
    raw_score: float,
    observed: str,
    blockers: List[str],
    unlocks: str,
) -> Dict[str, Any]:
    weight = GATE_WEIGHTS[gate_id]
    score = 1.0 if passed else max(0.0, min(float(raw_score), 0.99))
    return {
        "id": gate_id,
        "label": label,
        "weight": weight,
        "passed": bool(passed),
        "score": round(score, 3),
        "weighted_score": round(score * weight, 3),
        "observed": observed,
        "blockers": _dedupe_strings(blockers)[:10] if not passed else [],
        "unlocks": unlocks,
    }


def _missing_compile(result: Dict[str, Any], dashboard: Dict[str, Any]) -> List[str]:
    blockers = []
    if not result.get("ok"):
        blockers.append("Compiler result is not ok.")
    if dashboard.get("required_artifacts_present") is False:
        blockers.append("Required project artifacts are missing.")
    return blockers


def _observed_circuit(mechatronics: Dict[str, Any]) -> str:
    circuit = _to_dict(_to_dict(mechatronics.get("subsystems")).get("circuit"))
    readiness = str(circuit.get("readiness") or "unknown")
    count = int(circuit.get("board_design_file_count") or 0)
    release = bool(circuit.get("release_ready"))
    return f"release_ready={release}, board_design_files={count}, readiness={readiness}"


def _release_blockers(packet: Dict[str, Any], fallback: str) -> List[str]:
    blockers = _string_list(packet.get("release_blockers")) + _string_list(packet.get("blockers"))
    if not blockers:
        blockers.append(fallback)
    return blockers


def _stage_blockers(packet: Dict[str, Any], stage_id: str | None = None) -> List[str]:
    blockers: List[str] = []
    for row in _list_dicts(packet.get("stages")):
        if stage_id and row.get("stage_id") != stage_id:
            continue
        if row.get("status") != "pass" or row.get("passed") is False:
            blockers.extend(_string_list(row.get("blockers")))
            if not stage_id:
                break
    return _dedupe_strings(blockers)


def _simulation_partial_score(simulation: Dict[str, Any]) -> float:
    if simulation.get("simulation_ready"):
        return 1.0
    statuses = []
    for key in ["power_budget", "runtime_estimate", "drive_kinematics", "servo_load_margins", "safety_envelope"]:
        domain = _to_dict(simulation.get(key))
        status = str(domain.get("status") or "").lower()
        if status and status != "not_applicable":
            statuses.append(status)
    if not statuses:
        return 0.0
    passed = len([status for status in statuses if status == "pass"])
    warnings = len([status for status in statuses if status in {"warn", "warning"}])
    score = (passed + warnings * 0.55) / len(statuses)
    blocker_penalty = min(int(simulation.get("blocking_finding_count") or 0) * 0.03, 0.45)
    return round(max(0.0, min(score - blocker_penalty, 0.95)), 3)


def _observed_simulation(simulation: Dict[str, Any]) -> str:
    coverage = _to_dict(simulation.get("coverage"))
    return (
        f"ready={bool(simulation.get('simulation_ready'))}, "
        f"domains={int(coverage.get('computed_domain_count') or 0)}, "
        f"blockers={int(simulation.get('blocking_finding_count') or 0)}"
    )


def _simulation_blockers(simulation: Dict[str, Any]) -> List[str]:
    blockers = []
    for row in _list_dicts(simulation.get("blocking_findings")):
        message = str(row.get("message") or "").strip()
        if message:
            blockers.append(message)
    return _dedupe_strings(blockers)


def _integration_gap_blockers(trace: Dict[str, Any], layer_ids: List[str]) -> List[str]:
    gaps = _string_list(trace.get("open_gaps"))
    if not layer_ids:
        return gaps
    out = []
    for gap in gaps:
        lowered = gap.lower()
        if any(layer.lower() in lowered for layer in layer_ids):
            out.append(gap)
    if out:
        return _dedupe_strings(out)
    closure = _to_dict(trace.get("layer_closure"))
    for layer in layer_ids:
        if closure.get(layer) is False:
            out.append(f"Layer not closed: {layer}.")
    return _dedupe_strings(out)


def _integrated_bench_partial_score(mechatronics: Dict[str, Any], validation: Dict[str, Any]) -> float:
    trace = _to_dict(mechatronics.get("integration_trace"))
    coverage = _to_dict(trace.get("coverage_summary"))
    pass_count = int(coverage.get("bench_pass_count") or validation.get("bench_pass_count") or 0)
    artifacts = int(coverage.get("bench_artifact_count") or validation.get("artifact_count") or 0)
    score = 0.0
    if pass_count:
        score += min(pass_count / 3, 1.0) * 0.65
    if artifacts:
        score += 0.35
    return round(min(score, 0.95), 3)


def _observed_integrated_bench(mechatronics: Dict[str, Any], validation: Dict[str, Any]) -> str:
    trace = _to_dict(mechatronics.get("integration_trace"))
    coverage = _to_dict(trace.get("coverage_summary"))
    return (
        f"bench_passes={int(coverage.get('bench_pass_count') or validation.get('bench_pass_count') or 0)}, "
        f"artifacts={int(coverage.get('bench_artifact_count') or validation.get('artifact_count') or 0)}"
    )


def _field_validation_blockers(validation: Dict[str, Any]) -> List[str]:
    blockers = _string_list(validation.get("blockers"))
    return [row for row in blockers if "field" in row.lower() or "validation" in row.lower() or "artifact" in row.lower()] or blockers


def _release_review_partial_score(platform_release: Dict[str, Any], mechatronics_release: Dict[str, Any]) -> float:
    ready_count = int(bool(platform_release.get("release_ready"))) + int(bool(mechatronics_release.get("release_ready")))
    available_count = int(bool(platform_release.get("available"))) + int(bool(mechatronics_release.get("available")))
    return round(min(ready_count * 0.5 + max(available_count - ready_count, 0) * 0.2, 0.95), 3)


def _observed_release(platform_release: Dict[str, Any], mechatronics_release: Dict[str, Any]) -> str:
    return f"robotics_project={bool(platform_release.get('release_ready'))}, hardware_splicer={bool(mechatronics_release.get('release_ready'))}"


def _deterministic_metrics(simulation: Dict[str, Any]) -> Dict[str, Any]:
    power = _to_dict(simulation.get("power_budget"))
    runtime = _to_dict(simulation.get("runtime_estimate"))
    drive = _to_dict(simulation.get("drive_kinematics"))
    servo = _to_dict(simulation.get("servo_load_margins"))
    return {
        "current_margin": power.get("peak_current_margin"),
        "runtime_margin": runtime.get("runtime_margin"),
        "estimated_runtime_min": runtime.get("estimated_runtime_min"),
        "drive_speed_margin": drive.get("speed_margin") if drive.get("available") else None,
        "drive_force_margin": drive.get("force_margin") if drive.get("available") else None,
        "servo_axes": servo.get("axes") or [],
    }


def _readiness_band(score: float, production_ready: bool) -> str:
    if production_ready:
        return "production_release"
    if score >= 0.85:
        return "near_release"
    if score >= 0.70:
        return "bench_validation_gap"
    if score >= 0.50:
        return "evidence_gap"
    if score >= 0.35:
        return "control_safety_planning"
    return "early_planning"


def _claim_text(authority: Dict[str, Any], production_ready: bool) -> str:
    if production_ready:
        return "Scoped production-ready Hardware-Splicer project package."
    level = str(authority.get("project_authority_level") or "unknown")
    return f"Scoped {level}; production release is blocked until open gates are closed."


def _to_dict(data: Any) -> Dict[str, Any]:
    return dict(data) if isinstance(data, Mapping) else {}


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
        return [str(row).strip() for row in data if str(row).strip()]
    return [str(data)]


def _dedupe_strings(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
