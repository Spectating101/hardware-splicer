"""Generate neutral same-input prompts for a genuine external diagnostic model.

No source URLs, forum titles, confirmed resolutions, scoring labels or
post-repair outcomes. External providers are NOT called by this script.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def make_model_prompts(cases: list[dict]) -> list[dict]:
    prompts=[]
    for case in cases:
        ev=case["repair_intake"]["path_evidence"]
        prompt={
            "case_id":case["case_id"],
            "role":"You are a hardware repair triage assistant. Do not claim a repair was confirmed.",
            "task":"Recommend first component to CHECK (not necessarily replace) or abstain if insufficient distinguishing evidence.",
            "device_category":case["device_category"],
            "reported_symptoms":case["repair_intake"]["symptoms"],
            "components":[{
                "id":x["id"],"label":x["label"],
                "service_cost_rank":x["service_cost_rank"],
                "reversible_test_available":x["reversible_test_available"],
            } for x in ev["components"]],
            "path_tests":[{
                "outcome":x["outcome"],"observation":x["observation"],
                "path_component_ids":x["path"],
            } for x in ev["path_tests"]],
            "ineffective_interventions":[{
                "component_id":x["component_id"],
                "result":"no_change"
            } for x in ev.get("interventions",[])],
            "reply_format":{"candidate_id":"component ID from supplied list or null","confidence":"low|medium|high","test_before_replacement":"one short reversible check","abstain_reason":"if candidate_id null, why"},
            "rules":[
                "Evidence is not a confirmed diagnosis.",
                "Do not infer measured values or make safety claims.",
                "Prefer a discriminating non-destructive test before proposing purchases.",
                "Do not invent tests, repair outcomes or vendor specifications.",
                "Output one JSON object with reply_format fields only.",
            ],
        }
        serialized=json.dumps(prompt,sort_keys=True)
        for prohibited in ("https://","ifixit","ground_truth","reported_resolution_component","poster_confirmed_fix","source_url"):
            if prohibited in serialized.lower():
                raise ValueError("potential evaluation leakage in external prompt: "+prohibited)
        prompts.append(prompt)
    return prompts


if __name__=="__main__":
    x=json.loads((ROOT/"blind_observations.json").read_text(encoding="utf-8"))
    prompts=make_model_prompts(x["cases"])
    out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"external_same_input_prompts.jsonl"
    contents="".join(json.dumps(p,sort_keys=True)+"\n" for p in prompts)
    out.write_text(contents,encoding="utf-8")
    print(json.dumps({"cases":len(prompts),"output":str(out),"sha256":hashlib.sha256(contents.encode()).hexdigest(),
                      "external_model_invoked":False},indent=2))
