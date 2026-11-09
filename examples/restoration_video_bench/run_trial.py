"""Retrospective restoration challenge using native HS repair_intake + new triage.

1. Load ONLY public-symptom case records.
2. Produce 0/1-stage predicted differential and source hash; SAVE predictions.
3. ONLY THEN open creator-reported gold fixture files and score predictions.

A JSON filesystem barrier exists; this is *not* a scientifically independent
blind benchmark because the taxonomy/rules were authored after learning the
cases. No YouTube frames, video OCR, transcripts or actual meters were used.
"""
from __future__ import annotations

import argparse,hashlib,json
from pathlib import Path
from typing import Any

from hardware_splicer.restoration_video_triage import triage

HERE=Path(__file__).resolve().parent
SRC=HERE/"cases"
OUTCOME=HERE/"hidden_outcomes"
EVIDENCE=HERE/"evidence"

def _sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def prepare(intakes:Path=SRC)->dict[str,Any]:
    records=sorted(intakes.glob("*.json"))
    if len(records)<4:
        raise ValueError("at least 4 documented video case intakes required")
    rows=[]
    for path in records:
        data=json.loads(path.read_text())
        if data.get("case_id")!=path.stem:raise ValueError("case/id mismatch")
        initial=triage(data,0)
        followup=triage(data,1)
        assert all(not x["release"]["repair_executed_by_HS"] for x in (initial,followup))
        rows.append({
            "case_id":data["case_id"],
            "source_url":data["source_context"]["url"],
            "case_input_sha256":_sha(path),
            "initial":initial,"followup":followup,
        })
    return {
        "schema":"hs.restoration.video_replay_predictions.v1",
        "dataset":"4 creator-described restoration cases (low variety, deliberately non-independent)",
        "source_kind":"YouTube public descriptions, not full video analysis",
        "source_notes":"human-authored generic taxonomy informed by public examples",
        "gold_labels_loaded_in_prediction_stage":False,
        "predictions":rows,
    }

def score(predictions:dict[str,Any],outcomes:Path=OUTCOME)->dict[str,Any]:
    if predictions.get("schema")!="hs.restoration.video_replay_predictions.v1":
        raise ValueError("must predict before opening gold")
    findings=[]
    for item in predictions["predictions"]:
        path=outcomes/(item["case_id"]+".json")
        gold=json.loads(path.read_text())
        if gold["case_id"]!=item["case_id"] or gold["schema"]!="hs.restoration.video_heldout_outcome.v1":
            raise ValueError("wrong gold source or case collision")
        if gold["source_url"]!=item["source_url"]:
            raise ValueError("video source mismatch")
        root=gold["root_cause"]
        initial=[x["hypothesis_id"] for x in item["initial"]["ranked_differential"]]
        follow=[x["hypothesis_id"] for x in item["followup"]["ranked_differential"]]
        findings.append({
          "case_id":item["case_id"],"video_url":item["source_url"],
          "creator_reported_root_cause":root,
          "source_outcome_quality":gold["evidence_quality"],
          "initial_top1":initial[0],
          "initial_top3":initial,
          "initial_hit_at_1":root==initial[0],
          "initial_hit_at_3":root in initial[:3],
          "after_observations_top1":follow[0],
          "after_observations_top3":follow,
          "after_observations_hit_at_1":root==follow[0],
          "after_observations_hit_at_3":root in follow[:3],
          "creator_reported_repair_actions":gold["repair_steps"],
          "creator_reported_outcome":gold["reported_outcome"],
          "HS_did_not_execute_repair":True,
          "human_electrical_confirmation_required":True,
          "creator_outcome_SHA256":_sha(path),
        })
    n=len(findings)
    metrics={key:sum(int(v[key]) for v in findings) for key in (
         "initial_hit_at_1","initial_hit_at_3",
         "after_observations_hit_at_1","after_observations_hit_at_3")}
    return {
       "schema":"hs.restoration.video_replay_evaluation.v1",
       "status":"RETROSPECTIVE_HUMAN_AUTHORED_TRIAGE_REPLAY_NO_PHYSICAL_REPAIR",
       "case_count":n,
       "metrics_counts":metrics,
       "metrics_denominator":n,
       "case_results":findings,
       "methodology":{
          "prediction_was_written_before_gold_opened_in_this_runner":True,
          "gold_labels_separated_from_diagnostic_function":True,
          "human_authored_rule_taxonomy_postdated_public_case_outcomes":True,
          "NOT_scientifically_independent_blind_test":True,
          "NOT_a_proof_of_generalization":True,
          "NOT_actual_video_frame_or_transcript_processing":True,
          "NOT_an_LLM_autonomous_diagnosis":True,
          "native_HS_repair_intake_was_used":True,
          "diagnostic_checks_are_proposed_not_measured":True,
          "root_cause_is_creator_report_not_independent_test":True,
          "actual_restoration_repaired_by_HS":False,
          "any_tools_or_parts_purchased":False,
       },
       "open_improvements":[
         "Real YouTube video timestamp/visual evidence extraction with provenance and consent",
         "Prospective unseen-device cases with no posthoc rule tuning",
         "Real images, boardview/netlist and independent multimeter observations",
         "Native tool dispatcher must select meter/CAD/KiCad/parts only when inputs support them",
         "Repair-to-verification feedback from an actual independent technician",
       ],
    }

def run(out:EVIDENCE=EVIDENCE)->dict[str,Any]:
    out.mkdir(parents=True,exist_ok=True)
    # Must write predictions prior to accessing hidden gold files.
    predicted=prepare()
    (out/"blind_predictions.json").write_text(json.dumps(predicted,indent=2)+"\n")
    evaluated=score(predicted)
    evaluated["predictions_file_sha256"]=_sha(out/"blind_predictions.json")
    (out/"evaluation.json").write_text(json.dumps(evaluated,indent=2)+"\n")
    return evaluated

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=EVIDENCE)
    args=p.parse_args()
    result=run(args.out)
    print(json.dumps({
        "status":result["status"],
        "cases":result["case_count"],
        "initial_top1":result["metrics_counts"]["initial_hit_at_1"],
        "followup_top1":result["metrics_counts"]["after_observations_hit_at_1"],
        "not_independent":result["methodology"]["NOT_scientifically_independent_blind_test"],
    },indent=2))
