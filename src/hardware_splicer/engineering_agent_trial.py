"""LLM-directed hardware engineering investigation, with external safety oracle.

The MODEL makes each next-step decision and proposes a non-template machine.
Only enumerated, read-only or CAD-plan actions are available. The host does not
execute model-authored shell commands and never confuses assumptions with bench
measurements or design files with proven products.

This trial intentionally uses a replaceable JSON model boundary. Local Ollama
is the first tested backend. It is not a general-purpose autonomous computer
controller, physical investigator or power/fabrication authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

SCHEMA="hardware_splicer.engineering_agent_trial.v1"
TOOLS=("inspect_donors","inspect_requirements","evaluate_design","prepare_concept_cad","finish")
PHYSICAL_FALSE=("physical_verified","real_donor_measured","physical_build_authorized",
                "fabrication_approved","safe_to_power","physically_tested")


def digest(o:Any)->str:
    return hashlib.sha256(json.dumps(o,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class JsonPolicy(Protocol):
    def decide(self,messages:list[dict[str,str]])->dict[str,Any]: ...


@dataclass
class OllamaJsonPolicy:
    model:str="qwen2.5:7b-instruct"
    endpoint:str="http://127.0.0.1:11434/api/chat"
    timeout:int=150
    temperature:float=0.15
    max_tokens:int=900

    def decide(self,messages:list[dict[str,str]])->dict[str,Any]:
        if self.endpoint!="http://127.0.0.1:11434/api/chat":
            raise ValueError("Only explicit loopback Ollama endpoint is permitted")
        req=urllib.request.Request(
            self.endpoint,method="POST",
            headers={"Content-Type":"application/json"},
            data=json.dumps({
                "model":self.model,
                "stream":False,
                "format":"json",
                "keep_alive":"90s",
                "options":{
                    "temperature":self.temperature,"num_predict":self.max_tokens,
                    "num_ctx":1536,
                },
                "messages":messages,
            }).encode(),
        )
        with urllib.request.urlopen(req,timeout=self.timeout) as response:
            raw=json.loads(response.read(2_000_000))
        if not isinstance(raw.get("message",{}).get("content"),str):
            raise ValueError("Model returned no text")
        result=json.loads(raw["message"]["content"])
        if not isinstance(result,dict):
            raise ValueError("LLM must return one JSON object")
        return result


def validate_case(case:Mapping[str,Any])->None:
    if not isinstance(case,Mapping):
        raise ValueError("case must be a mapping")
    if not isinstance(case.get("goal"),str) or not case["goal"].strip():
        raise ValueError("missing engineering goal")
    donors=case.get("donors")
    if not isinstance(donors,list) or len(donors)<2 or len(donors)>12:
        raise ValueError("a bounded two-or-more donor investigation is required")
    ids=[]
    for donor in donors:
        if not isinstance(donor,Mapping) or not isinstance(donor.get("id"),str):
            raise ValueError("invalid donor record")
        ids.append(donor["id"])
        if not isinstance(donor.get("reported_capabilities"),list):
            raise ValueError("donor reported_capabilities required")
        if donor.get("specimen_verified") is not False:
            raise ValueError("the current trial accepts only unverified donor hypotheses")
        if donor.get("measured_interfaces") not in (None,[],{}):
            raise ValueError("no physical interface measurements are authenticated")
    if len(ids)!=len(set(ids)):
        raise ValueError("duplicate donor IDs")
    constraints=case.get("constraints") or {}
    if not isinstance(constraints,Mapping):
        raise ValueError("constraints must be an object")
    if constraints.get("stationary_only") is True and constraints.get("mobile_required") is True:
        raise ValueError("contradictory locomotion requirements")
    # Prevent model from reading injected tool instructions inside donor data.
    if len(json.dumps(case))>30_000:
        raise ValueError("case too large")


def inspect_donors(case:Mapping[str,Any])->dict[str,Any]:
    return {
        "tool":"inspect_donors",
        "donors":[{
            "id":d["id"],
            "original_device":d.get("original_device"),
            "reported_capabilities":d["reported_capabilities"],
            "source_claims":d.get("source_claims",[]),
            "specimen_verified":False,
            "verified_measurements":[],
            "condition":d.get("condition","unknown"),
        } for d in case["donors"]],
        "evidence_warning":"Names and public listings are reported hypotheses, NOT observed usable donor components.",
    }


def inspect_requirements(case:Mapping[str,Any])->dict[str,Any]:
    return {
        "tool":"inspect_requirements",
        "goal":case["goal"],
        "constraints":case.get("constraints",{}),
        "safety":{"physical_power":False,"fabrication":False,"unattended_motor_operation":False},
        "unknowns":["No donor acquired or measured","No verified electrical ratings or mounting geometry"],
        "cad_parameters_source":"Only case.concept_envelope_mm if supplied, never infer geometry from seller claim.",
    }


def independent_design_audit(case:Mapping[str,Any],design:Any)->dict[str,Any]:
    """Separate physical/identity/requirements checks; never reads model PASS claims."""
    errors=[]
    warnings=[]
    if not isinstance(design,Mapping):
        design={}
        errors.append("no_design_object")
    donor_ids={x["id"] for x in case["donors"]}
    arch=design.get("architecture_name")
    concept=design.get("concept")
    if not isinstance(arch,str) or len(arch.strip())<5 or not isinstance(concept,str) or len(concept.strip())<25:
        errors.append("insufficient_architecture_description")
    raw_functions=design.get("functions")
    functions=raw_functions if isinstance(raw_functions,list) else []
    function_ids=[]
    for f in functions:
        if isinstance(f,Mapping) and isinstance(f.get("id"),str) and isinstance(f.get("purpose"),str):
            function_ids.append(f["id"])
    if len(function_ids)<4 or len(function_ids)!=len(functions) or len(set(function_ids))!=len(function_ids):
        errors.append("insufficient_or_duplicated_functional_decomposition")
    safety_tokens=" ".join(f.get("id","")+" "+f.get("purpose","") for f in functions if isinstance(f,Mapping)).lower()
    if not any(x in safety_tokens for x in ("safety","stop","inhibit","power isolation","shutdown")):
        errors.append("missing_independent_stop_or_hazard_function")
    allocations=design.get("allocations")
    rows=allocations if isinstance(allocations,list) else []
    reused=set()
    for row in rows:
        if not isinstance(row,Mapping):
            errors.append("malformed_allocation")
            continue
        did=row.get("donor_id")
        if did not in donor_ids|{"NEW_COMPONENT_REQUIRED"}:
            errors.append("invented_donor_identity")
        if row.get("function_id") not in function_ids:
            errors.append("allocation_not_bound_to_function")
        if not isinstance(row.get("hypothetical_use"),str) or len(row["hypothetical_use"])<8:
            errors.append("allocation_missing_functional_role")
        if did in donor_ids:
            reused.add(did)
            source=next(d for d in case["donors"] if d["id"]==did)
            claims=source["reported_capabilities"]+source.get("source_claims",[])
            if row.get("source_capability_quote") not in claims:
                errors.append("allocation_donor_claim_quote_unsupported")
        if row.get("observed_compatible") is not False:
            errors.append("unverified_part_promoted_as_compatible")
        if row.get("physical_stock_owned") is not False:
            errors.append("unowned_donor_claimed_in_inventory")
    if len(reused)<2:
        errors.append("fewer_than_two_distinct_reused_donor_hypotheses")
    links=design.get("interfaces")
    edges=links if isinstance(links,list) else []
    for edge in edges:
        if not isinstance(edge,Mapping):
            errors.append("malformed_interface")
            continue
        if edge.get("from_function") not in function_ids or edge.get("to_function") not in function_ids:
            errors.append("interface_endpoint_missing_function")
        if edge.get("verified") is not False:
            errors.append("unmeasured_interface_marked_verified")
    if len(edges)<2:
        errors.append("insufficient_cross_component_interface_explanation")

    requests=design.get("measurement_requests")
    requests=requests if isinstance(requests,list) else []
    requested=set()
    for x in requests:
        if not isinstance(x,Mapping):
            errors.append("malformed_measurement_request")
            continue
        if x.get("donor_id") not in donor_ids:
            errors.append("measurement_unknown_donor")
        else:
            requested.add(x["donor_id"])
        if any(not isinstance(x.get(k),str) or len(x[k].strip())<4 for k in
               ("quantity","method","decision_affected")):
            errors.append("measurement_not_actionable")
    if not reused.issubset(requested):
        errors.append("reused_donors_missing_measurement_requests")
    if len(requests)<2:
        errors.append("insufficient_physical_measurement_plan")
    alternatives=design.get("alternatives")
    if not isinstance(alternatives,list) or not alternatives:
        errors.append("no_alternative_architecture_compared")
    constraints=case.get("constraints",{})
    if constraints.get("stationary_only") is True:
        domain=str(design.get("machine_domain") or "").lower()
        if any(x in domain for x in ("rover","vehicle","mobile","flying")) or not domain:
            errors.append("stationary_objective_misclassified_as_mobile")
    for field in PHYSICAL_FALSE:
        if design.get(field) is not False:
            errors.append("false_or_unstated_physical_authority:"+field)
    # This is an integrity and bounded-completeness oracle, not genuine
    # verification that the proposed creative architecture is technically good.
    warnings.append("Engineering feasibility and physical behavior are not independently verified.")
    warnings.append("A passing bounded audit is NOT a verified repair, assembled product, or safe print.")
    return {
        "schema_version":"hardware_splicer.independent_agent_design_oracle.v1",
        "passes_bounded_evidence_and_structure":not errors,
        "issues":sorted(set(errors)),
        "warnings":warnings,
        "different_donors_reused_hypothetically":len(reused),
        "measurements_request_count":len(requests),
        "physical_measurements_observed":0,
        "practical_feasibility_independently_verified":False,
        "physical_build_authorized":False,
    }


SYSTEM="""You are Hardware Splicer's ENGINEERING AGENT. Select the next action from:
inspect_donors, inspect_requirements, evaluate_design, prepare_concept_cad, finish.
Respond with ONE JSON object {"action":"...","reason":"..."}.
For evaluate_design, additionally provide "design": a JSON object of this shape:
architecture_name, concept, machine_domain, functions:[{id,purpose}],
allocations:[{function_id,donor_id,hypothetical_use,source_capability_quote,
observed_compatible:false,physical_stock_owned:false}],
interfaces:[{from_function,to_function,medium,verified:false}],
measurement_requests:[{donor_id,quantity,method,decision_affected}],
alternatives:[{name,tradeoff}],
physical_verified:false, real_donor_measured:false,
physical_build_authorized:false, fabrication_approved:false,
safe_to_power:false, physically_tested:false.
Requirements: four or more functions incl independent emergency stop; two different
donors; at least two interface hypotheses; unknown electrical/physical interfaces
remain unverified. Compare another architecture and specify REAL measurements.
For donor allocations source_capability_quote MUST be an EXACT original
reported_capabilities string returned by inspect_donors, never invented.
All donors are FAULTY, UNOWNED, UNTESTED. Report uncertainty, do not invent
voltages, connectors, geometry, motor ratings, tests or inventory.
If independent audit rejects your design, improve it and resubmit.
Do not run code, browse, operate devices or approve physical hardware.
If out of time finish; a model statement alone cannot pass any gate.
"""


def run_agent_trial(case:dict[str,Any], model:JsonPolicy, *,max_rounds:int=7)->dict[str,Any]:
    validate_case(case)
    if not 2<=max_rounds<=12:
        raise ValueError("max_rounds must be between 2 and 12")
    messages=[
        {"role":"system","content":SYSTEM},
        {"role":"user","content":json.dumps({
            "objective":case["goal"][:470],
            "donors":[{
                "id":d["id"],
                "reported_capabilities":d["reported_capabilities"][:1],
                "physical_verified":False,
            } for d in case["donors"]],
            "constraints":case.get("constraints") or {},
            "instructions":"Select a useful next action; source information is available in tools. Feel free to submit a conditional design, then revise it according to the independent evaluator.",
        },ensure_ascii=False)},
    ]
    trace=[]
    latest_design=None
    latest_audit=None
    illegal_tool_attempts=[]
    finishes=0
    provider_errors=[]
    for n in range(max_rounds):
        started=time.perf_counter()
        try:
            context=messages if len(messages)<=6 else [*messages[:2],*messages[-4:]]
            response=model.decide(copy.deepcopy(context))
        except (TimeoutError,ValueError,urllib.error.URLError,KeyError,json.JSONDecodeError) as exc:
            provider_errors.append({
                "round":n+1,"type":type(exc).__name__,
                "message":str(exc)[:250],
            })
            trace.append({
                "round":n+1,"model_action":None,
                "model_elapsed_sec":round(time.perf_counter()-started,3),
                "tool_receipt":{"error":"MODEL_PROVIDER_FAILURE"},
                "model_design_in_this_round":False,
            })
            break
        elapsed=round(time.perf_counter()-started,3)
        action=response.get("action")
        reasoning=str(response.get("reason",""))[:2000]
        if action not in TOOLS:
            illegal_tool_attempts.append(str(action)[:100])
            receipt={"error":"INVALID_ACTION","allowed_actions":list(TOOLS)}
        elif action=="inspect_donors":
            receipt=inspect_donors(case)
        elif action=="inspect_requirements":
            receipt=inspect_requirements(case)
        elif action=="evaluate_design":
            latest_design=response.get("design")
            latest_audit=independent_design_audit(case,latest_design)
            receipt={"tool":"evaluate_design","independent_audit":latest_audit}
        elif action=="prepare_concept_cad":
            # CAD cannot be based on inferred listing dimensions.
            specified=case.get("concept_envelope_mm")
            if not isinstance(specified,Mapping):
                receipt={"tool":"prepare_concept_cad","status":"BLOCKED",
                         "reason":"No explicit CAD dimensions in case; model must not invent them."}
            else:
                from .solidcraft_workspace_bridge import build_solidcraft_workspace_handoff
                from .functional_architecture import derive_functional_architecture
                intake={"goal":case["goal"],"constraints":case.get("constraints",{}),
                        "concept_envelope_mm":specified}
                if not latest_audit or not latest_audit["passes_bounded_evidence_and_structure"]:
                    receipt={"tool":"prepare_concept_cad","status":"BLOCKED",
                             "reason":"No independently audited conditional design"}
                else:
                    workspace=build_solidcraft_workspace_handoff(intake,derive_functional_architecture(intake))
                    receipt={"tool":"prepare_concept_cad","cad_plan":workspace}
        else:
            finishes+=1
            receipt={"tool":"finish",
                     "conditional_design_accepted":bool(latest_audit and latest_audit["passes_bounded_evidence_and_structure"]),
                     "physical_hardware_success":False}
        trace.append({"round":n+1,"model_action":action,"reason":reasoning,
                      "model_elapsed_sec":elapsed,
                      "tool_receipt":receipt,
                      "model_design_in_this_round":action=="evaluate_design"})
        messages.extend([
            {"role":"assistant","content":json.dumps(response,ensure_ascii=False)},
            {"role":"user","content":json.dumps({
                "tool_receipt":receipt,
                "instruction":"Choose next action based on independent feedback. If issues exist, revise design and resubmit; only finish after audit success or budget exhaustion.",
                "rounds_remaining":max_rounds-n-1,
            },ensure_ascii=False)},
        ])
        if action=="finish":
            break

    accepted=bool(latest_audit and latest_audit["passes_bounded_evidence_and_structure"])
    return {
        "schema_version":SCHEMA,
        "objective":case["goal"],
        "source_case_digest":digest(case),
        "model_backend_type":type(model).__name__,
        "model_name":getattr(model,"model","injected_policy"),
        "llm_decision_rounds":len(trace),
        "model_actions":[t["model_action"] for t in trace],
        "model_drove_action_selection":True,
        "independent_audit":latest_audit,
        "candidate_design":latest_design,
        "bounded_conditional_design_accepted":accepted,
        "completed_agent_loop":finishes>0,
        "invalid_model_tool_requests":illegal_tool_attempts,
        "model_provider_errors":provider_errors,
        "trace":trace,
        "all_original_donor_specs_unverified":True,
        "actual_bench_measurements_observed":0,
        "real_sensor_instruments_used":False,
        "real_cad_executed_during_agent_loop":False,
        "real_electrical_simulation_executed_during_agent_loop":False,
        "physical_build_authorized":False,
        "real_product_functionally_proven":False,
    }
