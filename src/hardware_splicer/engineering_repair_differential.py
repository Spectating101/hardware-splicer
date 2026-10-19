"""Manufacturer-scoped *hypothesis* ranking for original-function repair.

We may know family documentation and a seller-described symptom without owning
the specimen. Report alternative diagnoses and discriminating evidence, never
an asserted root cause, a pinout, energized test instruction or repair success.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_PROFILE_DIR = Path(__file__).parent / "data" / "repair_diagnostic_profiles"
SCHEMA = "hardware_splicer.repair_differential.v1"


def _bounded_symptoms(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [s.strip() for s in value[:32] if isinstance(s, str) and s.strip()]


def repair_differential(mission: Mapping[str, Any], repair_intake: Mapping[str, Any] | None = None) -> dict[str, Any]:
    if mission.get("type") != "restorative_repair":
        raise ValueError("repair differential requires restorative_repair mission")
    notes = repair_intake if isinstance(repair_intake, Mapping) else {}
    symptoms = _bounded_symptoms(notes.get("symptoms"))
    seller_text = " ".join([mission["original_device"], *symptoms, str(notes.get("operator_notes") or "")]).lower()
    profiles = []
    for path in sorted(_PROFILE_DIR.glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        tokens = profile.get("model_match_tokens") or []
        if any(isinstance(token, str) and token.lower() in mission["original_device"].lower() for token in tokens):
            profiles.append(profile)
    if len(profiles) != 1:
        return {
            "schema_version": SCHEMA,
            "profile_id": None,
            "source_status": "no_unique_exact_family_profile",
            "alternative_hypotheses": [],
            "next_evidence_requests": [
                "Identify actual device model, revision and interface, and locate suitable primary documentation",
                "Record physical baseline and symptoms before selecting a repair procedure"
            ],
            "root_cause_verified": False,
            "repair_procedure_verified": False,
            "may_perform_repair_or_power": False,
        }

    profile = profiles[0]
    alternatives = []
    for item in profile["hypotheses"]:
        indicators = item.get("indicators") or []
        matched = [x for x in indicators if isinstance(x, str) and x in seller_text]
        # A reported concrete mechanical break is more discriminating than
        # generic device/task words such as "scan" or "barcode".
        indicator_specificity = sum(
            5 if x in {"cut cable", "cable cut", "severed", "cut-cable"}
            else 1 for x in matched
        )
        alternatives.append({
            "hypothesis_id": item["id"],
            "hypothesis": item["statement"],
            "evidence_status": "unverified_hypothesis",
            "seller_indicators_matched": matched,
            "seller_specificity_rank_not_probability": indicator_specificity,
            "priority": "investigate_early" if matched else "alternative_possible",
            "discriminating_evidence_needed": list(item["discriminating_evidence"]),
            "supported_diagnosis": False,
            "root_cause_proven": False,
        })
    alternatives.sort(key=lambda x: (-x["seller_specificity_rank_not_probability"], x["hypothesis_id"]))
    return {
        "schema_version": SCHEMA,
        "profile_id": profile["profile_id"],
        "manufacturer_reference": profile["manufacturer_reference"],
        "family_documentation_facts": list(profile["manufacturer_facts"]),
        "reported_symptoms_unverified": symptoms,
        "alternative_hypotheses": alternatives,
        "next_evidence_requests": list(dict.fromkeys(
            step for hypothesis in alternatives
            for step in hypothesis["discriminating_evidence_needed"]
        )),
        "source_status": "manufacturer_family_manual_plus_unverified_seller_report",
        "root_cause_verified": False,
        "repair_procedure_verified": False,
        "original_device_function_verified": False,
        "may_perform_repair_or_power": False,
    }
