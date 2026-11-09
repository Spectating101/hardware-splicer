"""Nine-device source-separated restoration flexibility probe.

Runs the REAL native HS repair_intake and original source-linked triage. Nothing
in here guesses a repair outcome or manufactures symptom codes to get a good
score. Neither this module nor its cases folder imports creator results.

The human-paraphrased early observations come from public auto-captions within
the stated time window; no video-frame analysis or ASR was run by HS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from hardware_splicer.repair_intake import extract_repair_context
from hardware_splicer.restoration_video_triage import triage

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases.json"
SCHEMA = "hs.restoration.raw_diversity_baseline.v1"
BAD_KEYS = {
    "root_cause", "gold", "outcome", "fix", "repair_steps", "answer",
    "creator_outcome", "hidden_outcomes", "conclusion", "after_repair",
}

def _canonical(x: Any) -> bytes:
    return (json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n").encode("utf-8")

def digest(x: Any) -> str:
    return hashlib.sha256(_canonical(x)).hexdigest()

def forbid_outcome_fields(x: Any) -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            if k.lower() in BAD_KEYS:
                raise ValueError("outcome information is prohibited before sealing")
            forbid_outcome_fields(v)
    elif isinstance(x, list):
        for v in x:
            forbid_outcome_fields(v)

def intake(case: dict, *, title_only: bool = False) -> dict:
    return {
        "schema": "hs.restoration.video_blind_intake.v1",
        "case_id": case["id"],
        "device": case["device"],
        "repair_intake": {
            "symptoms": ([case["title_symptom"]] if title_only else
                         [case["title_symptom"], *case["opening_observations"]]),
            "device_hint": case["device"],
            "when_it_fails": case["title_symptom"],
        },
        "source_context": {
            "url": case["source_url"],
            "cutoff_seconds": 0 if title_only else case["caption_cutoff_s"],
            "kind": ("title_only" if title_only else case["evidence_stage"]),
        },
        # Raw natural language ON PURPOSE; no hand-supplied initial_codes.
    }

def load_cases() -> dict:
    data = json.loads(CASES.read_text(encoding="utf-8"))
    if data.get("schema") != "hs.restoration.raw_video_diversity.v1":
        raise ValueError("wrong candidate set")
    if len(data["cases"]) != 9:
        raise ValueError("expected nine distinctly sourced cases")
    forbid_outcome_fields(data)
    ids = [c["id"] for c in data["cases"]]
    urls = [c["source_url"] for c in data["cases"]]
    groups = [c["category"] for c in data["cases"]]
    if not (len(set(ids)) == len(set(urls)) == len(set(groups)) == 9):
        raise ValueError("duplicate case, URL or device fault domain")
    for c in data["cases"]:
        assert c["source_url"] == "https://www.youtube.com/watch?v=" + c["video_id"]
        if c["caption_cutoff_s"]:
            assert 0 < c["caption_cutoff_s"] <= 120
            assert c["opening_observations"]
        if not c["hazards"]:
            raise ValueError("unreviewed hazard list")
    return data

def evaluate_raw() -> dict:
    data = load_cases()
    rows = []
    for c in data["cases"]:
        phases = {}
        for phase, title_only in (("title", True), ("opening", False)):
            obj = intake(c, title_only=title_only)
            context = extract_repair_context({"repair_intake": obj["repair_intake"]})
            assert context["symptoms"] and context["device_hint"] == c["device"]
            try:
                prediction = triage(obj, 0)
                outcome = {
                    "accepted_raw_text": True,
                    "top_ids": [h["hypothesis_id"] for h in
                                prediction["ranked_differential"]],
                }
            except (ValueError, KeyError) as exc:
                outcome = {
                    "accepted_raw_text": False,
                    "failure_type": type(exc).__name__,
                    "error": str(exc),
                }
            phases[phase] = {
                "input_sha256": digest(obj),
                "native_repair_intake_normalized": True,
                "raw_legacy_triage": outcome,
            }
        rows.append({
            "case_id": c["id"], "source_url": c["source_url"],
            "category": c["category"], "evidence_stage": c["evidence_stage"],
            "phases": phases,
        })
    return {
        "schema": SCHEMA,
        "case_count": len(rows),
        "unique_fault_domains": len(set(r["category"] for r in rows)),
        "native_repair_intake_accepted": sum(
            r["phases"]["opening"]["native_repair_intake_normalized"] for r in rows
        ),
        "legacy_triage_accepted_raw_text": sum(
            r["phases"]["opening"]["raw_legacy_triage"]["accepted_raw_text"] for r in rows
        ),
        "title_only_raw_supported": sum(
            r["phases"]["title"]["raw_legacy_triage"]["accepted_raw_text"] for r in rows
        ),
        "assessment": (
            "Measures free-text compatibility of the PR318 rule-based triage "
            "entrypoint ONLY. Not a test of every HS agent, not video vision, "
            "not a diagnostic accuracy score."
        ),
        "creator_outcomes_read": False,
        "post_repair_evidence_used": False,
        "physical_hardware_touched": False,
        "candidate_set_sha256": digest(data),
        "cases": rows,
    }

def generate_open_agent_packet() -> dict:
    cases = load_cases()
    tasks = []
    for c in cases["cases"]:
        obj = intake(c)
        ctx = extract_repair_context({"repair_intake": obj["repair_intake"]})
        tasks.append({
            "case_id": c["id"],
            "device": ctx["device_hint"],
            "source_url": c["source_url"],
            "symptoms_and_opening_only": ctx["symptoms"],
            "hazards": c["hazards"],
            "intake_sha256": digest(obj),
            "instructions": (
                "Do not browse the video outcome or infer a repair was completed. "
                "Generate <=3 distinct mechanisms with falsifiable observations; "
                "give the single best safe next discriminating check; distinguish "
                "confirmed vs suggested facts; abstain when evidence insufficient. "
                "No physical mains probing, lithium pack work, powered laser, "
                "irreversible parts replacement or data wiping."
            )
        })
    return {
        "schema": "hs.restoration.open_agent_packet.v1",
        "task_count": len(tasks),
        "model_access_not_implied": True,
        "tasks": tasks,
    }

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--agent-packet", type=Path)
    a = p.parse_args()
    result = evaluate_raw()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if a.agent_packet:
        a.agent_packet.parent.mkdir(parents=True, exist_ok=True)
        a.agent_packet.write_text(
            json.dumps(generate_open_agent_packet(), indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "cases": result["case_count"],
        "fault_domains": result["unique_fault_domains"],
        "native_intakes": result["native_repair_intake_accepted"],
        "raw_rule_engine_accepted": result["legacy_triage_accepted_raw_text"],
        "creator_outcomes_read": False,
    }, indent=2))

if __name__ == "__main__":
    main()
