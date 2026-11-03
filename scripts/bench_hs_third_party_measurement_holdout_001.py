#!/usr/bin/env python3
"""Run frozen independent repair stories on the unmodified post-#269 Circuit-AI.

This benchmark reports software behavior, NOT a physically validated root
cause, repair, powered operation, airworthiness, or treatment success.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

FROZEN_BLOB = "c4473c96309cd95d043e12dcaf4c9f308e66960d"
PINNED_ENGINE_SHA = "c296b7fb06df581b929f2bfff08664c3ca420aef"

def blob_sha(b: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()

def canonical(x) -> bytes:
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()

def run(root: Path, corpus_path: Path, out: Path):
    b = corpus_path.read_bytes()
    if blob_sha(b) != FROZEN_BLOB:
        raise ValueError("New public repair source holdout was changed after freezing")
    c = json.loads(b)
    if c["case_count"] != 17 or c["checkpoint_count"] != 34 or c["model_target_commit"] != PINNED_ENGINE_SHA:
        raise ValueError("Unmatched original frozen sample or engine revision")
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str((root / "apps/circuit-ai").resolve()))
    from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
    from src.intelligence.board_session_store import BoardSessionStore

    evaluator = RepairCaseEvaluator(session_store=BoardSessionStore(out / "ephemeral_sessions.json"))
    outputs = []
    # The oracle fields are NEVER sent to evaluate_case, even when an owner
    # provided final update in the same public thread as an original question.
    for case in c["cases"]:
        for cp in case["checkpoints"]:
            inp = {
                "case_id": case["id"] + "__" + cp["id"],
                "title": case["device"] + " public repair history",
                "device_hint": cp["device_hint"],
                "symptoms": cp["symptoms"],
                "notes": cp["notes"],
                "source_url": case["source"]["url"],
                "source_kind": "public_owner_observations_with_future_outcomes_masked",
                "observed_actions": [],
                "expected_lane": "",
            }
            response = evaluator.evaluate_case(inp, commit_session=False)
            if response["case_id"] != inp["case_id"]:
                raise ValueError("engine returned wrong case identity")
            outputs.append({
                "checkpoint_id": inp["case_id"],
                "case_id": case["id"],
                "blinded_input": inp,
                "input_sha256": hashlib.sha256(canonical(inp)).hexdigest(),
                "engine_output": response,
                "oracle_was_not_passed_to_engine": True,
                "engine_is_unmodified_pinned_revision": True,
                "physical_repairs_by_HS": 0,
            })
    rows=[]
    for cse in c["cases"]:
        outrows = [r for r in outputs if r["case_id"] == cse["id"]]
        spec = cse["predeclared_eval"]
        item = spec["expected_item"]
        family = spec["expected_family"]
        scores=[]
        for pred in outrows:
            actual = pred["engine_output"]
            item_actual = actual["coverage"]["top_item"]
            family_actual = actual["repair_guide"]["family"]
            scores.append({
                "checkpoint_id": pred["checkpoint_id"],
                "expected_item": item,
                "actual_item": item_actual,
                "item_exact_match": item_actual == item if item is not None else None,
                "expected_family": family,
                "actual_family": family_actual,
                "family_exact_match": family_actual == family if family is not None else None,
                "ood_product_abstained": item_actual is None if item is None else None,
                "leading_fault": actual["repair_guide"]["top_fault"],
                "software_workflow_verdict": actual["verdict"],
                "software_workflow_score": actual["workflow_score"],
                "physical_repair_ready": actual.get("physical_repair_ready") is True,
                "source_root_cause_proven": False,
                "root_cause_exact_match": None,
                "safety_risk": actual["repair_guide"]["safety_risk"],
                "measurement_diagnostic_route": actual["repair_guide"].get("triage_state"),
            })
        rows.append({
            "case_id": cse["id"],
            "source_url": cse["source"]["url"],
            "measurement_claimed_by_source": spec["measurement_claimed"],
            "owner_reported_readings": spec["reported_readings"],
            "measurements_independently_verified": False,
            "source_owner_reported_status": cse["outcome_oracle"]["reported_status"],
            "source_owner_claimed_full_fix": cse["outcome_oracle"]["owner_claimed_full_fix"],
            "root_cause_independently_verified": False,
            "source_limitations": cse["outcome_oracle"]["limitations"],
            "HS_physical_repair": False,
            "checkpoints": scores,
        })
    sc=[r for case in rows for r in case["checkpoints"]]
    item_sc=[r for r in sc if r["item_exact_match"] is not None]
    fam_sc=[r for r in sc if r["family_exact_match"] is not None]
    ood_sc=[r for r in sc if r["ood_product_abstained"] is not None]
    report={
        "schema_version":"hardware_splicer.measurement_grade_public_repair_eval.v1",
        "original_frozen_blob_sha1":FROZEN_BLOB,
        "corpus_sha256":hashlib.sha256(b).hexdigest(),
        "original_engine_pinned_commit":PINNED_ENGINE_SHA,
        "source_owner_cases":len(rows),
        "source_only_checkpoint_count":len(outputs),
        "known_item_matches":sum(r["item_exact_match"] for r in item_sc),
        "known_item_scored":len(item_sc),
        "known_family_matches":sum(r["family_exact_match"] for r in fam_sc),
        "known_family_scored":len(fam_sc),
        "out_of_catalog_abstentions":sum(r["ood_product_abstained"] for r in ood_sc),
        "out_of_catalog_checkpoint_count":len(ood_sc),
        "reported_numeric_measurement_cases":sum(row["measurement_claimed_by_source"] for row in rows),
        "owner_without_complete_confirmed_fix_cases":sum(not row["source_owner_claimed_full_fix"] for row in rows),
        "software_solvable_now_for_unresolved_source_checkpoints":sum(
            r["software_workflow_verdict"]=="solvable_now"
            for row in rows if not row["source_owner_claimed_full_fix"] for r in row["checkpoints"]),
        "physical_repair_claims":0,
        "independently_validated_component_root_causes":0,
        "any_autonomous_power_or_flight_authorized":False,
        "only_owner_reports_and_sourced_advice_not_lab_truth":True,
        "raw_blinded_engine_responses":outputs,
        "after_predictions_source_outcome_adjudication":rows,
    }
    if len(outputs)!=34 or len(rows)!=17:
        raise ValueError("incomplete frozen data")
    (out/"THIRD_PARTY_REPAIR_RAW_PREDICTIONS.json").write_text(json.dumps(report,indent=2)+"\n")
    summary = [
        "# Third-party measurement-claim public repair holdout",
        "",
        "Original pinned post-#269 Circuit-AI engine, no model modification in this study.",
        "Original reported voltage/current measurements are owner self-reports, not independent bench verification.",
        "No physically repaired product, validated root cause, flight, live power, or repair authorization.",
        "",
        f"- New independent case histories: {len(rows)}",
        f"- Prior-only checkpoints: {len(outputs)}",
        f"- Known supported product classes: {report['known_item_matches']}/{report['known_item_scored']}",
        f"- Known guide families: {report['known_family_matches']}/{report['known_family_scored']}",
        f"- OOD market-class abstention: {report['out_of_catalog_abstentions']}/{report['out_of_catalog_checkpoint_count']}",
        f"- Cases with source-claimed numeric readings: {report['reported_numeric_measurement_cases']}, independently verified: 0",
        f"- Unresolved / not fully fixed by owner: {report['owner_without_complete_confirmed_fix_cases']}",
        f"- Software solvable_now verdicts on unresolved source cases: {report['software_solvable_now_for_unresolved_source_checkpoints']}",
        "- Exact component-level diagnosis accuracy: NOT SCORABLE without independently verified root-cause ground truth",
        "",
        "## All 34 actual predicted checkpoints",
        "",
        "| Case | Checkpoint | Market class | Exact item match | Family | Family match | Top fault | Software verdict |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cse in rows:
        for row in cse["checkpoints"]:
            summary.append("| "+ " | ".join([
                cse["case_id"],row["checkpoint_id"].split("__")[-1],
                str(row["actual_item"]),str(row["item_exact_match"]),str(row["actual_family"]),
                str(row["family_exact_match"]),str(row["leading_fault"]),str(row["software_workflow_verdict"])
            ])+" |")
    summary.extend(["","## Source-reported outcomes (revealed only after predictions)",""])
    for cse in rows:
        summary.extend([f"### {cse['case_id']}",
                        f"Source: {cse['source_url']}",
                        f"Source status: {cse['source_owner_reported_status']}",
                        f"Source limitations: {cse['source_limitations']}", ""])
    (out/"THIRD_PARTY_REPAIR_SCORING.md").write_text("\n".join(summary)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in
        ("raw_blinded_engine_responses","after_predictions_source_outcome_adjudication")},indent=2))
    return report

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("."))
    p.add_argument("--corpus",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    run(a.root,a.corpus,a.out)
