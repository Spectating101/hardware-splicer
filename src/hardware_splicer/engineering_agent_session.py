"""Model-independent MCP/SDK action boundary for an engineering LLM.

A connected model (ChatGPT/Claude/etc.) chooses the next operation and supplies
architectural hypotheses. This service validates actions, maintains a bounded
session ledger, and never delegates physical authority or shell execution.
No API key or on-host model runtime is needed for this interface.

The returned JSON state is a transport convenience, NOT a tamper-proof server
audit log. Data within it remains externally proposed and untrusted. Durable
proof requires independently persisted tool and instrument records.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import copy
import hashlib
import json

from .engineering_agent_trial import (
    TOOLS,digest,independent_design_audit,inspect_donors,inspect_requirements,
    validate_case,
)

SCHEMA="hardware_splicer.model_independent_engineering_session.v1"
MAX_STEPS=10


def start_engineering_session(case:Mapping[str,Any])->dict[str,Any]:
    validate_case(case)
    safe=copy.deepcopy(dict(case))
    return {
        "schema_version":SCHEMA,
        "case":safe,
        "case_sha256":digest(safe),
        "stage":"ACTIVE",
        "rounds_remaining":MAX_STEPS,
        "actions":[],
        "latest_design":None,
        "latest_independent_audit":None,
        "last_tool_receipt":{
            "kind":"ENGINEERING_SESSION_START",
            "objective":safe["goal"],
            "potential_donor_count":len(safe["donors"]),
            "allowed_actions":list(TOOLS),
            "next_action_comes_from_connected_llm":True,
            "physical_authority":False,
        },
        "physical_actions_authorized":False,
        "device_observations_authenticated":False,
    }


def engineering_session_step(state:Mapping[str,Any], decision:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(state,Mapping) or state.get("schema_version")!=SCHEMA:
        raise ValueError("Not a valid HS model-independent session state")
    if state.get("stage")!="ACTIVE":
        raise ValueError("Session is not active")
    case=state.get("case")
    validate_case(case)
    if state.get("case_sha256")!=digest(case):
        raise ValueError("Source case mutation in session state")
    if not isinstance(decision,Mapping):
        raise ValueError("Connected-model decision must be an object")
    action=decision.get("action")
    if action not in TOOLS:
        raise ValueError("Unsupported tool action; no model commands may be executed")
    remaining=state.get("rounds_remaining")
    if not isinstance(remaining,int) or remaining<1 or remaining>MAX_STEPS:
        raise ValueError("Session budget invalid")
    out=copy.deepcopy(dict(state))
    reason=str(decision.get("reason") or "")[:1000]
    design=out["latest_design"]
    # Do not trust a supplied prior PASS status from the model-controlled
    # state blob: recompute from canonical case and candidate every step.
    audit=(independent_design_audit(case,design) if design is not None else None)

    if action=="inspect_donors":
        receipt=inspect_donors(case)
    elif action=="inspect_requirements":
        receipt=inspect_requirements(case)
    elif action=="evaluate_design":
        design=copy.deepcopy(decision.get("design"))
        audit=independent_design_audit(case,design)
        receipt={
            "tool":"evaluate_design",
            "independent_design_audit":audit,
            "candidate_has_measured_physical_donors":False,
        }
    elif action=="prepare_concept_cad":
        declared=case.get("concept_envelope_mm")
        if not isinstance(declared,Mapping):
            receipt={"tool":action,"status":"BLOCKED",
                     "reason":"No separately declared geometric concept envelope in source case"}
        elif not audit or not audit.get("passes_bounded_evidence_and_structure"):
            receipt={"tool":action,"status":"BLOCKED",
                     "reason":"Architecture does not pass independent conditional evidence audit"}
        else:
            # A connected LLM can ask to develop CAD, but cannot silently
            # fabricate exact geometry from an unowned specimen.
            from .solidcraft_workspace_bridge import build_solidcraft_workspace_handoff
            goal=case["goal"]
            intent={
                "goal":goal,"constraints":case.get("constraints") or {},
                "concept_envelope_mm":dict(declared),
            }
            # Source the function description from the accepted model, NOT a
            # canned rover classifier. Only a conceptual bounding volume.
            functional={
                "functional_domain":str(design.get("machine_domain") or "UNRESOLVED"),
                "functional_decomposition_supported":True,
                "functions_are_conditional_from_llm":True,
            }
            candidate=build_solidcraft_workspace_handoff(intent,functional)
            receipt={"tool":action,"status":"CONDITIONAL_CAD_PLAN" if candidate["script_ready"] else "BLOCKED",
                     "cad_handoff":candidate,
                     "native_cad_binary_executed":False}
    else:
        receipt={
            "tool":"finish",
            "bounded_conditional_architecture_ready":bool(
                audit and audit["passes_bounded_evidence_and_structure"]
            ),
            "actual_electrical_mechanical_feasibility_validated":False,
            "physical_product_built":False,
        }
        out["stage"]="FINISHED"

    out["latest_design"]=design
    out["latest_independent_audit"]=audit
    out["last_tool_receipt"]=receipt
    out["rounds_remaining"]=remaining-1
    out["actions"].append({
        "step":len(out["actions"])+1,
        "action":action,
        "model_reason":reason,
        "evidence_receipt_sha256":digest(receipt),
        "model_supplied_design":action=="evaluate_design",
        "physical_authority_granted":False,
    })
    if out["rounds_remaining"]==0 and out["stage"]=="ACTIVE":
        out["stage"]="BUDGET_EXHAUSTED"
    out["physical_actions_authorized"]=False
    out["device_observations_authenticated"]=False
    return out
