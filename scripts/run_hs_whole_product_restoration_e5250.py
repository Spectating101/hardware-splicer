#!/usr/bin/env python3
"""Execute a real-source whole-product restoration dossier on existing HS modules.

Retrospective source replay, never a prospective/blind prediction or physical repair.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/whole_product_restorations/dell_latitude_e5250_technician_case_2026.json"

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

def validate(case):
    assert case["schema_version"] == "hs.repair_restoration_episode.v1"
    assert case["research_context"]["not_a_frozen_unknown_holdout"] is True
    assert case["scope_control"]["retrospective_not_blind"] is True
    assert case["scope_control"]["physically_repaired_by_HS"] is False
    assert case["scope_control"]["HS_performed_any_measurement"] is False
    events=case["chronology"]
    assert [x["id"] for x in events] == ["T0","T1","T2","T3","T4","T5"]
    assert [x["allowed_in_engine"] for x in events] == [True]*5+[False]
    measured=[m for e in events for m in e["source_measurements"]]
    assert len(measured)==7
    assert all(m["reporter"]=="original_repair_technician" and m["independent_HS_measurement"] is False for m in measured)
    assert all(i["approved_by_HS"] is False for i in case["source_reported_interventions"])
    assert all(x["approved_purchase"] is False and x["cost_estimate"] is None for x in case["conditional_bom"])
    assert all(x["HS_observed"] is False and x["qualified_independent_retest"] is False for x in case["acceptance_requirements"])

def actual_engine_replay(case):
    sys.path.insert(0,str(ROOT/"apps/circuit-ai"))
    from src.intelligence.repair_case_evaluator import RepairCaseEvaluator
    from src.intelligence.board_session_store import BoardSessionStore
    trace=[]
    cumulative=[]
    with tempfile.TemporaryDirectory(prefix="hs_e5250_") as folder:
        evaluator=RepairCaseEvaluator(session_store=BoardSessionStore(Path(folder)/"sessions.json"))
        for event in case["chronology"]:
            if not event["allowed_in_engine"]:
                continue
            cumulative.extend(event["previously_known_observations"])
            inp={
                "case_id":case["case_id"]+"__"+event["id"],
                "title":case["title"],
                "device_hint":"Dell Latitude E5250 business laptop",
                "symptoms":list(cumulative),
                "source_url":case["source"]["article_url"],
                "source_kind":"public_technician_retrospective_chronological_replay",
                "observed_actions":[],
                "notes":"Third-party technician observations only. HS has not tested this hardware.",
                "expected_lane":"",
            }
            response=evaluator.evaluate_case(inp,commit_session=False)
            guide=evaluator.encyclopedia.generate(
                analysis={},symptoms=inp["symptoms"],device_hint=inp["device_hint"])
            if response["physical_repair_ready"] is not False:
                raise AssertionError("software score improperly promoted to physical repair")
            trace.append({
                "stage_id":event["id"],
                "stage_title":event["title"],
                "real_engine_input":inp,
                "real_engine_input_sha256":sha256(json.dumps(inp,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()),
                "real_engine_output":response,
                "real_guide_hypotheses":(guide.get("fault_candidates") or [])[:5],
                "real_guide_evidence_next":(guide.get("evidence_to_collect_next") or [])[:8],
                "real_guide_safety_profile":guide.get("safety_profile"),
                "source_measurement_ids_known_at_this_stage":[
                    m["id"] for past in case["chronology"]
                    if past["id"]<=event["id"] for m in past["source_measurements"]],
                "source_final_outcome_given_to_engine":False,
                "HS_measured_or_modified_hardware":False,
            })
    return trace

def disposition(case,trace,source_sha):
    requirements=case["acceptance_requirements"]
    return {
        "schema_version":"hs.whole_product_restoration_disposition.v1",
        "case_id":case["case_id"],
        "original_source_sha256":source_sha,
        "demonstration_kind":"retrospective_public_professional_technician_case",
        "actual_engine_evaluation_count":len(trace),
        "source_reported_numeric_readings":sum(len(x["source_measurements"]) for x in case["chronology"]),
        "HS_instrumented_measurement_count":0,
        "source_reported_physical_interventions":len(case["source_reported_interventions"]),
        "HS_performed_physical_interventions":0,
        "source_reported_functional_gates":sum(x["source_reported"] for x in requirements),
        "source_functional_gate_denominator":len(requirements),
        "HS_independently_verified_functional_gates":0,
        "component_diagnosis_accuracy":"UNSCORABLE retrospective source case, no independent prospective root truth",
        "physical_repair_authority":"BLOCKED",
        "full_product_customer_release":"BLOCKED",
        "part_purchase_authority":"BLOCKED",
        "reported_source_outcome":"technician reports startup to BitLocker prompt and resumed power cycling",
        "unverified_acceptance_gates":[r["id"] for r in requirements if not r["source_reported"]],
        "missing_component_replacement_specs":next(x["missing_spec"] for x in case["conditional_bom"] if x["id"]=="B4"),
        "third_party_outcome_and_intervention_never_supplied_as_prediction_labels":True,
        "commercial_costs":"UNKNOWN no valid parts quote, labor hours or verified working-condition resale price",
        "energized_current_injection_RTC_hotplug_and_flammable_solvent_authorized":False,
        "stage_predictions":[
            {"stage":s["stage_id"],"market_class":s["real_engine_output"]["coverage"]["top_item"],
             "diagnostic_family":s["real_engine_output"]["repair_guide"]["family"],
             "top_fault":s["real_engine_output"]["repair_guide"]["top_fault"],
             "software_workflow_verdict":s["real_engine_output"]["verdict"],
             "physical_repair_ready":s["real_engine_output"]["physical_repair_ready"]}
            for s in trace],
    }

def render_dossier(case,trace,graded,source_sha):
    lines=[
        "# HS whole-product restoration: Dell Latitude E5250",
        "",
        "**Study:** Retrospective, source-reported real professional repair — not HS physical work or prospective blind diagnosis.",
        "**Outcome:** Technician reports boot to BitLocker prompt, repeated power cycling; customer-grade return-to-use is not proven.",
        "",
        "Source: "+case["source"]["article_url"],
        "Linked repair video: "+case["source"]["video_url"],
        "Source SHA-256: "+source_sha,
        "Device serial, exact board revision, original schematic, component package/capacitance: not supplied.",
        "",
        "## Actual HS analysis, chronologically replayed from source observations",
        "",
        "| Stage | Evidence available by then | Real HS leading fault | HS software verdict |",
        "| --- | --- | --- | --- |",
    ]
    for r in trace:
        e=next(x for x in case["chronology"] if x["id"]==r["stage_id"])
        o=r["real_engine_output"]
        lines.append("| "+r["stage_id"]+" | "+e["title"]+" | "+str(o["repair_guide"]["top_fault"])+" | "+str(o["verdict"])+" |")
    lines += [
        "",
        "The table is actual unchanged RepairCaseEvaluator output, retained even when incorrect.",
        "All inputs stop before T5 final source acceptance. The example was selected retrospectively, so it is not an unseen benchmark.",
        "",
        "## Original technician measurement ledger (none obtained by HS)",
        "",
        "| Evidence | Timepoint | Measurement as reported | Recorded state |",
        "| --- | --- | --- | --- |",
    ]
    for e in case["chronology"]:
        for m in e["source_measurements"]:
            lines.append("| "+m["id"]+" | "+e["id"]+" | "+str(m["value"])+" "+m["unit"]+" | "+m["condition"]+" |")
    lines += [
        "",
        "Under attempted board current injection, voltage reportedly fell nearly to zero; no exact voltage reading was documented.",
        "A current-sense resistor first appeared hot but was merely carrying fault current. It was NOT the source's actual failed component.",
        "",
        "## Conditional engineering and parts package",
        "",
        "| ID | Instrument/part/reference | Purchase approved |",
        "| --- | --- | --- |",
    ]
    for x in case["conditional_bom"]:
        lines.append("| "+x["id"]+" | "+x["name"]+" | NO |")
    lines += [
        "",
        "MLCC replacement blocked pending: "+", ".join(graded["missing_component_replacement_specs"])+".",
        "A donor MacBook capacitor described in the source is not proof of compatible ratings. No priced BOM or invented margin.",
        "",
        "## Actual technician interventions (historical evidence only)",
        "",
    ]
    for x in case["source_reported_interventions"]:
        lines.append("- "+x["id"]+" ["+x["stage"]+"]: "+x["action"]+"; permission="+x["authorization"]+".")
    lines += [
        "",
        "SAFETY STOP: Source-described petrol/flammable solvent heated-part methods, uncontrolled rail injection, energized RTC-battery reconnection, and speculative donor-part substitution are not authorized. Any powered motherboard faultfinding or rework requires a qualified technician using a safe model-specific procedure.",
        "",
        "## Full-product acceptance, rather than a software pass",
        "",
        "| Gate | Technician reported success | Independent HS verification |",
        "| --- | --- | --- |",
    ]
    for x in case["acceptance_requirements"]:
        lines.append("| "+x["name"].replace("_"," ")+" | "+("yes" if x["source_reported"] else "not documented")+" | NO |")
    lines += [
        "",
        "Source-reported functional gates: "+str(graded["source_reported_functional_gates"])+"/"+str(graded["source_functional_gate_denominator"])+". HS independently verified: 0/8.",
        "BitLocker prompt means the operating system got far enough to present the encrypted drive unlock interface; it does not verify actual data access, battery cycles, thermals or owner acceptance.",
        "",
        "## Product release disposition",
        "",
        "- Boot restoration: REPORTED BY SOURCE.",
        "- Actual HS fault identification: stage-by-stage raw predictions in WHOLE_PRODUCT_ENGINE_TRACE.json; do not infer success from the selected final story.",
        "- HS hardware measurements: 0. HS reworked components: 0.",
        "- Board/parts engineering: conditional only, component specification remains unavailable.",
        "- Product return-to-use and resale: BLOCKED until battery, thermal, power-cycle, RTC, keyboard, display, ports, fan, mechanical safety, secure data-access and customer acceptance evidence.",
        "- Economic opportunity: no prices, credible labor time or parts reference, so profitability deliberately NOT ESTIMATED.",
        "",
        "## Next physical acceptance pilot",
        "",
        "Request owner consent, correct Dell board revision, technician photos, calibrated voltage/current logs, verified spare-part specification and service guidance. Use the same staged intake/measurement/decision and final release gates for a genuine device. Do not authorize physical work based on this public repair replay alone.",
        "",
    ]
    return "\n".join(lines)

def main():
    a=argparse.ArgumentParser()
    a.add_argument("--case",type=Path,default=SOURCE)
    a.add_argument("--out",type=Path,default=ROOT/".cache/hs_e5250_product_restoration")
    opts=a.parse_args()
    case= json.loads(opts.case.read_text())
    validate(case)
    source_sha=sha256(opts.case.read_bytes())
    opts.out.mkdir(parents=True,exist_ok=True)
    trace=actual_engine_replay(case)
    graded=disposition(case,trace,source_sha)
    save_json(opts.out/"WHOLE_PRODUCT_ENGINE_TRACE.json",{"source_sha256":source_sha,"actual_existing_engine":True,"stages":trace})
    save_json(opts.out/"WHOLE_PRODUCT_DISPOSITION.json",graded)
    save_json(opts.out/"WHOLE_PRODUCT_SOURCE_LEDGER.json",
              {"source":case["source"],"source_sha256":source_sha,"device":case["device"],
               "source_chronology":case["chronology"],
               "source_interventions_not_HS_actions":case["source_reported_interventions"]})
    (opts.out/"WHOLE_PRODUCT_RESTORATION_DOSSIER.md").write_text(render_dossier(case,trace,graded,source_sha))
    manifest={"schema_version":"hs.whole_product_restoration_manifest.v1",
              "case_id":case["case_id"],"source_sha256":source_sha,
              "artifacts":{},"HS_performed_physical_repair":False}
    for name in ("WHOLE_PRODUCT_ENGINE_TRACE.json","WHOLE_PRODUCT_DISPOSITION.json",
                 "WHOLE_PRODUCT_SOURCE_LEDGER.json","WHOLE_PRODUCT_RESTORATION_DOSSIER.md"):
        manifest["artifacts"][name]=sha256((opts.out/name).read_bytes())
    save_json(opts.out/"WHOLE_PRODUCT_MANIFEST.json",manifest)
    print(json.dumps({
        "case_id":case["case_id"],"real_engine_stage_count":len(trace),
        "real_engine_top_fault_by_stage":{s["stage_id"]:s["real_engine_output"]["repair_guide"]["top_fault"] for s in trace},
        "real_engine_verdict_by_stage":{s["stage_id"]:s["real_engine_output"]["verdict"] for s in trace},
        "source_measurements":graded["source_reported_numeric_readings"],
        "source_reported_functional_gates":[graded["source_reported_functional_gates"],graded["source_functional_gate_denominator"]],
        "HS_physical_acceptance":0,"product_release":"BLOCKED",
        "artifact_names":list(manifest["artifacts"])},indent=2))

if __name__=="__main__":main()
