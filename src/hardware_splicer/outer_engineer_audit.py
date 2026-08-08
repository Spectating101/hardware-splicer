"""Outer System Engineer audit over model-first Hardware Splicer outputs.

This combines two independent deterministic questions without asking another model to
vote on correctness:

1. constitution: did legacy semantic authority or physical authority become effective?
2. identity closure: did unresolved physical identity quietly turn into concrete module
   identity in graph/firmware/bring-up/mechanical/procurement artifacts?

Proposal quality remains outside this audit and belongs to model/evidence/tool evaluation.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .identity_propagation_audit import audit_identity_propagation
from .model_first_truth_audit import audit_model_first_truth


SCHEMA_VERSION = "hardware_splicer.outer_engineer_audit.v1"


def audit_outer_engineer_run(
    *,
    project_plan: Mapping[str, Any] | None = None,
    circuit_candidate: Any = None,
    salvage_package: Mapping[str, Any] | None = None,
    robot_topology: Mapping[str, Any] | None = None,
    change_impact: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    constitution = audit_model_first_truth(
        project_plan=project_plan,
        circuit_candidate=circuit_candidate,
        salvage_package=salvage_package,
        robot_topology=robot_topology,
        change_impact=change_impact,
    )
    identity_closure = (
        audit_identity_propagation(dict(salvage_package or {}))
        if salvage_package
        else {
            "schema_version": "hardware_splicer.identity_propagation_audit.v1",
            "status": "not_run",
            "finding_count": 0,
            "blocking_finding_count": 0,
            "review_finding_count": 0,
            "findings": [],
            "authority_effect": "none",
        }
    )

    blocking = (
        constitution.get("status") == "blocked"
        or identity_closure.get("status") == "blocked"
    )
    review = (
        not blocking
        and identity_closure.get("status") == "review"
    )
    status = "blocked" if blocking else "review" if review else "pass"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "constitution": constitution,
        "identity_closure": identity_closure,
        "blocking_finding_count": int(constitution.get("blocking_violation_count") or 0)
        + int(identity_closure.get("blocking_finding_count") or 0),
        "review_finding_count": int(identity_closure.get("review_finding_count") or 0),
        "diagnostic_contract": {
            "proposal_correctness_judged": False,
            "model_reasoning_judged": False,
            "legacy_semantic_authority_checked": True,
            "physical_authority_checked": True,
            "physical_identity_provenance_checked": bool(salvage_package),
            "downstream_identity_closure_checked": bool(salvage_package),
        },
        "recommended_outer_action": (
            "classify and repair contract/system leakage before evaluating model reasoning"
            if blocking
            else "review proposed/unbound downstream design identities before claiming physical truth"
            if review
            else "continue to proposal-quality, deterministic-tool, and physical-evidence evaluation"
        ),
        "authority_effect": "none",
    }
