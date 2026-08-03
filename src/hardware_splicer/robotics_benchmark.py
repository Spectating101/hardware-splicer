"""Evaluate how faithfully Hardware Splicer represents increasingly complex robots.

The benchmark is intentionally diagnostic. It does not grant engineering authority
from public reference material, and a high structural score never substitutes for
simulation, bench, field, or release evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

SCHEMA_VERSION = "hardware_splicer.robotics_scaling_benchmark.v1"
SUITE_SCHEMA_VERSION = "hardware_splicer.robotics_scaling_suite.v1"

_DOMAIN_PROBES: dict[str, tuple[tuple[str, ...], ...]] = {
    "mechanical": (("mechanism",),),
    "actuation": (("robotics_actuation",),),
    "control": (("control_stack",),),
    "platform": (("robotics_project",),),
    "safety": (("safety_case",),),
    "electrical": (("electrical",), ("electronics",), ("circuit",), ("power_budget",)),
    "perception": (("perception",), ("sensor_stack",), ("robotics_project", "platform", "sensors")),
    "firmware": (("firmware",), ("firmware_stack",)),
    "ros": (("ros",), ("ros_interfaces",), ("middleware",)),
}


def load_robotics_benchmark(path: str | Path) -> Dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"robotics benchmark must be an object: {source}")
    required = {"benchmark_id", "robot_genre", "expected_archetype", "intake", "stress_profile"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"robotics benchmark {source} missing: {', '.join(missing)}")
    payload.setdefault("source_file", str(source.resolve()))
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _has_path(payload: Mapping[str, Any], path: Iterable[str]) -> bool:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return False
        current = current[key]
    return current not in (None, {}, [], "")


def _contains_key(payload: Any, wanted: set[str]) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized = str(key).strip().lower()
            if normalized in wanted or any(token in normalized for token in wanted):
                if value not in (None, {}, [], ""):
                    return True
            if _contains_key(value, wanted):
                return True
    elif isinstance(payload, (list, tuple)):
        return any(_contains_key(value, wanted) for value in payload)
    return False


def _represented_domains(spec: Mapping[str, Any], plan: Mapping[str, Any]) -> set[str]:
    represented: set[str] = set()
    for domain, probes in _DOMAIN_PROBES.items():
        if any(_has_path(spec, probe) for probe in probes):
            represented.add(domain)
    if _contains_key(spec, {"sensor", "lidar", "camera", "imu", "encoder"}):
        represented.add("perception")
    if _contains_key(spec, {"firmware", "binary", "flash", "toolchain"}):
        represented.add("firmware")
    if _contains_key(spec, {"ros", "topic", "service", "urdf", "middleware"}):
        represented.add("ros")
    if _mapping(plan.get("evidence_summary")) or plan.get("missing_info") is not None:
        represented.add("evidence")
    return represented


def _pressure_index(profile: Mapping[str, Any]) -> float:
    dynamic = {"low": 0.25, "medium": 0.6, "high": 1.0}.get(
        str(profile.get("dynamic_coupling") or "low").lower(), 0.25
    )
    safety = {"low": 0.25, "medium": 0.6, "high": 1.0}.get(
        str(profile.get("safety_criticality") or "low").lower(), 0.25
    )
    values = [
        min(float(profile.get("actuator_count") or 0) / 12.0, 1.0),
        min(float(profile.get("kinematic_chains") or 0) / 4.0, 1.0),
        min(float(profile.get("sensor_count") or 0) / 8.0, 1.0),
        min(float(profile.get("control_loops") or 0) / 8.0, 1.0),
        min(float(profile.get("power_domains") or 0) / 4.0, 1.0),
        min(float(profile.get("external_interfaces") or 0) / 10.0, 1.0),
        dynamic,
        safety,
    ]
    return round(sum(values) / len(values) * 100.0, 1)


def evaluate_robotics_benchmark(
    benchmark: Mapping[str, Any],
    *,
    planner: Callable[..., Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Run one robot reference profile through the real project-intake planner."""

    if planner is None:
        from .project_intake import plan_project_from_intake

        planner = plan_project_from_intake

    intake = _mapping(benchmark.get("intake"))
    plan = dict(planner(intake, skip_vision=True))
    scenario = _mapping(plan.get("scenario"))
    spec = _mapping(scenario.get("compile_spec"))
    profile = _mapping(benchmark.get("stress_profile"))

    expected_archetype = str(benchmark.get("expected_archetype") or "")
    detected_archetype = str(plan.get("archetype") or "")
    archetype_match = detected_archetype == expected_archetype

    required_domains = {str(value) for value in _sequence(profile.get("required_domains"))}
    represented_domains = _represented_domains(spec, plan)
    matched_domains = required_domains & represented_domains
    domain_coverage = (
        len(matched_domains) / len(required_domains) if required_domains else 1.0
    )

    actuators = _sequence(_mapping(spec.get("robotics_actuation")).get("actuators"))
    represented_actuators = len(actuators)
    required_actuators = int(profile.get("actuator_count") or 0)
    actuator_coverage = (
        min(represented_actuators / required_actuators, 1.0)
        if required_actuators
        else 1.0
    )

    source_material = _mapping(benchmark.get("reference_sources"))
    has_video_sources = bool(_sequence(source_material.get("videos")))
    source_governed = bool(
        plan.get("reference_sources")
        or plan.get("video_evidence")
        or _contains_key(plan, {"timestamp", "video_evidence", "reference_source"})
    )

    has_kinematic_identity = _contains_key(
        spec, {"joint_id", "joint_ids", "kinematic_chain", "kinematics", "urdf"}
    )
    has_firmware_lineage = _contains_key(
        spec, {"firmware_revision", "binary_hash", "toolchain", "flash_result", "pin_map_hash"}
    )
    has_ros_lineage = _contains_key(
        spec, {"ros_topic", "ros_service", "ros_interface", "middleware_contract"}
    )
    has_dynamic_validation = _contains_key(
        spec, {"dynamic_validation", "stability", "gait", "flight_envelope", "collision"}
    )

    gaps: list[str] = []
    if not archetype_match:
        gaps.append("native_archetype_missing")
    if actuator_coverage < 1.0:
        gaps.append("actuator_cardinality_loss")
    if int(profile.get("kinematic_chains") or 0) and not has_kinematic_identity:
        gaps.append("kinematic_topology_not_canonical")
    if int(profile.get("firmware_components") or 0) and not has_firmware_lineage:
        gaps.append("firmware_build_lineage_missing")
    if int(profile.get("ros_interfaces") or 0) and not has_ros_lineage:
        gaps.append("ros_interface_lineage_missing")
    if has_video_sources and not source_governed:
        gaps.append("timestamped_video_evidence_missing")
    if str(profile.get("dynamic_coupling") or "").lower() == "high" and not has_dynamic_validation:
        gaps.append("dynamic_system_validation_missing")
    for domain in sorted(required_domains - represented_domains):
        gaps.append(f"domain_not_represented:{domain}")

    score = round(
        20.0 * float(archetype_match)
        + 30.0 * domain_coverage
        + 20.0 * actuator_coverage
        + 10.0 * float(source_governed or not has_video_sources)
        + 10.0 * float(has_kinematic_identity or not int(profile.get("kinematic_chains") or 0))
        + 5.0 * float(has_firmware_lineage or not int(profile.get("firmware_components") or 0))
        + 5.0 * float(has_ros_lineage or not int(profile.get("ros_interfaces") or 0)),
        1,
    )
    verdict = "native" if score >= 80 else "partial" if score >= 45 else "generic_only"

    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": benchmark.get("benchmark_id"),
        "robot_genre": benchmark.get("robot_genre"),
        "reference_project": benchmark.get("reference_project"),
        "expected_archetype": expected_archetype,
        "detected_archetype": detected_archetype,
        "archetype_match": archetype_match,
        "planning_confidence": plan.get("planning_confidence"),
        "pressure_index": _pressure_index(profile),
        "stack_coverage_score": score,
        "verdict": verdict,
        "required_domains": sorted(required_domains),
        "represented_domains": sorted(represented_domains),
        "domain_coverage": round(domain_coverage, 3),
        "required_actuators": required_actuators,
        "represented_actuators": represented_actuators,
        "actuator_coverage": round(actuator_coverage, 3),
        "source_governed": source_governed,
        "kinematic_identity": has_kinematic_identity,
        "firmware_lineage": has_firmware_lineage,
        "ros_lineage": has_ros_lineage,
        "dynamic_validation": has_dynamic_validation,
        "gaps": sorted(set(gaps)),
        "missing_info": list(plan.get("missing_info") or []),
    }


def evaluate_robotics_suite(
    benchmarks: Iterable[Mapping[str, Any]],
    *,
    planner: Callable[..., Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    rows = [evaluate_robotics_benchmark(row, planner=planner) for row in benchmarks]
    rows.sort(key=lambda row: (float(row["pressure_index"]), str(row["benchmark_id"])))
    return {
        "schema_version": SUITE_SCHEMA_VERSION,
        "benchmark_count": len(rows),
        "native_count": sum(row["verdict"] == "native" for row in rows),
        "partial_count": sum(row["verdict"] == "partial" for row in rows),
        "generic_only_count": sum(row["verdict"] == "generic_only" for row in rows),
        "rows": rows,
    }
