"""Persistent bounded LLM reasoning -> real read-only engineering tools -> revision.

Unlike the existing single-pass proposal planner, a real LLM adapter is asked
again after observing actual tool outputs. No provider/key assumed. A callable
may be injected for deterministic falsification tests. Tool execution is
allowlisted and cannot actuate machinery, flash firmware, slice G-code or
authorize fabrication.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from .integrations.llm_text_client import call_llm_chat

ALLOWED_TOOLS=frozenset({
    "inspect_sources", "derive_functions", "audit_candidate", "propose_printed_casing",
})
MAX_STEPS=6


def _digest(value:Any)->str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def _tools(name:str, args:Mapping[str,Any], scenario:Mapping[str,Any])->dict:
    if name=="inspect_sources":
        source_rows=scenario.get("engineering_sources") or []
        return {
            "source_count":len(source_rows),
            "sources":[{"source_id":x.get("source_id"),"uri":x.get("uri"),
                        "claimed_version":x.get("version") or x.get("revision"),
                        "claims":x.get("claims",[])[:8],
                        "authentication":"SUPPLIED_UNVERIFIED"} for x in source_rows[:24]],
            "physical_measurements_authenticated":False,
        }
    if name=="derive_functions":
        from .functional_architecture import derive_functional_architecture
        return derive_functional_architecture(scenario["intake"])
    if name=="audit_candidate":
        from .sdk import plan_source_bound_design
        return plan_source_bound_design(scenario=scenario)
    if name=="propose_printed_casing":
        from .printed_enclosure_workbench import prepare_printed_enclosure
        # Caller must provide a fully explicit spec. No LLM-generated
        # measured-specimen labels are allowed.
        spec=dict(args.get("casing_spec") or {})
        return prepare_printed_enclosure(spec)
    raise ValueError("tool not allowlisted")


def _parse(content:str)->dict:
    data=json.loads(content)
    if not isinstance(data,dict) or data.get("action") not in ALLOWED_TOOLS | {"finish"}:
        raise ValueError("invalid model action")
    if not isinstance(data.get("reason"),str) or not data["reason"].strip():
        raise ValueError("missing model rationale")
    if data.get("action")!="finish" and not isinstance(data.get("arguments",{}),dict):
        raise ValueError("invalid arguments")
    if data["action"]=="finish" and (not isinstance(data.get("result"),dict)):
        raise ValueError("missing final structured result")
    return data


def run_engineering_reasoning_agent(
    scenario:Mapping[str,Any],
    *,
    llm_callable:Callable[...,dict]|None=None,
    max_steps:int=MAX_STEPS,
)->dict:
    if not 1<=max_steps<=MAX_STEPS:
        raise ValueError("max_steps outside bounded allowance")
    if not isinstance(scenario,Mapping) or not isinstance(scenario.get("intake"),Mapping):
        raise ValueError("full scenario with intake required")
    client=llm_callable or call_llm_chat
    prompt_context={
        "scenario":dict(scenario),
        "tools":[
            {"name":"inspect_sources","purpose":"Examine supplied source claims and limitations"},
            {"name":"derive_functions","purpose":"Inspect functional decomposition; not physical proof"},
            {"name":"audit_candidate","purpose":"Run actual canonical HS planner and independent oracle"},
            {"name":"propose_printed_casing","purpose":"Only declared test dimensions and concept authority"},
        ],
        "safety":"Never claim a donor owned/measured, a working assembly, or permission to actuate/print.",
    }
    transcript=[]
    last=None
    final=None
    for index in range(max_steps):
        prompt=json.dumps({
            "mission":"Independently investigate and reason from engineering requirements using available tools. Choose exactly one next action; do not simply repeat fixed tool sequence.",
            "initial_context":prompt_context,
            "prior_tool_receipts":transcript[-5:],
            "response_schema":{"action":"one tool name or finish",
                               "reason":"engineering reason for action",
                               "arguments":"object for tool, if action is a tool",
                               "result":"object if finish including hypotheses and unresolved evidence"},
        },sort_keys=True,default=str)
        raw=client(
            prompt,stage="planning",temperature=0,json_mode=True,timeout_s=120,
            system="You are a conservative Hardware Splicer engineering investigator. Respond with one JSON object. No fabrication or physical authorization.",
        )
        if not isinstance(raw,Mapping) or not raw.get("ok"):
            return {"status":"MODEL_UNAVAILABLE","error":str((raw or {}).get("error") if isinstance(raw,Mapping) else raw),
                    "model_was_called":True,"steps":transcript,"physical_release":False}
        decision=_parse(str(raw.get("content") or ""))
        action=decision["action"]
        receipt={"step":index+1,"model_action":action,"model_reason":decision["reason"],
                 "model_response_sha256":hashlib.sha256(str(raw["content"]).encode()).hexdigest()}
        if action=="finish":
            final=decision["result"]
            transcript.append(receipt)
            break
        args=decision.get("arguments") or {}
        try:
            tool_result=_tools(action,args,scenario)
            receipt["tool_output"]=tool_result
            receipt["tool_ok"]=True
            receipt["tool_result_sha256"]=_digest(tool_result)
        except (ValueError,KeyError,TypeError) as exc:
            receipt["tool_ok"]=False
            receipt["tool_error"]=str(exc)[:800]
        transcript.append(receipt)
    return {
        "schema_version":"hardware_splicer.engineering_reasoning_agent.v1",
        "status":"MODEL_FINISHED" if final is not None else "STEP_BUDGET_EXHAUSTED",
        "model_was_called":True,
        "model_is_test_double":llm_callable is not None,
        "steps":transcript,
        "final_proposal":final,
        "source_scenario_sha256":_digest(scenario),
        "tool_names_allowed":sorted(ALLOWED_TOOLS),
        "physically_authenticated_observations":False,
        "autonomous_physical_execution":False,
        "fabrication_authorized":False,
        "power_authorized":False,
        "physical_release":False,
    }
