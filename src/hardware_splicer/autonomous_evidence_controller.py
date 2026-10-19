"""Bounded, autonomous public-evidence investigation for both HS mission types.

Runs read-only source queries, conditionally revises source credibility and
missing-evidence prioritization, then stops without pretending to observe
physical electronics. No user-supervised steps, no purchases or device I/O.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import re
from typing import Any

from .autonomous_source_observer import observe_source, ZEBRA_SPEC, QNAP_SPEC, EPSON_DOC, _fetch_public_html
from .engineering_mission_contract import normalize_engineering_mission, repair_investigation_plan
from .engineering_multi_donor_compatibility import evaluate_multi_donor_compatibility
from .autonomous_engineering_revision import propose_design_revisions

SCHEMA = "hardware_splicer.autonomous_evidence_controller.v1"
_MODEL_REGEX = re.compile(r"(?<!\w)(LS\d{4,}|LQ[- ]\d{3,4}(?:C)?|TS[- ]?\d{3,4}P?(?:\s*II)?|A\d{4})(?!\w)",re.I)
_MAX_ACTIONS=12


def _model_from_source(text: str) -> str | None:
    match=_MODEL_REGEX.search(text)
    # Preserve spaces in model variants such as "TS-219P II"; otherwise the
    # literal identifier check incorrectly rejects a matching product title.
    return match.group(1) if match else None


def _ruten_from_ref(ref: str) -> str | None:
    if not isinstance(ref,str) or not re.fullmatch(r"ruten:\d{10,20}",ref):
        return None
    return "https://www.ruten.com.tw/item/"+ref.split(":",1)[1]+"/"


def _listings_for_source_refs(splice: Mapping[str,Any]) -> dict[str,dict[str,str]]:
    """Only bind a source when the item ID is independently in part notes."""
    refs=splice["engineering_mission"]["source_refs"]
    rows={}
    for row in splice.get("available_parts") or []:
        if not isinstance(row,Mapping):
            continue
        notes=str(row.get("notes") or "")
        name=str(row.get("name") or "")
        for ref in refs:
            url=_ruten_from_ref(ref)
            if url and url in notes:
                if ref in rows:
                    raise ValueError(f"source duplicated across available_parts: {ref}")
                model=_model_from_source(name)
                if model:
                    rows[ref]={"url":url,"model":model}
    return rows


def run_public_evidence_investigation(
    repair_intake: Mapping[str,Any],
    splice_intake: Mapping[str,Any],
    *,
    fetcher: Callable[[str],tuple[int,str,bytes,str]]=_fetch_public_html,
    observed_at: str | None=None,
) -> dict[str,Any]:
    repair=normalize_engineering_mission(repair_intake)
    splice=normalize_engineering_mission(splice_intake)
    if repair is None or repair["type"]!="restorative_repair":
        raise ValueError("first case must explicitly be restorative_repair")
    if splice is None or splice["type"]!="novel_splice":
        raise ValueError("second case must explicitly be novel_splice")
    diagnostic=repair_investigation_plan(repair,repair_intake.get("repair_intake"))
    compat=evaluate_multi_donor_compatibility(splice,splice_intake.get("engineering_materials"))

    actions=[]
    receipts=[]
    fetch_cache: dict[tuple[str,str,str],dict[str,Any]] = {}
    action_count=0

    def execute(action: str, ref: str, url: str, model: str, purpose: str, why: str):
        nonlocal action_count
        if action_count >= _MAX_ACTIONS:
            raise RuntimeError("bounded autonomous investigation budget exhausted")
        action_count+=1
        cache_key=(url,purpose,model)
        cached=cache_key in fetch_cache
        if cached:
            receipt=fetch_cache[cache_key]
        else:
            receipt=observe_source(
                source_id=ref,url=url,expected_model=model,purpose=purpose,
                fetcher=fetcher,observed_at=observed_at,
            )
            fetch_cache[cache_key]=receipt
            receipts.append(receipt)
        actions.append({
            "sequence":action_count,
            "selected_action":("reuse_previous_source_receipt" if cached else action),
            "subject":ref,
            "selected_because":why,
            "result_status":receipt["status"],
            "advanced_physical_evidence":False,
            "retry_decision":"no_repeated_fetch_or_retry",
        })
        return receipt

    repair_sources={}
    # Repair case: exact item identity must occur in source notes. Do not
    # guess an item's URL from prose that may be stale or ambiguous.
    for row in repair_intake.get("available_parts") or []:
        name=str(row.get("name") or "")
        notes=str(row.get("notes") or "")
        model=_model_from_source(name)
        for ref in repair["source_refs"]:
            url=_ruten_from_ref(ref)
            if model and url and url in notes:
                repair_sources[ref]={"model":model,"url":url}
    for ref in repair["source_refs"]:
        if ref in repair_sources:
            s=repair_sources[ref]
            execute("read_seller_item_metadata",ref,s["url"],s["model"],"market_listing",
                    "Verify whether listed model and seller claim can still be observed without touching hardware")
        else:
            actions.append({"sequence":len(actions)+1,"selected_action":"skip_missing_source_binding",
                            "subject":ref,"result_status":"NO_CANONICAL_LISTING_IN_SOURCE_NOTES",
                            "advanced_physical_evidence":False,
                            "retry_decision":"record_missing_binding_not_assume_model"})
    if diagnostic["differential_diagnosis"].get("profile_id")=="zebra_symbol_ls2208":
        execute("read_manufacturer_family_spec","zebra:ls2208_spec",
                ZEBRA_SPEC,"LS2208","manufacturer_spec",
                "Different host cable standards may explain the reported failure; verify family-specific interface options")

    # New-product case: follow source references only to observed canonical
    # item pages associated with the user's donated-item hypotheses.
    linked=_listings_for_source_refs(splice_intake)
    for ref in splice["source_refs"]:
        source=linked.get(ref)
        if source:
            execute("read_seller_item_metadata",ref,source["url"],source["model"],"market_listing",
                    "Check exact listing-model consistency before using any seller-named component as a candidate")
        else:
            actions.append({"sequence":len(actions)+1,"selected_action":"skip_missing_source_binding",
                            "subject":ref,"result_status":"NO_CANONICAL_LISTING_IN_SOURCE_NOTES",
                            "advanced_physical_evidence":False,
                            "retry_decision":"record_source_identity_gap"})

    # Conditional research: read official family documentation only after
    # matching the listed model. A seller's wrong model is not rescued by a
    # manufacturer's specification of some different product.
    if any(r["source_id"]=="ruten:21447795842755" and
           r["status"]=="MARKET_LISTING_METADATA_REOBSERVED" for r in receipts):
        execute("read_manufacturer_reference","epson:lq680_manual",EPSON_DOC,
                "LQ-680","manufacturer_spec",
                "Check whether an official manual exists for the exact printer family; do not import unrelated Stylus 680 motor specifications")
    if any(r["source_id"]=="ruten:22606139676402" and
           r["status"]=="MARKET_LISTING_METADATA_REOBSERVED" for r in receipts):
        execute("read_manufacturer_reference","qnap:ts219pii_spec",QNAP_SPEC,
                "TS-219P II","manufacturer_spec",
                "Identify documented ports of the complete NAS family while keeping the bare PCB unpowered and unverified")

    by_ref:dict[str,list[dict[str,Any]]]={}
    for receipt in receipts:
        by_ref.setdefault(receipt["source_id"],[]).append(receipt)

    def source_state(ref):
        rows=by_ref.get(ref) or []
        if not rows:
            return "NO_PUBLIC_SOURCE_RECHECK"
        if any(r["status"]=="SOURCE_MODEL_CONFLICT" for r in rows):
            return "CONFLICT_REQUIRES_NEW_SOURCE"
        if any(r["status"]=="MARKET_LISTING_METADATA_REOBSERVED" for r in rows):
            return "SELLER_ADVERTISEMENT_REOBSERVED_NOT_PART_VERIFIED"
        return "PUBLIC_SOURCE_RETRIEVAL_UNAVAILABLE"

    repair_listing_state=source_state(repair["source_refs"][0])
    source_manufacturer=next((r for r in receipts if r["purpose"]=="manufacturer_spec"),None)
    repair_update={
        "repair_differential_hypothesis_count":len(diagnostic["differential_diagnosis"]["alternative_hypotheses"]),
        "first_hypothesis_id":(
            diagnostic["differential_diagnosis"]["alternative_hypotheses"][0]["hypothesis_id"]
            if diagnostic["differential_diagnosis"]["alternative_hypotheses"] else None
        ),
        "seller_listing_state":repair_listing_state,
        "family_spec_state":source_manufacturer["status"] if source_manufacturer else "NOT_QUERIED",
        "model_family_host_interfaces_known":(
            (source_manufacturer or {}).get("manufacturer_family_interface_options",[])
        ),
        "specific_used_scanner_cable_variant_known":False,
        "actual_scanner_condition_verified":False,
        "seller_cut_cable_description_reobserved":any(
            (receipt.get("source_id")==repair["source_refs"][0] and
             receipt.get("status")=="MARKET_LISTING_METADATA_REOBSERVED" and
             re.search(r"剪線|cut.{0,12}cable|cable.{0,12}cut|severed",receipt.get("title") or "",re.I))
            for receipt in receipts
        ),
        "seller_description_does_not_prove_damage":True,
        "diagnosis_proved":False,
        "next_automatable_step":"model_specific_documentation_followup_or_alternate_source_lookup",
        "physical_inspection_still_required":True,
    }
    if source_manufacturer and source_manufacturer["status"]=="MANUFACTURER_FAMILY_SPEC_REOBSERVED":
        repair_update["interpretation"]="Host-mode options confirmed at manufacturer FAMILY level; seller's exact specimen and cable remain unverified."
    else:
        repair_update["interpretation"]="Manufacturer page unavailable or model mismatched; no new family facts promoted."

    manufacturer_by_model={
        "epson_paper_motion":"epson:lq680_manual",
        "qnap_embedded_compute":"qnap:ts219pii_spec",
        "ls2208_scanner_engine":"zebra:ls2208_spec",
    }
    candidates=[]
    for candidate in compat["components"]:
        ref=candidate["source_ref"]
        status=source_state(ref)
        manufacturer=next((r for r in receipts if
                           r["source_id"]==manufacturer_by_model.get(candidate["candidate_id"])),None)
        candidates.append({
            "candidate_id":candidate["candidate_id"],
            "source_ref":ref,
            "official_model_family_source_status":manufacturer["status"] if manufacturer else "NOT_RECHECKED",
            "official_model_family_interface_options":(
                manufacturer.get("manufacturer_family_interface_options",[]) if manufacturer else []
            ),
            "public_listing_identity_status":status,
            "current_seller_ask_twd":next(
                (r["seller_price_claim_twd"] for r in (by_ref.get(ref) or [])
                 if r.get("status")=="MARKET_LISTING_METADATA_REOBSERVED"),None
            ),
            "current_seller_stock_claim":next(
                (r["seller_stock_claim_units"] for r in (by_ref.get(ref) or [])
                 if r.get("status")=="MARKET_LISTING_METADATA_REOBSERVED"),None
            ),
            "function_hypothesis_status":"UNVERIFIED",
            "verified_components":0,
            "can_bind_electrical_interface":False,
        })

    coverage=compat["function_coverage"]
    priority=[
        {"priority":1,"type":"source_identity_discrepancy","source_ref":x["source_ref"],
         "reason":"Marketplace item no longer verifies the expected model"}
        for x in candidates if x["public_listing_identity_status"]=="CONFLICT_REQUIRES_NEW_SOURCE"
    ]
    for f in coverage:
        if f["coverage_status"] in {"PARTIAL_CLAIM_GAP","UNMAPPED_GAP"}:
            priority.append({
                "priority":2,"type":"missing_system_function",
                "required_function":f["required_function"],
                "reason":"No component fully claimed to cover this function; ordinary mouse buttons do not prove a safety-rated stop",
            })
    for edge in compat["proposed_interfaces"]:
        priority.append({
            "priority":3,"type":"interface_unknown",
            "connection_id":edge["connection_id"],
            "reason":edge["comparison_status"],
            "missing_facts":edge["missing_interface_facts"],
        })
    priority.sort(key=lambda r:(r["priority"],r.get("connection_id") or r.get("required_function") or r.get("source_ref") or ""))
    revision=propose_design_revisions(repair_update,candidates,compat)
    actions.append({
        "sequence":len(actions)+1,
        "selected_action":"revise_repair_route_and_new_machine_architecture",
        "subject":"both_missions",
        "result_status":"CONDITIONAL_DESIGN_REVISION_GENERATED",
        "advanced_physical_evidence":False,
        "retry_decision":"do_not_authorize_untested_component_bindings",
    })
    next_steps=[
        "Research safe low-voltage hardware subsystem interface alternatives without assuming donor presence",
        "Source manufacturer exact-revision manuals or teardowns with explicit interface contracts",
        "Keep physical specimen verification, actual measurements and working-machine tests blocked until authorized physical evidence exists",
    ]
    actions.append({
        "sequence":len(actions)+1,
        "selected_action":"recompute_repair_and_splice_evidence_gaps",
        "subject":"both_missions",
        "result_status":"SOURCE_EVIDENCE_REASSESSED",
        "advanced_physical_evidence":False,
        "retry_decision":"stop_at_public_evidence_frontier",
    })
    return {
        "schema_version":SCHEMA,
        "mode":"real_public_source_checks_not_physical_evidence",
        "bounded_source_fetches":len(receipts),
        "actions":actions,
        "source_receipts":receipts,
        "repair":{"original_function":repair["original_function"],"analysis":repair_update,
                  "repair_procedure_established":False,"mission_success":False},
        "splicing":{"new_product":splice["new_product"],"candidate_source_audit":candidates,
                    "function_coverage":coverage,"interconnection_gaps":priority,
                    "verified_distinct_donors":0,"mission_success":False},
        "next_automatable_work":next_steps,
        "proposed_engineering_revision":revision,
        "physical_operations_executed":0,
        "purchases_or_seller_contacts":0,
        "completion_status":"PUBLIC_RESEARCH_ADVANCED; PHYSICAL_AND_INTEGRATION_PROOF_UNAVAILABLE",
        "stop_reason":"source_recheck_done_and_remaining_requirements_are_not_verifiable_by_public_listing_or_family_spec_alone",
    }
