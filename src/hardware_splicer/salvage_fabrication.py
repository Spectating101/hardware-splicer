"""Mission-scoped control projection for the salvage fabrication agent loop.

This module owns no mission, donor, evidence, artifact, lab or authority state. It
projects the existing canonical stores into one bounded context that an agent can
reload on every turn instead of reconstructing state from chat.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .fabrication_operator import FabricationValidationError
from .mission_donors import read_donors
from .mission_store import MissionStore
from .salvage_resource_graph import project_salvage_resource_graph

_SCHEMA = "hardware_splicer.salvage_fabrication_context.v1"


def build_salvage_fabrication_context(
    *,
    mission_store: MissionStore,
    project_id: str,
    mission_id: str,
    fabrication_resources: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return a stable, read-only context for one salvage mission.

    Accepted missions use their frozen ``donor_read`` projection. Before
    acceptance, the context may show a current project donor projection, clearly
    marked as pre-acceptance and therefore not frozen into the mission yet.
    """
    if not isinstance(mission_store, MissionStore):
        raise FabricationValidationError("salvage fabrication requires a mission store")
    mission = mission_store.get_mission(project_id, mission_id)
    accepted = mission.get("accepted") is not None
    if accepted:
        donors = list(mission.get("donors") or [])
        donor_snapshot = "mission_frozen_donor_read"
        donor_snapshot_frozen = True
    else:
        references = mission.get("intake", {}).get("donors") or []
        try:
            donors = read_donors(mission_store.project_store, project_id, references)
        except (TypeError, ValueError, KeyError) as exc:
            raise FabricationValidationError(str(exc)) from exc
        donor_snapshot = "current_project_projection_pre_acceptance"
        donor_snapshot_frozen = False

    graph = project_salvage_resource_graph(
        project_id=project_id,
        donors=donors,
        fabrication_resources=fabrication_resources,
    )
    candidates = [_candidate_summary(row) for row in mission.get("candidates") or []]
    needs = [_need_summary(row) for row in mission.get("needs") or []]
    hypotheses = _hypotheses(donors)
    next_state = _next_state(mission, candidates, needs)
    context = {
        "schema": _SCHEMA,
        "project_id": mission["project_id"],
        "mission_id": mission["mission_id"],
        "project_revision": mission["revision"],
        "last_event_seq": mission["last_event_seq"],
        "phase": mission["phase"],
        "accepted": accepted,
        "terminal": mission.get("terminal"),
        "staged": mission.get("staged"),
        "goal": mission.get("intake", {}).get("goal"),
        "constraints": list(mission.get("intake", {}).get("constraints") or []),
        "budgets": dict(mission.get("budgets") or {}),
        "resource_graph": graph,
        "donor_snapshot": donor_snapshot,
        "donor_snapshot_frozen": donor_snapshot_frozen,
        "hypotheses": hypotheses,
        "candidates": candidates,
        "needs": needs,
        "next_state": next_state,
        "truth_contract": {
            "projection_only": True,
            "persists_independent_truth": False,
            "mission_truth_owner": "mission_store_event_replay",
            "donor_truth_owner": "mission_frozen_donor_read_after_acceptance",
            "hypotheses_promote_physical_truth": False,
            "resource_availability_grants_physical_authority": False,
            "agent_can_accept_mission": False,
            "agent_can_supply_human_measurement": False,
            "agent_can_approve_physical_actuation": False,
        },
    }
    context["context_sha256"] = _digest(context)
    return context


def _candidate_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise FabricationValidationError("mission candidate must be an object")
    evaluations = row.get("evaluations") or []
    latest = evaluations[-1] if isinstance(evaluations, list) and evaluations else None
    return {
        "candidate_id": row.get("id"),
        "kind": row.get("kind"),
        "label": row.get("label"),
        "repairs": row.get("repairs"),
        "covers_inventory": row.get("covers_inventory"),
        "uncovered_inventory": list(row.get("uncovered_inventory") or []),
        "violated_requirements": list(row.get("violated_requirements") or []),
        "latest_evaluation": (
            {
                "seq": latest.get("seq"),
                "operation": latest.get("operation"),
                "result": latest.get("result"),
                "artifact": latest.get("artifact"),
            }
            if isinstance(latest, Mapping)
            else None
        ),
    }


def _need_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise FabricationValidationError("mission evidence need must be an object")
    request = row.get("request") if isinstance(row.get("request"), Mapping) else None
    return {
        "need_seq": row.get("seq"),
        "state": row.get("need_state"),
        "blocker": row.get("blocker"),
        "candidate_id": row.get("candidate_id"),
        "need": row.get("need"),
        "request": dict(request) if request is not None else None,
        "requires_human_physical_evidence": request is not None,
    }


def _hypotheses(donors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for donor in donors:
        if not isinstance(donor, Mapping):
            continue
        for finding in donor.get("findings") or []:
            if not isinstance(finding, Mapping):
                continue
            artifacts = finding.get("artifacts") or []
            retained = [
                {"name": item.get("name"), "sha256": item.get("sha256")}
                for item in artifacts
                if isinstance(item, Mapping)
            ]
            values.append({
                "donor_id": donor.get("donor_id"),
                "finding_seq": finding.get("seq"),
                "signal": finding.get("signal"),
                "claim": finding.get("claim"),
                "method": finding.get("method"),
                "source": finding.get("source"),
                "grade": finding.get("grade"),
                "retained_artifacts": retained,
                "support_state": "retained_artifact_reference" if retained else "unsupported_hypothesis",
                "promotes_contract_truth": False,
                "physical_fact": False,
            })
    values.sort(key=lambda row: (str(row.get("donor_id")), int(row.get("finding_seq") or 0)))
    return values


def _next_state(
    mission: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    needs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    terminal = mission.get("terminal")
    if terminal is not None:
        return {
            "state": "terminal",
            "agent_may_mutate_mission": False,
            "recommended_intents": ["read_terminal", "build_or_read_package", "stage_if_ready"],
        }
    if mission.get("accepted") is None:
        return {
            "state": "awaiting_human_acceptance",
            "agent_may_mutate_mission": False,
            "recommended_intents": ["inspect_context", "await_human_acceptance"],
        }
    unresolved = [row for row in needs if row.get("state") != "resolved"]
    if unresolved:
        physical = any(row.get("requires_human_physical_evidence") for row in unresolved)
        return {
            "state": "evidence_required",
            "agent_may_mutate_mission": True,
            "recommended_intents": [
                "inspect_existing_hypotheses",
                "await_human_physical_evidence" if physical else "resolve_nonphysical_evidence_need",
                "propose_repair_after_new_fact",
            ],
        }
    if not candidates:
        return {
            "state": "architecture_required",
            "agent_may_mutate_mission": True,
            "recommended_intents": [
                "inspect_resources",
                "propose_findings_or_evidence_need",
                "propose_multiple_architectures",
                "compare_architecture_tradeoffs",
            ],
        }
    return {
        "state": "architecture_in_progress",
        "agent_may_mutate_mission": True,
        "recommended_intents": [
            "run_bounded_candidate_checks",
            "compare_architecture_tradeoffs",
            "request_missing_evidence",
            "propose_repair_or_terminal_state_when_grounded",
        ],
    }


def _digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
