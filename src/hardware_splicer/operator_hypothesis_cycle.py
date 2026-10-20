"""Two-stage advisory hypothesis evaluation over independent HS findings."""
from __future__ import annotations

import json
from typing import Callable, Mapping, Any

from .engineering_analysis import analyze_engineering_candidate
from .engineering_source_graph import build_engineering_source_graph
from .robot_topology import build_robot_topology

Operator = Callable[[str], Mapping[str, Any]]


def _validate(response: Mapping[str, Any]) -> list[dict[str, str]]:
    items = response.get("hypotheses")
    if response.get("measurements_claimed") is not False or not isinstance(items, list) or not 2 <= len(items) <= 5:
        raise ValueError("invalid hypothesis packet")
    checked = []
    ids = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("invalid hypothesis")
        keys = ("id", "explanation", "discriminating_test", "predicted_observation")
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in keys):
            raise ValueError("incomplete hypothesis")
        if item["id"] in ids:
            raise ValueError("duplicate hypothesis")
        ids.add(item["id"])
        checked.append({k: item[k] for k in keys})
    return checked


def investigate_hypotheses(case: Mapping[str, Any], *, operator: Operator) -> dict[str, Any]:
    """Propose explanations, inspect immutable HS blockers, request a revision."""
    intake = dict(case.get("intake") or case)
    analysis = analyze_engineering_candidate(intake, topology=build_robot_topology(intake))
    graph = build_engineering_source_graph(
        case.get("engineering_sources", intake.get("engineering_sources", [])),
        declared_conflicts=case.get("declared_conflicts", intake.get("declared_conflicts", [])),
    )
    blockers = [r.finding_id for r in analysis.findings if r.blocking]
    conflicts = [r.conflict_id for r in graph.conflicts if r.blocking]
    packet = {"goal": intake.get("goal"), "constraints": intake.get("constraints", {}),
              "components": intake.get("available_parts", []),
              "claims": [{"source": c.source_id, "value": c.value} for c in graph.claims],
              "findings": [{"id": f.finding_id, "status": f.status.value, "missing": f.missing_inputs}
                           for f in analysis.findings]}
    schema = ('Return ONLY JSON: {"hypotheses":[{"id":"h1","explanation":"...",'
              '"discriminating_test":"...","predicted_observation":"..."}],'
              '"measurements_claimed":false}. Provide 2-5 distinct hypotheses.')
    initial = []
    revision = []
    status = "incomplete"
    try:
        initial = _validate(dict(operator(
            "Advisory reasoning only; no actual tests, measurements or approval. "
            + schema + "\nCASE: " + json.dumps(packet, default=str)
        )))
        critique = {"blocking_findings": blockers, "blocking_conflicts": conflicts,
                    "initial_hypotheses": initial,
                    "note": "These are untested hypotheses; do not promote predictions to measurements."}
        revision = _validate(dict(operator(
            "Revise competing explanations and their discriminating tests after HS critique. "
            + schema + "\nCRITIQUE: " + json.dumps(critique, default=str)
        )))
        status = "reviewed"
    except (ValueError, TypeError, RuntimeError, TimeoutError):
        status = "operator_error"
    return {"schema_version": "hardware_splicer.operator_hypothesis_cycle.v1",
            "status": status, "initial": initial, "revised": revision,
            "blocking_findings": blockers, "blocking_conflicts": conflicts,
            "tests_executed": 0, "decision": "hold",
            "physical_authority": "not_authorized", "ready_for_physical_execution": False}
