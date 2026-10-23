"""Score a real external model's frozen same-input predictions.

Do NOT put reference answers, source URLs or solution titles into the
model prompts. This script does not contact any service and cannot turn a
heuristic baseline into a market-comparison result by renaming it.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path

from evaluate import run

ROOT=Path(__file__).resolve().parent


def score_predictions(root: Path, prediction_file: Path) -> dict:
    base=run(root)
    raw=prediction_file.read_bytes()
    supplied=json.loads(raw)
    provider=str(supplied.get("provider") or "").strip()
    model=str(supplied.get("model") or "").strip()
    if not provider or not model:
        raise ValueError("real provider and model/version identity required")
    if provider.lower() in {"dummy","synthetic","hs","naive","mock","example"}:
        raise ValueError("do not misrepresent internal or fictional baselines as external systems")
    predictions=supplied.get("predictions")
    if not isinstance(predictions,list) or len(predictions)!=base["totals"]["all_cases"]:
        raise ValueError("one real model response is required per input case")
    cases=json.loads((root/"blind_observations.json").read_text(encoding="utf-8"))["cases"]
    allowed={c["case_id"]:{x["id"] for x in c["repair_intake"]["path_evidence"]["components"]} for c in cases}
    predicted={}
    for entry in predictions:
        cid=entry.get("case_id")
        if cid not in allowed or cid in predicted:
            raise ValueError("unknown or repeated case id")
        proposed=entry.get("candidate_id")
        if proposed is not None and proposed not in allowed[cid]:
            raise ValueError("prediction uses part ID not provided to model")
        if not entry.get("transcript_sha256") or len(str(entry["transcript_sha256"]))!=64:
            raise ValueError("attach SHA256 of actual model transcript, not invented results")
        predicted[cid]=proposed
    if set(predicted)!=set(allowed):
        raise ValueError("missing cases")
    # Only NOW load reported resolutions. The scored model file is sealed before scoring.
    gold={x["case_id"]:x for x in json.loads((root/"sealed_outcomes.json").read_text(encoding="utf-8"))["labels"]}
    eligible=[cid for cid,v in base["cases"].items() if v["score_as_original_owner_confirmed"] and v["admissible_route_evidence"]]
    return {
        "provider":provider,
        "model":model,
        "predictions_file_sha256":hashlib.sha256(raw).hexdigest(),
        "transcripts_supplied_but_not_replayed_or_authenticated":True,
        "genuinely_external_model_execution_verified":False,
        "owner_confirmed_with_eligible_paths":len(eligible),
        "external_top1_matches":sum(predicted[cid]==gold[cid]["reported_resolution_component"] for cid in eligible),
        "hs_top1_matches_on_same_input":base["totals"]["hs_confirmed_top1_matches_admissible"],
        "external_abstentions":sum(v is None for v in predicted.values()),
        "warning":"Results supplied by user/provider; independent model execution authentication required before public competitive claims.",
    }


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: python score_external_baseline.py <actual_model_predictions.json>")
    print(json.dumps(score_predictions(ROOT,Path(sys.argv[1])),indent=2))
