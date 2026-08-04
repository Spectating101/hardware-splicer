"""Reference-corpus end-to-end validation for Hardware Splicer robotics.

This runner uses public references as declared or observed inputs, adds one pinned
fixture URDF plus firmware/ROS manifests, and executes the complete guided planner.
It validates product delivery and fail-closed authority; it does not claim that the
fixture artifacts or public references physically verify a robot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from .engineering_action import prepare_engineering_action
from .engineering_status import build_engineering_status
from .guided_engineering_planner import plan_guided_engineering_project


ROBOT_REFERENCE_E2E_SCHEMA = "hardware_splicer.robot_reference_e2e_report.v1"
_SOURCE_TYPE_MAP = {
    "repository": "repository",
    "documentation": "manual",
    "assembly_manual": "manual",
    "cad_index": "cad",
    "research_paper": "paper",
    "video": "video",
    "video_index": "video",
}


def load_json(path: str | Path) -> Dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def flatten_catalog(catalog: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for family in catalog.get("families") or []:
        if not isinstance(family, Mapping):
            continue
        family_id = str(family.get("family_id") or "")
        genre = str(family.get("genre") or "")
        for source in family.get("sources") or []:
            if not isinstance(source, Mapping):
                continue
            source_id = str(source.get("source_id") or "")
            if not source_id:
                continue
            if source_id in result:
                raise ValueError(f"duplicate robot reference source_id: {source_id}")
            result[source_id] = {
                **dict(source),
                "family_id": family_id,
                "family_genre": genre,
            }
    return result


def selected_engineering_sources(
    catalog: Mapping[str, Any],
    case: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    by_id = flatten_catalog(catalog)
    selected: list[Dict[str, Any]] = []
    missing: list[str] = []
    retrieved_at = str(catalog.get("generated_at") or "2026-08-04T15:04:00+08:00")
    for source_id in case.get("selected_catalog_source_ids") or []:
        source = by_id.get(str(source_id))
        if source is None:
            missing.append(str(source_id))
            continue
        source_type = _SOURCE_TYPE_MAP.get(
            str(source.get("source_type") or ""),
            "other",
        )
        authority = str(source.get("authority_ceiling") or "declared")
        claims = []
        for index, claim in enumerate(source.get("claims") or []):
            claims.append(
                {
                    "subject_id": f"reference:{source.get('source_id')}",
                    "predicate": f"reference_claim_{index}",
                    "value": str(claim),
                    "authority": authority,
                    "evidence_locator": {
                        "uri": source.get("uri"),
                        "locator": source.get("locator"),
                        "claim_index": index,
                    },
                    "metadata": {
                        "evidence_use": source.get("evidence_use"),
                        "limitations": list(source.get("limitations") or []),
                    },
                }
            )
        selected.append(
            {
                "source_id": source["source_id"],
                "source_type": source_type,
                "uri": source.get("uri"),
                "revision": f"retrieved-{retrieved_at}",
                "retrieved_at": retrieved_at,
                "authority_ceiling": authority,
                "claims": claims,
                "metadata": {
                    "title": source.get("title"),
                    "family_id": source.get("family_id"),
                    "family_genre": source.get("family_genre"),
                    "original_source_type": source.get("source_type"),
                    "revision_policy": source.get("revision_policy"),
                    "evidence_use": source.get("evidence_use"),
                    "limitations": list(source.get("limitations") or []),
                },
            }
        )
    if missing:
        raise ValueError(f"case references unknown catalog sources: {missing}")
    selected.extend(
        dict(row)
        for row in case.get("inline_engineering_sources") or []
        if isinstance(row, Mapping)
    )
    return selected


def _rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _check(name: str, passed: bool, observed: Any, expected: Any) -> Dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
    }


def run_robot_reference_e2e(
    catalog: Mapping[str, Any],
    case: Mapping[str, Any],
) -> Dict[str, Any]:
    sources = selected_engineering_sources(catalog, case)
    plan = plan_guided_engineering_project(
        case.get("intake") or {},
        engineering_sources=sources,
        skip_vision=True,
    )
    status = build_engineering_status(plan)
    prepared = prepare_engineering_action(
        plan,
        action_id=status.next_action_id,
    )

    families = [
        row for row in catalog.get("families") or []
        if isinstance(row, Mapping)
    ]
    catalog_sources = flatten_catalog(catalog)
    graph = dict(plan.get("engineering_source_graph") or {})
    topology = dict(plan.get("robot_topology") or {})
    closure = dict(plan.get("manufacturing_closure") or {})
    analysis = dict(plan.get("engineering_analysis") or {})
    execution = dict(plan.get("engineering_execution_plan") or {})
    guide = dict(plan.get("operator_guide") or {})
    readiness = dict(plan.get("engineering_readiness") or {})
    source_adapter = dict(plan.get("source_adapter") or {})

    operator_steps = _rows(guide.get("steps"))
    if not operator_steps:
        operator_steps = _rows(plan.get("ordered_steps"))
    selected_video_count = sum(
        1
        for row in sources
        if str(row.get("source_type") or "") == "video"
    )
    selected_source_types = sorted(
        {str(row.get("source_type") or "other") for row in sources}
    )
    physical_flags = {
        key: bool(readiness.get(key) or prepared.metadata.get(key))
        for key in (
            "fabrication_authorized",
            "flash_authorized",
            "power_on_authorized",
            "motion_authorized",
            "release_authorized",
        )
    }
    candidate_delivered = bool(
        readiness.get("candidate_machine_synthesized")
        or readiness.get("structured_robot_model_selected")
        or source_adapter.get("selected_robot_model_source_id")
    )

    expected = dict(case.get("expected") or {})
    checks = [
        _check(
            "catalog-source-count",
            len(catalog_sources) >= int(expected.get("minimum_catalog_sources") or 0),
            len(catalog_sources),
            f">={expected.get('minimum_catalog_sources')}",
        ),
        _check(
            "catalog-family-count",
            len(families) >= int(expected.get("minimum_catalog_families") or 0),
            len(families),
            f">={expected.get('minimum_catalog_families')}",
        ),
        _check(
            "selected-source-count",
            len(sources) >= int(expected.get("minimum_selected_sources") or 0),
            len(sources),
            f">={expected.get('minimum_selected_sources')}",
        ),
        _check(
            "video-is-one-source-type",
            selected_video_count > 0 and len(selected_source_types) > 3,
            {
                "video_count": selected_video_count,
                "source_types": selected_source_types,
            },
            "video present alongside repository/manual/CAD/firmware/middleware sources",
        ),
        _check(
            "source-graph-retention",
            len(graph.get("sources") or []) == len(sources),
            len(graph.get("sources") or []),
            len(sources),
        ),
        _check(
            "native-robot-genre",
            topology.get("robot_genre") == expected.get("robot_genre")
            and plan.get("native_robot_genre") == expected.get("robot_genre"),
            {
                "topology": topology.get("robot_genre"),
                "plan": plan.get("native_robot_genre"),
            },
            expected.get("robot_genre"),
        ),
        _check(
            "topology-joint-count",
            len(topology.get("joints") or []) >= int(expected.get("minimum_joints") or 0),
            len(topology.get("joints") or []),
            f">={expected.get('minimum_joints')}",
        ),
        _check(
            "candidate-delivered",
            candidate_delivered is bool(expected.get("candidate_synthesized")),
            {
                "candidate_machine_synthesized": bool(readiness.get("candidate_machine_synthesized")),
                "structured_robot_model_selected": bool(readiness.get("structured_robot_model_selected")),
                "selected_robot_model_source_id": source_adapter.get("selected_robot_model_source_id"),
            },
            bool(expected.get("candidate_synthesized")),
        ),
        _check(
            "manufacturing-closure-present",
            bool(closure) is bool(expected.get("manufacturing_closure_present")),
            bool(closure),
            bool(expected.get("manufacturing_closure_present")),
        ),
        _check(
            "execution-plan-present",
            bool(execution) is bool(expected.get("execution_plan_present")),
            bool(execution),
            bool(expected.get("execution_plan_present")),
        ),
        _check(
            "operator-guide-depth",
            len(operator_steps) >= int(expected.get("minimum_operator_steps") or 0),
            len(operator_steps),
            f">={expected.get('minimum_operator_steps')}",
        ),
        _check(
            "ranked-action-prepared",
            bool(prepared.action.action_id) and bool(prepared.payload),
            {
                "action_id": prepared.action.action_id,
                "category": prepared.action.category,
                "prepared_status": prepared.status,
            },
            "one concrete next-action packet",
        ),
        _check(
            "physical-authority-fail-closed",
            not any(physical_flags.values()),
            physical_flags,
            "all false",
        ),
    ]
    passed = all(row["passed"] for row in checks)

    return {
        "schema_version": ROBOT_REFERENCE_E2E_SCHEMA,
        "scenario_id": case.get("scenario_id"),
        "passed": passed,
        "catalog": {
            "family_count": len(families),
            "source_count": len(catalog_sources),
            "genres": sorted({str(row.get("genre") or "") for row in families}),
        },
        "selected_evidence": {
            "source_count": len(sources),
            "video_source_count": selected_video_count,
            "source_types": selected_source_types,
            "source_ids": [row.get("source_id") for row in sources],
        },
        "plan_summary": {
            "archetype": plan.get("archetype"),
            "native_robot_genre": plan.get("native_robot_genre"),
            "source_graph_source_count": len(graph.get("sources") or []),
            "source_graph_claim_count": len(graph.get("claims") or []),
            "source_graph_conflict_count": len(graph.get("conflicts") or []),
            "topology_link_count": len(topology.get("links") or []),
            "topology_joint_count": len(topology.get("joints") or []),
            "topology_actuator_count": len(topology.get("actuators") or []),
            "analysis_finding_count": len(analysis.get("findings") or []),
            "analysis_blocking_count": len(
                [
                    row
                    for row in _rows(analysis.get("findings"))
                    if row.get("blocking")
                ]
            ),
            "manufacturing_closure_status": closure.get("status"),
            "manufacturing_blocker_count": len(
                [
                    row
                    for row in _rows(closure.get("checks"))
                    if row.get("blocking")
                    and str(row.get("status") or "") in {"fail", "unknown"}
                ]
            ),
            "execution_check_count": len(execution.get("checks") or []),
            "execution_unresolved_count": len(execution.get("unresolved") or []),
            "operator_guide_step_count": len(operator_steps),
            "engineering_status": status.overall_status,
            "engineering_phase": status.current_phase,
            "blocker_count": len(status.blockers),
            "advisory_count": len(status.advisories),
            "next_action_id": status.next_action_id,
        },
        "prepared_action": prepared.model_dump(mode="json"),
        "physical_authority": physical_flags,
        "checks": checks,
        "limitations": [
            "Public references are declared or observed evidence, not physical verification.",
            "Fixture URDF, firmware hashes, wiring hashes and CAD hashes exercise identity continuity but are not fabricated artifacts.",
            "Remote repositories and documents are not materialized into the bounded execution workspace by this run.",
            "No flashing, power-on, motion, fabrication or release operation is performed.",
        ],
        "plan": plan,
    }
