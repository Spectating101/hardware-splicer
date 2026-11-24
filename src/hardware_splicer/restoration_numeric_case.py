"""Same source claims in plain/model and HS numeric-provenance arms.

No post-repair outcome data is loaded or trusted. Both arms receive the
same quantitative statements as E-coded text; HS also receives the REAL
native-engineering-source-graph provenance, condition keys and authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .repair_intake import extract_repair_context
from .restoration_reasoning_agent import SCHEMA, sha
from .restoration_schematic_grounding import build_case_context

PS5_URL="https://www.youtube.com/watch?v=xbp8lIggbxY"
GAMEBOY_CASE="dmg_reported_battery_only_failure"
PS5_CASE="ps5_pro_no_power_hdmi"
VALID_CASES={GAMEBOY_CASE,PS5_CASE}


def _reference_relation(claim: Mapping[str,Any])->str:
    """Typed comparator from an already source-verified anchor."""
    if claim["claim_type"]!="published_reference_expectation":
        return "reported_scalar"
    if claim["upper_value"] is not None:
        return "expected_range"
    anchor=claim["source_anchor"].lower()
    if "at least" in anchor:
        return "recommended_minimum"
    if "below" in anchor:
        return "failure_below"
    if "above" in anchor:
        return "failure_above"
    return "unclassified_public_reference"


def _readable_claim(claim: Mapping[str,Any], *, render_version:str)->str:
    # Every field is already validated and anchored to the actual source.
    # Do not infer an observed result from a published expected range.
    number=(f'{claim["value"]} to {claim["upper_value"]} {claim["unit"]}'
            if claim["upper_value"] is not None
            else f'{claim["value"]} {claim["unit"]}')
    if claim["claim_type"]=="published_reference_expectation":
        if render_version=="legacy_v1":
            # Frozen PR #329 measurement prompts must remain reproducible.
            desc=f"an expected/reference value of {number}"
        else:
            relation=_reference_relation(claim)
            if relation=="expected_range":
                desc=f"an expected open-circuit RANGE of {number}"
            elif relation=="recommended_minimum":
                desc=f"a recommended MINIMUM of at least {number}"
            elif relation=="failure_below":
                desc=f"a failure-warning threshold BELOW {number}"
            elif relation=="failure_above":
                desc=f"a failure-warning threshold ABOVE {number}"
            else:
                desc=f"an unclassified reference value of {number}"
        return (
            f"Public repair article RECOMMENDS {desc} for {claim['condition_description']}. "
            "This is NOT a measurement from this particular console, and "
            "is NOT a manufacturer-verified specification."
        )
    return (
        f"Video creator REPORTS {number} while {claim['condition_description']}. "
        "This is an unverified narrated meter reading, not an independent "
        "HS instrument observation."
    )


def build_numeric_case_context(
    ledger:Mapping[str,Any], *, case_id:str, assisted:bool,
    render_version:str="semantic_v2"
)->dict[str,Any]:
    if render_version not in ("legacy_v1","semantic_v2"):
        raise ValueError("unrecognized source claim rendering contract")
    if case_id not in VALID_CASES:
        raise ValueError("not an authorized no-outcome real source pilot")
    if ledger.get("schema")!="hs.restoration.source_numeric_evidence_ledger.v1":
        raise ValueError("numeric evidence not sourced through HS ledger")
    claims=[c for c in ledger["claims"] if c["case_id"]==case_id]
    if not claims:
        raise ValueError("no source-verified numeric claims for device")
    if any(c["measured_by_HS"] or c["target_board_physically_verified"]
           or c["authority"]!="declared" for c in claims):
        raise ValueError("unverified readings promoted to false independent truth")
    if case_id==GAMEBOY_CASE:
        # The previous Game Boy intake supplied board label as REPORT only.
        context=build_case_context(reported_board_revision="DMG-CPU-06")
    else:
        native=extract_repair_context({"repair_intake":{
            "device_hint":"Sony PlayStation 5 Pro console",
            "symptoms":[
                "Video creator reports PS5 Pro has no startup power.",
                "Separately reports visible physical HDMI port damage.",
            ],
        }})
        base=[
            {"id":f"E{i+1}","kind":"creator_reported_symptom",
             "source":PS5_URL,"text":str(t),
             "stage":"opening_video_symptoms_without_creator_repair"}
            for i,t in enumerate(native["symptoms"])
        ]
        context={
            "schema":SCHEMA,"case_id":case_id,"device":native["device_hint"],
            "source_url":PS5_URL,
            "native_HS_repair_intake_schema":native["schema_version"],
            "hazards":["internal_mains_power_supply","unverified_high_energy_electronics",
                       "repair_data_and_parts_loss"],
            "evidence_stage":"opening_and_reported_numeric_claims_pre_repair",
            "preceding_receipt_sha256":None,
            "evidence":base,"evidence_sha256":sha(base),
            "repair_authorized":False,
        }
    original_len=len(context["evidence"])
    for j,claim in enumerate(claims,original_len+1):
        if claim["source_url"]!=context["source_url"]:
            raise ValueError("numeric claim source does not match the selected device")
        context["evidence"].append({
            "id":f"E{j}",
            "kind":claim["claim_type"],
            "text":_readable_claim(claim,render_version=render_version),
            "source":claim["source_url"],
            "stage":"source_hashed_numeric_claim_not_independently_measured",
            "source_claim_id":claim["claim_id"],
            "source_artifact_sha256":claim["source_sha256"],
        })
    context["evidence_sha256"]=sha(context["evidence"])
    if assisted:
        context["numeric_source_tool"]={
            "schema":"hs.restoration.per_device_numeric_evidence_tool.v1",
            "case_id":case_id,
            "source_manifest_sha256":ledger["source_manifest_sha256"],
            "HS_real_source_graph_sha256":ledger["native_HS_source_graph_sha256"],
            "per_case_claim_sha256":sha(claims),
            "claims":deepcopy(claims),
            "source_authority_ceiling":"declared",
            "unresolved_source_ids":[
                "no_component_datasheet_provided",
                "no_verified_meter_observations",
                "no_independent_bench_measurement_or_instrument_log",
                "board_revision_not_physically_authenticated",
            ],
            "independent_numeric_thresholds_available":False,
            "target_board_physically_verified":False,
            "repair_authorized":False,
        }
        if render_version=="semantic_v2":
            context["numeric_source_tool"]["semantic_comparators"]={
                c["claim_id"]:_reference_relation(c) for c in claims
            }
    return context
