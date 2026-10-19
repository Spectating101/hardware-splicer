"""Conservative design revisions from autonomous public-source evidence.

Creates engineering paths and candidate replacements without asserting the
source hardware works, relying on undocumented wiring, or buying materials.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "hardware_splicer.autonomous_engineering_revision.v1"


def propose_design_revisions(
    repair_analysis: Mapping[str,Any],
    splice_source_audit: list[Mapping[str,Any]],
    compatibility: Mapping[str,Any],
)->dict[str,Any]:
    seller_supports_cable=repair_analysis.get("seller_cut_cable_description_reobserved") is True
    family_supports_interfaces=repair_analysis.get("family_spec_state")=="MANUFACTURER_FAMILY_SPEC_REOBSERVED"
    if seller_supports_cable and family_supports_interfaces:
        repair_route={
            "route_id":"consider_exact_model_replacement_interface_cable",
            "why":"Seller's cut-cable description was reobserved and manufacturer model-family documentation supports multiple modular host interfaces.",
            "safe_method":"Identify exact host cable variant before selecting a manufacturer-compatible replacement; DO NOT invent or apply conductor pinouts.",
            "hypothesis_advanced":"severed_interface_cable",
            "alternative_faults_eliminated":[],
            "original_device_repaired":False,
            "confidence_scope":"plausible repair route, not confirmed faulty component",
        }
    else:
        repair_route={
            "route_id":"inspect_original_interface_before_selecting_repair",
            "why":"Current available public source evidence is incomplete, unreachable, or conflicting.",
            "safe_method":"Do not assume that a cut cable is the only defect, or prescribe replacement wiring.",
            "hypothesis_advanced":None,
            "alternative_faults_eliminated":[],
            "original_device_repaired":False,
            "confidence_scope":"unresolved evidence only",
        }

    statuses={x["candidate_id"]:x["public_listing_identity_status"] for x in splice_source_audit}
    qnap_status=statuses.get("qnap_embedded_compute","NO_PUBLIC_SOURCE_RECHECK")
    stop=next((f for f in compatibility["function_coverage"] if "stop" in f["required_function"].lower()),None)
    if not stop:
        raise ValueError("novel splicing revision expected to audit an operator stop function")
    source_consistent=lambda cid: statuses.get(cid)=="SELLER_ADVERTISEMENT_REOBSERVED_NOT_PART_VERIFIED"
    modules=[]
    for item in compatibility["components"]:
        cid=item["candidate_id"]
        state=statuses.get(cid,"NO_PUBLIC_SOURCE_RECHECK")
        disposition=("QUARANTINE_SOURCE_IDENTITY" if state=="CONFLICT_REQUIRES_NEW_SOURCE"
                     else "CANDIDATE_UNVERIFIED")
        if cid=="qnap_embedded_compute":
            disposition=("OPTIONAL_COMPUTE_DONOR_UNTIL_POWER_AND_OS_PROVED"
                         if disposition!="QUARANTINE_SOURCE_IDENTITY" else disposition)
        if cid=="mouse_button_switch":
            disposition="ONLY_NONSafety_UI_HYPOTHESIS"
        modules.append({
            "candidate_id":cid,"source_ref":item["source_ref"],
            "disposition":disposition,
            "usable_subsystem_verified":False,
            "next_material_fact":item["missing_facts"][0],
        })
    provisional_architecture=[
        {
            "function":"barcode read",
            "preferred_hypothesis":"LS2208 intact decoder via correctly identified manufacturer-compatible cable",
            "fallback":"separately documented, known-good USB barcode scanner for reference software testing",
            "limitation":"LS2208 physical output and cable interface still unknown",
        },
        {
            "function":"mechanical indexing",
            "preferred_hypothesis":"salvaged LQ-680 carriage/paper-feed mechanism after physical teardown",
            "fallback":"known-rated low-voltage linear motion stage for software reference tests",
            "limitation":"no verified motor type, driver or travel limits",
        },
        {
            "function":"local decision logic",
            "preferred_hypothesis":(
                "QNAP bare motherboard may become optional embedded compute if exact power/OS/ports can be demonstrated"
                if qnap_status=="SELLER_ADVERTISEMENT_REOBSERVED_NOT_PART_VERIFIED"
                else "QNAP board source is unresolved; do not select it as critical path"
            ),
            "fallback":"existing authorized Linux computer can be used for software-only processing demonstrations",
            "limitation":"no permission to assume a bare QNAP PCB is a compatible host",
        },
        {
            "function":"human input and stop",
            "preferred_hypothesis":"salvaged mouse switch only for non-safety user-interface input",
            "fallback":"use a separately specified independent safety-rated stop system, not an ordinary mouse switch",
            "limitation":"existing four donors do not establish a safety-stop solution",
        },
    ]
    return {
        "schema_version":SCHEMA,
        "repair_route":repair_route,
        "new_product_revision":{
            "revision_name":"barcode_inspection_reference_architecture_v1",
            "scope":"software-only candidate revision; not wiring or fabrication instructions",
            "module_dispositions":modules,
            "provisional_functional_blocks":provisional_architecture,
            "identified_critical_missing_functions":[
                stop["required_function"]
            ] if stop["coverage_status"]!="HYPOTHESIZED_NOT_VERIFIED" else [],
            "external_support_components_likely_needed":[
                "documented scanner-host interface cable with exact part compatibility",
                "properly rated motion driver and controller after motor characterization",
                "verified supply and protection hardware",
                "independent safety-rated machine stop and interlock design",
                "documented motion mounting and limit sensing",
            ],
            "replacement_part_purchased":False,
            "donor_measured_or_integrated":False,
            "complete_system_demonstrated":False,
            "connection_authorized":False,
            "candidate_source_consistency_count":sum(source_consistent(x["candidate_id"]) for x in modules),
        },
        "repair_mission_success":False,
        "splice_mission_success":False,
        "physical_hardware_actions":0,
        "why_this_is_a_revision":"Uses retrieved model-family facts and renewed seller listing identities to re-rank approaches and reject unsafe or undocumented subassemblies.",
    }
