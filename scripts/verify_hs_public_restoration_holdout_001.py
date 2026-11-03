#!/usr/bin/env python3
"""Independent proof that the unseen source holdout was frozen and not leaked.

Avoid importing the evaluator/benchmark to recompute results. The report must
preserve exact predeclared prior-only symptoms, never show source outcomes to
the engine, and never promote owner hearsay or generated score to a repair.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

LOCKED_BLOB="b2441fb0fbdeb594e33a4f8f01deda25b3b3096a"
LOCKED_ORIGINAL_BRANCH_SHA="eb60037fb16e4b3696c4ad8197e5202606855caf"
EXPECTED_IDS={
  "holdout_iphone_se_2020_bracket_not_flex",
  "holdout_samsung_np_r580_no_charger_voltage",
  "holdout_nintendo_switch_dock_across_two_docks",
  "holdout_hp_deskjet_842c_carriage_stuck",
  "holdout_gameboy_color_speaker_after_two_replacements",
  "holdout_syma_x5c_crash_spins_no_lift",
  "holdout_syma_x5sw_wrong_prop_order_user_fixed",
}

def need(ok,reason):
    if not ok:raise ValueError("Independent HS unseen-public-repair holdout verification: "+reason)

def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha_blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def exact(data):return json.dumps(data,sort_keys=True,separators=(",",":")).encode()

def verify(cases:Path,report:Path)->dict:
    b=cases.read_bytes()
    need(sha_blob(b)==LOCKED_BLOB,"frozen independent public holdout was edited after preregistration")
    original=json.loads(b)
    evaluation=json.loads(report.read_text())
    need(original["schema_version"]=="hardware_splicer.public_restoration_unseen_holdout.v1" and
         evaluation["schema_version"]=="hardware_splicer.public_restoration_untouched_holdout_evaluation.v1",
         "frozen evaluator schema changed")
    need(evaluation["holdout_corpus_sha256"]==sha_bytes(b) and
         evaluation["holdout_corpus_git_blob_sha1"]==LOCKED_BLOB,
         "replay output computed against a different holdout")
    need(original["case_count"]==evaluation["precommitted_public_case_count"]==7 and
         original["checkpoint_count"]==evaluation["source_only_pre_solution_checkpoints"]==14,
         "frozen original sample count changed")
    case_map={x["id"]:x for x in original["cases"]}
    need(set(case_map)==EXPECTED_IDS and len(case_map)==7,"source population manipulated")
    preds=evaluation["raw_blinded_engine_outputs"]
    adjud=evaluation["after_prediction_case_by_case_adjudication"]
    need(len(preds)==14 and len(adjud)==7,"source evidence dropped")
    need(len({r["checkpoint_id"] for r in preds})==14 and
         {x["id"] for x in adjud}==EXPECTED_IDS,"source identity duplicated")
    for cid,case in case_map.items():
        need(case["oracle"]["physical_repaired_by_hs"] is False,"source itself invents HS physical repair")
        need(case["source"]["url"].startswith("https://www.ifixit.com/Answers/View/"),
             "unverified original public iFixit source link")
        steps=case["chronology"]
        need(len(steps)>=3 and [x["n"] for x in steps]==list(range(1,len(steps)+1)),
             "original public source chronology malformed")
        need(len(case["checkpoints"])==2 and len({x["id"] for x in case["checkpoints"]})==2,
             "original source two blind checkpoints dropped")
        for cp in case["checkpoints"]:
            need(cp["time_available"] and cp["time_available"]==sorted(set(cp["time_available"])) and
                 all(i<=len(steps) for i in cp["time_available"]) and
                 max(cp["time_available"])<len(steps),
                 "future source fix shown to diagnostic engine")
            ident=cid+"__"+cp["id"]
            row=next((x for x in preds if x["checkpoint_id"]==ident),None)
            need(row is not None,"frozen diagnostic checkpoint missing: "+ident)
            expected={
                "case_id":ident,
                "title":case["title"],
                "device_hint":cp["device_hint"],
                "symptoms":cp["symptoms"],
                "notes":cp["notes"],
                "source_url":case["source"]["url"],
                "source_kind":"earlier_public_case_observations_not_final_repair",
                "observed_actions":[],
                "expected_lane":"",
            }
            need(row["blinded_input"]==expected and
                 row["blinded_input_sha256"]==sha_bytes(exact(expected)),
                 "source outcome or diagnostic target leaked into actual evaluator request")
            need(row["source_event_steps_known"]==cp["time_available"] and
                 row["repair_and_future_truth_not_passed_to_engine"] is True,
                 "source intervention revealed before original model run")
            output=row["original_CircuitAI_evaluator_returned"]
            need(output["case_id"]==ident and
                 output["source_url"]==case["source"]["url"] and
                 output["verdict"] in {"solvable_now","assistive_only","not_ready"} and
                 output["repair_guide"]["family"] and
                 output["coverage"]["top_item"] and
                 0<=output["workflow_score"]<=1,
                 "original Circuit-AI model did not actually return a complete, valid case")
            # A model may correctly ABSTAIN: the unchanged engine emitted
            # top_fault=None for an unseen printer. Record this real lack of
            # diagnosis, never manufacture a candidate or discard the case.
            if output["repair_guide"]["top_fault"] is None:
                need(not row["generated_diagnostics"]["fault_candidates"] and
                     "hard: no fault candidate generated" in output["blockers"],
                     "missing fault must be transparently classified as engine abstention")
            need(row["current_model_not_modified_to_fit_holdout"] is True and
                 row["physical_product_repaired_by_HS"] is False and
                 row["bench_power_or_flight_authorized"] is False,
                 "source model manipulation or physical authority asserted")
        current=next(x for x in adjud if x["id"]==cid)
        need(current["source_url"]==case["source"]["url"] and
             current["reported_product_status"]==case["oracle"]["status"] and
             current["source_reported_intervention"]==case["oracle"]["source_intervention"] and
             current["owner_reported_full_fix"] is case["oracle"]["owner_reported_complete_fix"] and
             current["remaining_source_reported_faults"]==case["oracle"]["open_faults"] and
             current["repair_created_by_HS"] is False,
             "after-the-fact source outcome was altered")
        need(len(current["checkpoint_scores_after_predictions"])==2,
             "evaluation omitted a source checkpoint from scoring")
        for cp,score in zip(case["checkpoints"],current["checkpoint_scores_after_predictions"]):
            row=next(x for x in preds if x["checkpoint_id"]==cid+"__"+cp["id"])
            engine=row["original_CircuitAI_evaluator_returned"]
            meta=case["predeclared_eval"]
            expected_item=meta["expected_item"]
            expected_family=meta["expected_family"]
            diag=json.dumps(row["generated_diagnostics"],ensure_ascii=False,default=str).lower()
            matched=[t for t in meta["diagnostic_terms_any"] if t.lower() in diag]
            need(score["checkpoint_id"]==row["checkpoint_id"] and
                 score["engine_market_item"]==engine["coverage"]["top_item"] and
                 score["engine_family"]==engine["repair_guide"]["family"] and
                 score["engine_leading_fault_hypothesis"]==engine["repair_guide"]["top_fault"] and
                 score["software_workflow_verdict"]==engine["verdict"] and
                 score["software_workflow_score"]==engine["workflow_score"] and
                 score["predeclared_expected_market_item"]==expected_item and
                 score["predeclared_expected_family"]==expected_family,
                 "real engine classification or predeclared reference overwritten")
            need(score["market_item_exact_match"]==(
                engine["coverage"]["top_item"]==expected_item if expected_item is not None else None),
                "device type matching score corrupted")
            need(score["family_exact_match"]==(
                engine["repair_guide"]["family"]==expected_family if expected_family is not None else None),
                "diagnostic family matching score corrupted")
            need(score["diagnostic_terms_present_in_actual_engine"]==matched and
                 score["weak_keyword_relevance_proxy_any"]==bool(matched) and
                 score["actual_root_cause_diagnosis_measured_correctly"] is None,
                 "lexical mention promoted to verified source root-cause truth")
            need(score["software_verdict_is_not_physical_certification"] is True and
                 score["retrospective_outcome_not_given_to_engine"] is True,
                 "software routing wrongly promoted to hardware acceptance")
    flattened=[x for c in adjud for x in c["checkpoint_scores_after_predictions"]]
    known_types=[x for x in flattened if x["market_item_exact_match"] is not None]
    known_families=[x for x in flattened if x["family_exact_match"] is not None]
    need(evaluation["scored_known_market_class_checkpoints"]==len(known_types) and
         evaluation["matched_known_market_class_checkpoints"]==sum(x["market_item_exact_match"] for x in known_types),
         "incorrect marketed product category numerator/denominator")
    need(evaluation["scored_known_diagnostic_family_checkpoints"]==len(known_families) and
         evaluation["matched_known_diagnostic_family_checkpoints"]==sum(x["family_exact_match"] for x in known_families),
         "incorrect device family numerator/denominator")
    need(evaluation["weak_keyword_presence_checkpoints"]==sum(x["weak_keyword_relevance_proxy_any"] for x in flattened),
         "weak lexical relevance miscomputed")
    need(evaluation["source_owner_did_not_confirm_final_repair_cases"]==
         sum(not c["oracle"]["owner_reported_complete_fix"] for c in case_map.values()),
         "source-resolved and unresolved reference facts conflated")
    for key in ("physical_power_or_flight_authorized",
                "private_owner_device_data_access_authorized",
                "external_repair_profit_measured"):
        need(evaluation[key] is False,"unqualified field authority")
    need(evaluation["physical_repairs_performed_or_independently_certified_by_HS"]==0 and
         evaluation["source_answers_are_not_independent_laboratory_ground_truth"] is True,
         "source author report falsely classified as tested hardware")
    return {
        "schema_version":"hardware_splicer.untouched_public_repair_holdout_independent_acceptance.v1",
        "baseline_original_CircuitAI_sha":LOCKED_ORIGINAL_BRANCH_SHA,
        "immutable_holdout_git_blob_sha1":LOCKED_BLOB,
        "genuine_new_public_repair_cases":7,
        "genuinely_pre_solution_engine_checkpoints":14,
        "correctly_recomputed_known_market_item_matches":evaluation["matched_known_market_class_checkpoints"],
        "known_market_item_comparisons":evaluation["scored_known_market_class_checkpoints"],
        "correctly_recomputed_known_guide_family_matches":evaluation["matched_known_diagnostic_family_checkpoints"],
        "known_guide_family_comparisons":evaluation["scored_known_diagnostic_family_checkpoints"],
        "no_fault_candidates_emitted":sum(x["original_CircuitAI_evaluator_returned"]["repair_guide"]["top_fault"] is None for x in preds),
        "software_lexical_relevance_is_weak_proxy":True,
        "source_unresolved_repair_cases":evaluation["source_owner_did_not_confirm_final_repair_cases"],
        "source_owner_claims_independently_electrically_verified":False,
        "HS_physically_repaired_a_device":False,
        "HS_flight_or_power_authorized":False
    }

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cases",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    result=verify(a.cases,a.report)
    a.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
