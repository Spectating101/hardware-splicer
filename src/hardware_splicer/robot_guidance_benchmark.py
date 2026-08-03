"""Measure whether Hardware Splicer can guide a real robot build or modification.

This benchmark evaluates the current project-intake output against concrete guidance
obligations. Public repositories, documentation, and videos are reference evidence;
they never become verified build truth without identity mapping and physical checks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

SCHEMA_VERSION = "hardware_splicer.robot_guidance_benchmark.v1"
SUITE_SCHEMA_VERSION = "hardware_splicer.robot_guidance_suite.v1"

_DIMENSION_WEIGHTS: dict[str, float] = {
    "requirements": 10.0,
    "reference_provenance": 8.0,
    "variant_selection": 8.0,
    "bom_and_tools": 10.0,
    "mechanical_guidance": 9.0,
    "electrical_power_guidance": 9.0,
    "firmware_lineage": 9.0,
    "control_middleware": 8.0,
    "modification_impact": 9.0,
    "ordered_procedure": 8.0,
    "verification_gates": 8.0,
    "rollback_repair": 4.0,
}


def load_robot_guidance_scenario(path: str | Path) -> Dict[str, Any]:
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"robot guidance scenario must be an object: {source}")
    required = {
        "scenario_id",
        "mode",
        "reference_project",
        "expected_archetype",
        "intake",
        "guidance_expectations",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"robot guidance scenario {source} missing: {', '.join(missing)}")
    mode = str(payload.get("mode") or "").strip().lower()
    if mode not in {"build", "modify", "repair"}:
        raise ValueError(f"unsupported robot guidance mode: {mode}")
    payload.setdefault("source_file", str(source.resolve()))
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


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


def _has_ordered_steps(payload: Any) -> bool:
    step_keys = {
        "assembly_steps",
        "build_steps",
        "ordered_steps",
        "procedure",
        "procedures",
        "bringup_steps",
        "calibration_steps",
        "installation_steps",
    }
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if str(key).strip().lower() in step_keys and len(_sequence(value)) >= 2:
                return True
            if _has_ordered_steps(value):
                return True
    elif isinstance(payload, (list, tuple)):
        return any(_has_ordered_steps(value) for value in payload)
    return False


def _source_governance(plan: Mapping[str, Any]) -> bool:
    """Require timestamped observations plus canonical target identity.

    Retaining a repository or video URL alone is not governed evidence.
    """

    return (
        _contains_key(plan, {"timestamp_start", "timestamp_end", "time_range"})
        and _contains_key(plan, {"canonical_target_id", "component_id", "joint_id", "interface_id"})
        and _contains_key(plan, {"authority", "authority_ceiling", "evidence_authority"})
    )


def _bom_quality(plan: Mapping[str, Any], expectations: Mapping[str, Any]) -> tuple[bool, list[str]]:
    normalized = _sequence(plan.get("normalized_parts"))
    minimum = int(expectations.get("minimum_part_lines") or 1)
    gaps: list[str] = []
    if len(normalized) < minimum:
        gaps.append("part_inventory_incomplete")
    quantities = [row.get("quantity") for row in normalized if isinstance(row, Mapping)]
    if normalized and not any(value not in (None, "") for value in quantities):
        gaps.append("part_quantities_missing")
    if expectations.get("tools_required") and not _contains_key(plan, {"tool", "tools", "equipment"}):
        gaps.append("tooling_plan_missing")
    return not gaps, gaps


def evaluate_robot_guidance_scenario(
    scenario: Mapping[str, Any],
    *,
    planner: Callable[..., Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Evaluate one user-specific robot build or modification request."""

    if planner is None:
        from .project_intake import plan_project_from_intake

        planner = plan_project_from_intake

    intake = _mapping(scenario.get("intake"))
    plan = dict(planner(intake, skip_vision=True))
    scenario_plan = _mapping(plan.get("scenario"))
    spec = _mapping(scenario_plan.get("compile_spec"))
    expectations = _mapping(scenario.get("guidance_expectations"))
    mode = str(scenario.get("mode") or "build").strip().lower()
    expected_archetype = str(scenario.get("expected_archetype") or "")
    detected_archetype = str(plan.get("archetype") or "")

    dimensions: dict[str, dict[str, Any]] = {}
    gaps: list[str] = []

    requirements_ok = bool(plan.get("goal")) and bool(intake.get("constraints"))
    if not requirements_ok:
        gaps.append("requirements_not_structured")
    dimensions["requirements"] = {
        "satisfied": requirements_ok,
        "evidence": ["goal", "constraints"] if requirements_ok else [],
    }

    provenance_ok = _source_governance(plan)
    if not provenance_ok:
        gaps.append("reference_sources_not_governed")
    dimensions["reference_provenance"] = {
        "satisfied": provenance_ok,
        "evidence": ["timestamped identity-resolved observation"] if provenance_ok else [],
    }

    variant_ok = detected_archetype == expected_archetype and bool(
        plan.get("recommended_build_id") or spec.get("robotics_project")
    )
    if not variant_ok:
        gaps.append("robot_variant_not_resolved")
    dimensions["variant_selection"] = {
        "satisfied": variant_ok,
        "evidence": [detected_archetype] if variant_ok else [],
    }

    bom_ok, bom_gaps = _bom_quality(plan, expectations)
    gaps.extend(bom_gaps)
    dimensions["bom_and_tools"] = {
        "satisfied": bom_ok,
        "evidence": [f"{len(_sequence(plan.get('normalized_parts')))} normalized part lines"] if bom_ok else [],
    }

    mechanical_ok = _contains_key(
        spec,
        {"mechanism", "dimensions", "clearance", "mount", "link", "joint_axis", "coordinate_frame"},
    )
    if expectations.get("custom_mechanics") and not _contains_key(
        spec, {"custom_mount", "mount_delta", "center_of_mass", "collision_geometry", "payload_inertia"}
    ):
        mechanical_ok = False
        gaps.append("custom_mechanical_impact_missing")
    if not mechanical_ok:
        gaps.append("mechanical_build_guidance_missing")
    dimensions["mechanical_guidance"] = {
        "satisfied": mechanical_ok,
        "evidence": ["mechanical compile specification"] if mechanical_ok else [],
    }

    electrical_ok = _contains_key(
        spec,
        {"electrical", "electronics", "circuit", "power_budget", "current_limit", "voltage"},
    )
    if not electrical_ok:
        gaps.append("electrical_power_guidance_missing")
    dimensions["electrical_power_guidance"] = {
        "satisfied": electrical_ok,
        "evidence": ["electrical or power specification"] if electrical_ok else [],
    }

    firmware_ok = _contains_key(
        spec,
        {
            "firmware_revision",
            "source_revision",
            "toolchain",
            "dependency_lock",
            "build_command",
            "binary_hash",
            "flash_command",
            "flash_result",
            "pin_map_hash",
        },
    )
    if expectations.get("firmware_required") and not firmware_ok:
        gaps.append("firmware_build_flash_lineage_missing")
    dimensions["firmware_lineage"] = {
        "satisfied": firmware_ok or not bool(expectations.get("firmware_required")),
        "evidence": ["versioned build/flash lineage"] if firmware_ok else [],
    }

    middleware_ok = _contains_key(
        spec,
        {
            "ros_topic",
            "ros_service",
            "ros_interface",
            "urdf",
            "moveit",
            "nav2",
            "micro_ros",
            "middleware_contract",
            "control_loop",
        },
    )
    if expectations.get("middleware_required") and not middleware_ok:
        gaps.append("control_middleware_lineage_missing")
    dimensions["control_middleware"] = {
        "satisfied": middleware_ok or not bool(expectations.get("middleware_required")),
        "evidence": ["control or middleware contract"] if middleware_ok else [],
    }

    modification_ok = True
    if mode in {"modify", "repair"}:
        modification_ok = _contains_key(
            plan,
            {
                "baseline_revision",
                "change_request",
                "affected_subsystems",
                "compatibility_impact",
                "modification_delta",
                "repair_delta",
                "replacement_mapping",
            },
        )
        if not modification_ok:
            gaps.append("modification_impact_analysis_missing")
    dimensions["modification_impact"] = {
        "satisfied": modification_ok,
        "evidence": ["explicit baseline-to-candidate delta"] if modification_ok and mode != "build" else [],
    }

    procedure_ok = _has_ordered_steps(plan)
    if not procedure_ok:
        gaps.append("ordered_build_procedure_missing")
    dimensions["ordered_procedure"] = {
        "satisfied": procedure_ok,
        "evidence": ["ordered assembly/bring-up steps"] if procedure_ok else [],
    }

    verification_ok = bool(plan.get("missing_info") is not None) and _contains_key(
        scenario_plan,
        {"acceptance", "safety", "verification", "evidence", "blocker"},
    )
    if not verification_ok:
        gaps.append("verification_gate_plan_missing")
    dimensions["verification_gates"] = {
        "satisfied": verification_ok,
        "evidence": ["acceptance and evidence gates"] if verification_ok else [],
    }

    rollback_ok = _contains_key(
        plan,
        {"rollback", "recovery", "safe_state", "replacement", "repair", "revert", "power_off"},
    )
    if not rollback_ok:
        gaps.append("rollback_repair_guidance_missing")
    dimensions["rollback_repair"] = {
        "satisfied": rollback_ok,
        "evidence": ["rollback or repair path"] if rollback_ok else [],
    }

    score = round(
        sum(
            _DIMENSION_WEIGHTS[name]
            for name, result in dimensions.items()
            if bool(result.get("satisfied"))
        ),
        1,
    )
    if score >= 85 and not gaps:
        verdict = "guided_build_ready"
    elif score >= 60:
        verdict = "useful_with_expert_fill"
    elif score >= 35:
        verdict = "planning_assistant_only"
    else:
        verdict = "reference_triage_only"

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": scenario.get("scenario_id"),
        "mode": mode,
        "reference_project": scenario.get("reference_project"),
        "user_need": scenario.get("user_need"),
        "expected_archetype": expected_archetype,
        "detected_archetype": detected_archetype,
        "planning_confidence": plan.get("planning_confidence"),
        "guidance_score": score,
        "verdict": verdict,
        "dimensions": dimensions,
        "gaps": sorted(set(gaps)),
        "missing_info": list(plan.get("missing_info") or []),
    }


def evaluate_robot_guidance_suite(
    scenarios: Iterable[Mapping[str, Any]],
    *,
    planner: Callable[..., Mapping[str, Any]] | None = None,
) -> Dict[str, Any]:
    rows = [evaluate_robot_guidance_scenario(row, planner=planner) for row in scenarios]
    rows.sort(key=lambda row: str(row.get("scenario_id") or ""))
    return {
        "schema_version": SUITE_SCHEMA_VERSION,
        "scenario_count": len(rows),
        "guided_build_ready_count": sum(row["verdict"] == "guided_build_ready" for row in rows),
        "useful_with_expert_fill_count": sum(row["verdict"] == "useful_with_expert_fill" for row in rows),
        "planning_assistant_only_count": sum(row["verdict"] == "planning_assistant_only" for row in rows),
        "reference_triage_only_count": sum(row["verdict"] == "reference_triage_only" for row in rows),
        "rows": rows,
    }
