"""Reproduce receipts for the frozen genuine numeric source A/B without a live LLM.

CI audits the EXACT pre-outcome model prompts from the validated immutable
source ledger, model identity, source classifications and result SHA.
The source artifacts were verified during live capture; original WebVTT
and full publisher HTML are not redistributed in this repository.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hardware_splicer.restoration_numeric_case import build_numeric_case_context
from hardware_splicer.restoration_reasoning_agent import build_messages, sha
from run_numeric_source_ab import protocol, CASE_ARMS, MODEL

HERE=Path(__file__).resolve().parent
SOURCE=HERE/"source_numeric_claims.json"
LEDGER=HERE/"source_numeric_claims_validated.json"

def inspect(frozen:dict)->dict:
    if frozen.get("protocol")!=protocol() or frozen.get("protocol_sha256")!=sha(protocol()):
        raise ValueError("changed experimental source comparison protocol")
    if not frozen.get("complete") or len(frozen.get("cases") or [])!=len(CASE_ARMS):
        raise ValueError("missing or incomplete actual model arms")
    manifest=json.loads(SOURCE.read_text())
    ledger=json.loads(LEDGER.read_text())
    if frozen["original_numeric_source_manifest_sha256"]!=sha(manifest):
        raise ValueError("source manifest changed after freezing the model")
    if ledger["source_manifest_sha256"]!=sha(manifest) or frozen["numeric_source_validation"]!=ledger:
        raise ValueError("source graph or source classifications changed after capture")
    if ledger["source_authority_ceiling"]!="declared" or ledger["measurements_physically_taken_by_HS"]:
        raise ValueError("reported numerical claim upgraded to bogus verified instrument evidence")
    if frozen["real_HS_graph_sha256"]!=ledger["native_HS_source_graph_sha256"]:
        raise ValueError("actual native HS engineering source graph changed")
    findings=[]
    for row,(case_id,order) in zip(frozen["cases"],CASE_ARMS):
        if row["case_id"]!=case_id or row["model_arm_order"]!=list(order):
            raise ValueError("registered case or execution order was changed")
        base=build_numeric_case_context(ledger,case_id=case_id,assisted=False)
        hs=build_numeric_case_context(ledger,case_id=case_id,assisted=True)
        if (base["evidence_sha256"]!=hs["evidence_sha256"]
                or base["evidence_sha256"]!=row["evidence_sha256"]):
            raise ValueError("same original numerical source evidence was not used")
        arm_results={}
        for arm,ctx in (("plain",base),("hs_numeric_source",hs)):
            r=row["arms"].get(arm)
            if r is None:
                raise ValueError("missing registered arm")
            digest=sha({k:v for k,v in r.items()
                        if k not in ("receipt_sha256","elapsed_seconds")})
            if digest!=r.get("receipt_sha256"):
                raise ValueError("frozen model receipt was edited")
            for k,expected in (
                ("evidence_sha256",ctx["evidence_sha256"]),
                ("prompt_sha256",sha(build_messages(ctx))),
                ("model_requested",MODEL),
                ("model_reported",MODEL),
            ):
                if r.get(k)!=expected:
                    raise ValueError(f"{arm} model/prompt mismatch: {k}")
            if r.get("provider_reported")!="agy_antigravity_subscription_cli":
                raise ValueError("not a real authenticated existing Antigravity model call")
            if r.get("physical_measurements_by_HS") is not False or r.get("repair_authorized") is not False:
                raise ValueError("improper physical authority")
            if arm=="hs_numeric_source":
                if r.get("numeric_source_tool_sha256")!=sha(ctx["numeric_source_tool"]):
                    raise ValueError("quantitative provenance tool changed")
                if r.get("numeric_source_graph_sha256")!=ledger["native_HS_source_graph_sha256"]:
                    raise ValueError("HS source graph inconsistent")
                if r.get("reported_numbers_not_HS_measurements") is not True:
                    raise ValueError("real vs reported instrument distinction lost")
            else:
                if r.get("numeric_source_tool_sha256") is not None:
                    raise ValueError("plain arm got the restricted treatment")
            arm_results[arm]={
                "status":r["status"],
                "seconds":r["elapsed_seconds"],
                "error_type":r.get("error_type"),
                "error":r.get("error"),
                "first_hypothesis": (
                    r["plan"]["hypotheses"][0]["mechanism"]
                    if r.get("plan") and r["plan"]["hypotheses"] else None
                ),
                "next_safe_check":r["plan"]["next_safe_check"] if r.get("plan") else None,
            }
        findings.append({"case_id":case_id,"arms":arm_results,"source_sha256":row["evidence_sha256"]})
    return {
        "schema":"hs.restoration.numeric_source_no_gold_receipt_review.v1",
        "real_hs_graph_provenance_validated":True,
        "original_source_claim_count":ledger["claim_count"],
        "published_expectations":sum(c["claim_type"]=="published_reference_expectation" for c in ledger["claims"]),
        "creator_reported_readings":sum(c["claim_type"]=="creator_reported_reading" for c in ledger["claims"]),
        "independent_instrument_measurements":0,
        "model_calls":sum(len(row["arms"]) for row in frozen["cases"]),
        "valid_by_arm":{
            a:sum(row["arms"][a]["status"]=="proposed_unverified_differential"
                  for row in findings) for a in ("plain","hs_numeric_source")
        },
        "elapsed_by_arm_seconds":{
            a:round(sum(row["arms"][a]["seconds"] for row in findings),2)
            for a in ("plain","hs_numeric_source")
        },
        "cannot_score_repair_accuracy_or_true_safety_from_these_receipts":True,
        "creator_outcomes_not_accessed":True,
        "cases":findings,
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--infile",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    report=inspect(json.loads(args.infile.read_text()))
    args.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps({
        "model_calls":report["model_calls"],
        "valid_by_arm":report["valid_by_arm"],
        "elapsed_by_arm_seconds":report["elapsed_by_arm_seconds"],
        "published_expectations":report["published_expectations"],
        "creator_reported_readings":report["creator_reported_readings"],
        "independent_instrument_measurements":report["independent_instrument_measurements"],
    },indent=2))
if __name__=="__main__":
    main()
