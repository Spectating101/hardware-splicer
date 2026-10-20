"""Replay a visibly model-authored, in-conversation agent tool session.

This is NOT a local Ollama inference or autonomous background completion.
The decision sequence and conditional design were authored by GPT-6 in the
current interactive session. Calls HS's actual MCP tool handler independently.
"""
from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path

from hardware_splicer import mcp_server
from hardware_splicer.engineering_agent_trial import digest

ROOT=Path(__file__).resolve().parents[1]


async def _main(case:Path,design:Path,out:Path)->int:
    source=json.loads(case.read_text(encoding="utf-8"))
    authored=json.loads(design.read_text(encoding="utf-8"))
    assert authored["producer"].startswith("GPT-6 design authored")
    steps=[
        {"action":"inspect_donors","reason":"Check what functions each proposed donor might contain, keeping condition uncertain"},
        {"action":"inspect_requirements","reason":"Separate stationary objective and independent safety constraints"},
        {"action":"evaluate_design","reason":"Develop a new seven-function sorting architecture with genuine alternative designs and donor-specific measurement requests","design":authored["design"]},
        {"action":"prepare_concept_cad","reason":"Try to advance to mechanical geometry only after checking whether actual donor dimensions exist"},
        {"action":"finish","reason":"Return architecture and exact evidence needed, rather than claiming completed salvage"},
    ]
    first=await mcp_server.call_tool("hs_engineering_agent_session",{"engineering_case":source})
    state=json.loads(first[0].text)
    tool_receipts=[]
    for step in steps:
        response=await mcp_server.call_tool("hs_engineering_agent_session",
                                            {"session_state":state,"model_decision":step})
        state=json.loads(response[0].text)
        tool_receipts.append({
            "model_selected_action":step["action"],
            "host_tool_receipt":state["last_tool_receipt"],
            "source_case_digest":state["case_sha256"],
        })
    assert state["stage"]=="FINISHED"
    assert state["latest_independent_audit"]["passes_bounded_evidence_and_structure"]
    assert state["actions"][3]["action"]=="prepare_concept_cad"
    assert state["last_tool_receipt"]["physical_product_built"] is False
    assert not state["physical_actions_authorized"]
    outcome={
        "schema_version":"hardware_splicer.gpt6_connected_engineering_session_evidence.v1",
        "model_decision_origin":"GPT-6 conversation-authoritative prompt decisions; replayed through real HS MCP server handler",
        "autonomous_unsupervised_model_inference_performed":False,
        "actual_mcp_tool_handler_invoked":True,
        "scenario":source["scenario_id"],
        "donor_count":len(source["donors"]),
        "source_case_sha256":digest(source),
        "model_decision_steps":len(steps),
        "model_actions":[s["action"] for s in steps],
        "full_tool_receipts":tool_receipts,
        "independent_design_integrity_audit":state["latest_independent_audit"],
        "bounded_design_accepted":state["latest_independent_audit"]["passes_bounded_evidence_and_structure"],
        "conditional_candidate_architecture":authored["design"]["architecture_name"],
        "physical_donor_evidence_authenticated":False,
        "concept_cad_rejected_no_measured_or_declared_geometry":tool_receipts[3]["host_tool_receipt"]["status"]=="BLOCKED",
        "physical_build_authorized":False,
        "physical_product_functionally_proven":False,
        "model_runtime_blocker":"Claude Code OAuth expired; Gemini CLI timed out; local Ollama Qwen 7B and 1.5B both timed out on memory-saturated Optiplex",
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(outcome,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
    print(json.dumps({
        "mcp_tool_calls":len(steps)+1,
        "model_authored_architecture":outcome["conditional_candidate_architecture"],
        "donor_hypotheses":outcome["independent_design_integrity_audit"]["different_donors_reused_hypothetically"],
        "conditional_audit":outcome["bounded_design_accepted"],
        "missing_geometry_rejected":outcome["concept_cad_rejected_no_measured_or_declared_geometry"],
        "physical_evidence":False,
        "local_autonomous_model_completed":False,
        "result_file":str(out),
    },indent=2))
    return 0


def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--case",type=Path,
                        default=ROOT/"examples/engineering_agent/hypothetical_sorter_multidonor.json")
    parser.add_argument("--reference",type=Path,
                        default=ROOT/"docs/evaluations/AGENT_OPTICAL_SORTER_CONDITIONAL_REFERENCE_2026-10-20.json")
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    return asyncio.run(_main(args.case,args.reference,args.out))


if __name__=="__main__":
    raise SystemExit(main())
