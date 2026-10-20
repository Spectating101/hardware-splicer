import json
from pathlib import Path
from hardware_splicer.engineering_reasoning_agent import run_engineering_reasoning_agent


def test_model_iterates_over_actual_evidence_and_stops():
    case=json.loads((Path(__file__).resolve().parents[1]/"examples/source_bound_holdout/unfamiliar_tabletop_label_feeder_20261020.json").read_text())
    count=[0]
    def reasoning(prompt,**kwargs):
        req=json.loads(prompt)
        count[0]+=1
        if count[0]==1:
            decision={"action":"inspect_sources","reason":"First inspect the provenance"}
        elif count[0]==2:
            assert req["prior_tool_receipts"][-1]["tool_output"]["source_count"]==6
            decision={"action":"derive_functions","reason":"Infer required functions from objective"}
        elif count[0]==3:
            assert req["prior_tool_receipts"][-1]["tool_output"]["functional_domain"]=="stationary_processing_cell"
            decision={"action":"finish","reason":"Evidence insufficient for physical design",
                      "result":{"proposal":"Conditional stationary indexing station",
                                "verified_donors":0,"needs":["motor characterization","scanner cable identity"]}}
        return {"ok":True,"content":json.dumps(decision)}
    result=run_engineering_reasoning_agent(case,llm_callable=reasoning)
    assert count[0]==3
    assert result["status"]=="MODEL_FINISHED"
    assert [r["model_action"] for r in result["steps"]]==[
        "inspect_sources","derive_functions","finish",
    ]
    assert result["steps"][0]["tool_result_sha256"]
    assert result["final_proposal"]["verified_donors"]==0
    assert result["physical_release"] is False
    assert result["model_is_test_double"]


def test_model_cannot_actuate_hardware_or_escape_allowlist():
    case={"scenario_id":"unrelated","mode":"synthesize","intake":{"goal":"Make a machine"}}
    def forbidden(prompt,**kwargs):
        return {"ok":True,"content":json.dumps({"action":"flash_firmware","reason":"Get ahead"})}
    import pytest
    with pytest.raises(ValueError):
        run_engineering_reasoning_agent(case,llm_callable=forbidden)


def test_unavailable_provider_is_not_fabricated_success():
    case={"scenario_id":"unrelated","intake":{"goal":"Make a machine"}}
    result=run_engineering_reasoning_agent(
        case,llm_callable=lambda prompt,**kw:{"ok":False,"error":"missing_provider"},
    )
    assert result["status"]=="MODEL_UNAVAILABLE"
    assert not result["physical_release"]


def test_mcp_exposes_real_agent_without_fabrication():
    import asyncio
    from hardware_splicer import mcp_server
    tools=asyncio.run(mcp_server.list_tools())
    assert any(x.name=="hs_run_reasoning_engineering_agent" for x in tools)
