"""Assess the delivery artifacts produced by a full Hardware Splicer robot run.

This complements the planning guidance benchmark. Generated artifacts improve operator
support, but scaffolds and checklists do not automatically satisfy authority-bearing
lineage or physical verification requirements.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from .robot_guidance_benchmark import evaluate_robot_guidance_scenario

SCHEMA_VERSION = "hardware_splicer.robot_guidance_delivery.v1"

_DELIVERY_WEIGHTS: dict[str, float] = {
    "compiled_design": 15.0,
    "mechanism_pack": 10.0,
    "firmware_scaffold": 10.0,
    "bringup_card": 15.0,
    "evidence_capture_kit": 15.0,
    "bench_session": 15.0,
    "project_package": 10.0,
    "production_metrics": 10.0,
}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _path_present(value: Any) -> bool:
    if isinstance(value, Path):
        return value.is_file() or value.is_dir()
    if isinstance(value, str) and value.strip():
        path = Path(value)
        return path.is_file() or path.is_dir()
    return False


def _present(value: Any) -> bool:
    if value in (None, "", {}, []):
        return False
    if isinstance(value, (str, Path)):
        return _path_present(value)
    return True


def assess_robot_guidance_delivery(
    scenario: Mapping[str, Any],
    run_result: Mapping[str, Any],
) -> Dict[str, Any]:
    """Combine plan coverage with the artifacts from an executed project intake."""

    result = dict(run_result)
    plan = _mapping(result.get("intake_plan"))
    if not plan:
        raise ValueError("run_result.intake_plan is required")

    planning = evaluate_robot_guidance_scenario(
        scenario,
        planner=lambda _intake, *, skip_vision: plan,
    )
    artifacts = _mapping(result.get("artifacts"))
    bench = _mapping(result.get("bench_session"))

    compiled_design = bool(
        result.get("compile_ok")
        or _mapping(result.get("build_compilation")).get("ok")
        or _path_present(artifacts.get("build_graph"))
        or _path_present(artifacts.get("kicad_pcb"))
    )
    mechanism_pack = _present(result.get("mechanism_pack")) or _path_present(
        artifacts.get("mechanism_pack")
    )
    firmware_scaffold = _present(result.get("firmware_scaffold")) or _path_present(
        artifacts.get("firmware_scaffold")
    )
    bringup_card = _present(result.get("bringup_card")) or _path_present(
        artifacts.get("bringup_card")
    ) or _path_present(artifacts.get("bringup_card_md"))
    evidence_capture_kit = _present(result.get("evidence_capture_kit")) or _path_present(
        artifacts.get("evidence_capture_kit")
    )
    bench_session = bool(bench) and (
        bench.get("readiness") is not None
        or bench.get("power_on_authorized") is not None
        or bool(bench.get("next_actions"))
    )
    project_package = _present(result.get("project_package")) or _path_present(
        artifacts.get("project_package")
    ) or _path_present(artifacts.get("project_package_json"))
    production_metrics = _present(result.get("production_release_metrics")) or _path_present(
        artifacts.get("production_release_metrics")
    )

    support = {
        "compiled_design": compiled_design,
        "mechanism_pack": mechanism_pack,
        "firmware_scaffold": firmware_scaffold,
        "bringup_card": bringup_card,
        "evidence_capture_kit": evidence_capture_kit,
        "bench_session": bench_session,
        "project_package": project_package,
        "production_metrics": production_metrics,
    }
    delivery_score = round(
        sum(weight for name, weight in _DELIVERY_WEIGHTS.items() if support[name]),
        1,
    )

    cautions: list[str] = []
    if firmware_scaffold and not planning["dimensions"]["firmware_lineage"]["satisfied"]:
        cautions.append("firmware_scaffold_is_not_build_flash_lineage")
    if mechanism_pack and not planning["dimensions"]["mechanical_guidance"]["satisfied"]:
        cautions.append("mechanism_pack_does_not_close_custom_mechanical_impact")
    if bringup_card and not planning["dimensions"]["ordered_procedure"]["satisfied"]:
        cautions.append("bringup_card_is_not_full_project_specific_assembly_procedure")
    if bench_session and not bool(bench.get("power_on_authorized")):
        cautions.append("bench_session_does_not_authorize_power_on")
    if project_package and planning.get("gaps"):
        cautions.append("project_package_retains_unclosed_guidance_gaps")

    if planning["verdict"] == "guided_build_ready" and delivery_score >= 85 and not cautions:
        verdict = "guided_build_package"
    elif delivery_score >= 70:
        verdict = "bounded_build_assistant"
    elif delivery_score >= 45:
        verdict = "engineering_planning_package"
    else:
        verdict = "reference_planning_only"

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": scenario.get("scenario_id"),
        "planning_guidance_score": planning.get("guidance_score"),
        "planning_verdict": planning.get("verdict"),
        "planning_gaps": list(planning.get("gaps") or []),
        "delivery_coverage_score": delivery_score,
        "delivery_support": support,
        "operator_guidance_verdict": verdict,
        "cautions": sorted(set(cautions)),
        "power_on_authorized": bool(bench.get("power_on_authorized")),
    }
