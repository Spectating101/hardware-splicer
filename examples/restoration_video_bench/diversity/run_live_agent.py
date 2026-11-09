"""Run real local Ollama on HS's frozen, outcome-free repair video packets.

Never loads the PR #321 postreview outcomes; deliberately requires the
pre-outcome manifest and source hashes from PR #320. Failing to obtain usable
inference is a measured failure, never a fabricated diagnostic plan.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from hardware_splicer.restoration_reasoning_agent import build_context, diagnose, agy_chat, ollama_chat
from hardware_splicer.restoration_caption_ingest import caption_case_context
from hardware_splicer.repair_intake import extract_repair_context

HERE = Path(__file__).resolve().parent
PACKET = HERE / "evidence/open_agent_packet.json"
CASES = HERE / "cases.json"


def prepare(packet_file: Path = PACKET, cases_file: Path = CASES) -> list[dict]:
    data = json.loads(packet_file.read_text(encoding="utf-8"))
    manifest = json.loads(cases_file.read_text(encoding="utf-8"))
    assert data["schema"] == "hs.restoration.open_agent_packet.v1"
    assert manifest["schema"] == "hs.restoration.raw_video_diversity.v1"
    by_id = {c["id"]: c for c in manifest["cases"]}
    if set(by_id) != {t["case_id"] for t in data["tasks"]}:
        raise ValueError("sealed packet and cases differ")
    contexts=[]
    for task in data["tasks"]:
        c = by_id[task["case_id"]]
        if task["source_url"] != c["source_url"]:
            raise ValueError("source video does not match sealed packet")
        symptoms = [c["title_symptom"], *c["opening_observations"]]
        if task["symptoms_and_opening_only"] != symptoms:
            raise ValueError("symptom text was changed after freezing")
        if task["hazards"] != c["hazards"]:
            raise ValueError("hazard list was changed after freezing")
        native = {"symptoms": symptoms, "device_hint": c["device"]}
        assert extract_repair_context({"repair_intake": native})["symptoms"] == symptoms
        ctx = build_context(
            case_id=c["id"], device=c["device"], repair_intake=native,
            source_url=c["source_url"], hazards=c["hazards"],
            evidence_stage=c["evidence_stage"],
        )
        contexts.append(ctx)
    return contexts


def run(case_ids: list[str], *, model: str, timeout_s: int,
        provider: str = "agy", caption_vtt: Path | None = None,
        cutoff_s: int = 120) -> dict:
    all_cases = prepare()
    selected = [c for c in all_cases if c["case_id"] in case_ids]
    if len(selected) != len(set(case_ids)):
        raise ValueError("unknown or duplicate requested case")
    if caption_vtt is not None:
        if len(selected) != 1:
            raise ValueError("raw WebVTT trial requires exactly one selected case")
        original = next(c for c in json.loads(CASES.read_text())["cases"]
                        if c["id"] == selected[0]["case_id"])
        if original["video_id"] not in caption_vtt.name:
            raise ValueError("caption file name does not match source video ID")
        selected = [caption_case_context(
            case_id=original["id"], device=original["device"],
            title_symptom=original["title_symptom"],
            video_url=original["source_url"], hazards=original["hazards"],
            vtt_path=caption_vtt, cutoff_s=cutoff_s,
        )]
    if provider not in ("agy","ollama"):
        raise ValueError("only explicit Antigravity or loopback Ollama allowed")
    backend = agy_chat if provider == "agy" else ollama_chat
    results=[diagnose(c, model=model, timeout_s=timeout_s, inference=backend) for c in selected]
    return {
        "schema": "hs.restoration.live_local_inference_batch.v1",
        "mode": "actual_optiplex_ollama_local_llm_not_gpt6_control",
        "preoutcome_inputs_only": True,
        "no_gold_files_loaded": True,
        "selected_count": len(results),
        "valid_plans": sum(r["status"] in (
            "proposed_unverified_differential","model_abstained") for r in results),
        "provider": "agy_antigravity_subscription_cli" if provider == "agy" else "ollama_local_loopback",
        "model_requested": model,
        "results": results,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--case-id",action="append",dest="case_ids",required=True)
    p.add_argument("--provider",choices=("agy","ollama"),default="agy")
    p.add_argument("--model",default=None)
    p.add_argument("--timeout",type=int,default=90)
    p.add_argument("--captions-vtt",type=Path,help="Optional locally supplied real auto-caption VTT")
    p.add_argument("--cutoff-seconds",type=int,default=120)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    model = a.model or ("gemini-3.8-flash-low" if a.provider=="agy" else "qwen2.5:1.5b-instruct")
    report=run(a.case_ids,model=model,timeout_s=a.timeout,
               provider=a.provider,caption_vtt=a.captions_vtt,cutoff_s=a.cutoff_seconds)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({
        "provider": report["provider"],"cases":report["selected_count"],
        "usable_diagnostics":report["valid_plans"],
        "statuses": {r["case_id"]:r["status"] for r in report["results"]}
    },indent=2))


if __name__=="__main__":
    main()
