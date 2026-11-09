"""Pre-outcome restoration trial: run HS, then reject device-incompatible faults.

No creator outcome, fix label or transcript is loaded here. The Git commit and
receipt SHA-256 are needed to establish what was predicted before source review.
This is a procedural case, not scientific double-blind validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from hardware_splicer.restoration_video_triage import triage

SCHEMA = "hs.restoration.prospective_prediction.v1"
FORBIDDEN = {
    "root_cause", "reported_outcome", "repair_steps", "source_outcome",
    "answer", "hidden_outcome", "gold", "gold_label", "final_diagnosis",
}
INCOMPATIBLE = {
    "ac_mains_internal_psu": {
        "corroded_battery_contact": "No user-replaceable cell contacts on AC-mains console",
        "open_power_trace": "Baseline hypothesis describes a battery-to-board path",
        "battery_management_fault": "Baseline hypothesis describes a rechargeable pack",
        "power_switch_fault": "Baseline test assumes a slide switch, not a button board",
    }
}
SAFE_CHECKS = [
    "Disconnect AC and visually inspect external power cord/plug only",
    "Document exact externally visible power-on response and history",
    "Use the manufacturer's service guide and qualified technicians for internal faults",
    "Do not probe or rework internal mains PSU without specialist safety procedures",
]


def _canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n").encode("utf-8")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ban_outcomes(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in FORBIDDEN:
                raise ValueError("outcome/gold field forbidden in pre-outcome intake")
            _ban_outcomes(child)
    elif isinstance(value, list):
        for item in value:
            _ban_outcomes(item)


def predict(case_path: Path) -> dict[str, Any]:
    case_bytes = case_path.read_bytes()
    case = json.loads(case_bytes)
    _ban_outcomes(case)
    if case.get("schema") != "hs.restoration.video_blind_intake.v1":
        raise ValueError("invalid typed intake")
    if case.get("followup_codes") or case.get("followup_repair_intake"):
        raise ValueError("no follow-up observations allowed in the pre-outcome stage")
    if case.get("challenge", {}).get("outcome_label_present") is not False:
        raise ValueError("intake not certified outcome-free")
    arch = case.get("device_power", {}).get("architecture")
    if arch not in INCOMPATIBLE:
        raise ValueError("unqualified architecture; cannot issue diagnostic candidates")
    arch_ref = case["device_power"].get("independent_device_reference", "")
    if not arch_ref.startswith("https://"):
        raise ValueError("independent device architecture reference required")
    source = case.get("source_context", {})
    if not str(source.get("url", "")).startswith("https://www.youtube.com/watch?v="):
        raise ValueError("YouTube video provenance missing")
    if not source.get("retrieval_limit"):
        raise ValueError("source retrieval limit missing")

    baseline = triage(case, stage=0)
    ranked = baseline["ranked_differential"]
    banned = INCOMPATIBLE[arch]
    accepted = [h["hypothesis_id"] for h in ranked if h["hypothesis_id"] not in banned]
    rejected = [
        {"hypothesis_id": h["hypothesis_id"], "exclusion_reason": banned[h["hypothesis_id"]]}
        for h in ranked if h["hypothesis_id"] in banned
    ]
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "case_id": case["case_id"],
        "source_url": source["url"],
        "case_sha256": _hash(case_bytes),
        "triage_source_sha256": _hash(Path(triage.__code__.co_filename).read_bytes()),
        "power_architecture": arch,
        "power_architecture_source": arch_ref,
        "stage": "INITIAL_SYMPTOMS_NO_OUTCOME",
        "baseline_hypothesis_ids": [h["hypothesis_id"] for h in ranked],
        "baseline_first_choice": ranked[0]["hypothesis_id"] if ranked else None,
        "rejected_as_device_incompatible": rejected,
        "qualified_hypothesis_ids": accepted,
        "decision": ("ABSTAIN_DEVICE_INCOMPATIBLE" if not accepted
                     else "MEASURE_BEFORE_REPAIR"),
        "next_safe_checks": SAFE_CHECKS,
        "repair_authorized": False,
        "HS_repair_executed": False,
        "outcome_opened_by_predictor": False,
        "independent_measurements_available": False,
        "score_available": False,
        "limitations": "Source-visible procedural split only; not an LLM video diagnosis",
    }
    report["receipt_sha256"] = _hash(_canonical(report))
    return report


def validate_receipt(receipt: dict[str, Any], expected: str) -> None:
    digest = receipt.get("receipt_sha256")
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    if not isinstance(digest, str) or digest != _hash(_canonical(body)):
        raise ValueError("receipt tampering or corruption")
    if expected != digest:
        raise ValueError("receipt not identical to preregistered digest")
    if receipt.get("score_available") is not False or receipt.get("HS_repair_executed") is not False:
        raise ValueError("invalid preregistration status")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seal a symptom-only HS trial")
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = predict(args.case)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "case": report["case_id"],
        "baseline_first_choice": report["baseline_first_choice"],
        "decision": report["decision"],
        "qualified": report["qualified_hypothesis_ids"],
        "PRE_OUTCOME_RECEIPT_SHA256": report["receipt_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
