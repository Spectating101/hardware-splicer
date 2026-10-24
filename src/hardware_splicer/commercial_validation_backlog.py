"""Source-traceable, evidence-first validation backlog across all HS opportunities.

This is triage, not purchase optimization. No inferred margin for unpriced
equipment, and no prioritization of unsafe/regulated waste handling.
"""
from __future__ import annotations

from typing import Any, Mapping

SCHEMA = "hardware_splicer.commercial_validation_backlog.v1"


def build_validation_backlog(dossier: Mapping[str, Any]) -> dict[str, Any]:
    cohort = dossier.get("cohort_review") or {}
    if cohort.get("schema_version") != "hardware_splicer.commercial_cohort_review.v1":
        raise ValueError("requires a complete commercial cohort")
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in cohort.get("records") or []:
        cid = str(record.get("concept_id") or "").strip()
        if not cid:
            raise ValueError("unnamed opportunity")
        groups.setdefault(cid, []).append(record)

    price_by_candidate = {
        str(r.get("candidate_id")): r
        for r in dossier.get("market_evidence_screens") or []
    }
    out: list[dict[str, Any]] = []
    for concept_id, records in sorted(groups.items()):
        sources = list(dict.fromkeys(str(r.get("source_ref")) for r in records if r.get("source_ref")))
        cls = {r["source_class"] for r in records}
        model = next((r for r in records if r["source_class"] == "salvage_economics"), None)
        market_data = price_by_candidate.get(concept_id)
        if model is not None:
            if model["decision"] == "MODELED_TARGET_PASS_UNVERIFIED":
                tier = "P1_PROVE_MARKET_AND_CONDITION"
                next_step = "Verify same-model settled resale comparables and defect/printhead condition before making any purchase case."
            elif model["decision"] == "BELOW_PROFIT_TARGET_UNVERIFIED":
                tier = "P4_BELOW_TARGET"
                next_step = "Reprice or reject: the modeled surplus is below the original profit hurdle even with unverified assumptions."
            else:
                tier = "P5_NEGATIVE_MODEL"
                next_step = "Do not acquire at modeled terms; only reopen with stronger new price, yield, or operating-use evidence."
        elif "product_factory" in cls:
            tier = "P2_ENGINEERING_AND_MARKET_EVIDENCE"
            next_step = "Prove an actual device, itemized landed BOM and a customer need or metered internal utility; target MSRP is not demand."
        elif "historical_regional_product_route" in cls:
            tier = "P2_SUPPLIER_AND_USE_CASE_DISCOVERY"
            next_step = "Verify exact local donor/finished-product quotes and usefulness against commodity substitutes."
        else:
            tier = "P3_IDENTIFY_DONOR_AND_RECOVERY"
            next_step = "Verify current listing, exact variant and condition; identify components, then price sale, recovery and internal use."

        tier_order = {"P1_": 1, "P2_": 2, "P3_": 3, "P4_": 4, "P5_": 5}
        priority_num = next(v for key, v in tier_order.items() if tier.startswith(key))
        records_by_type = sorted(cls)
        native = sorted({str(r.get("currency")) for r in records if r.get("currency")})
        candidate_evidence = market_data or {}
        if candidate_evidence and candidate_evidence.get("status") == "INVALID":
            next_step = "Resolve invalid market evidence before using any comparable price."
        elif candidate_evidence and candidate_evidence.get("sold_median") is not None:
            # A validated input is still not independently audited by HS.
            next_step = "Audit settlement receipts and exact SKU/condition of reported sold comps; do not treat median as guaranteed selling price."
        out.append({
            "concept_id": concept_id,
            "priority_tier": tier,
            "_priority_sort": priority_num,
            "source_classes": records_by_type,
            "source_count": len(records),
            "source_refs": sources,
            "native_currencies": native,
            "business_case_status": "UNPROVEN",
            "model_expected_net": model["modeled_net"] if model is not None else None,
            "model_currency": model["currency"] if model is not None else None,
            "market_sold_median": candidate_evidence.get("sold_median"),
            "market_sold_evidence_status": candidate_evidence.get("status", "NOT_SUBMITTED"),
            "next_verification": next_step,
            "verified_margin": None,
            "physical_acceptance_verified": False,
            "purchase_authorized": False,
        })
    out.sort(key=lambda r: (r["_priority_sort"], r["concept_id"]))
    for r in out:
        del r["_priority_sort"]

    # A bounded, DIVERSE first evidence wave, intentionally not a ranking of
    # speculative profit, with two markets and multiple sourcing archetypes.
    def pick(predicate, count):
        return [r["concept_id"] for r in out if predicate(r)][:count]
    wave: list[str] = []
    wave += pick(lambda x: x["priority_tier"].startswith("P1_"), 1)
    wave += pick(lambda x: "product_factory" in x["source_classes"]
                 and x["concept_id"] == "proofpod-v0", 1)
    # The donor choices are for free/desk research, not buying or handling
    # defective/battery/mains equipment.
    donor_candidates = [
        r for r in out if "used_equipment_marketplace" in r["source_classes"]
    ]
    allowed_families = {"barcode_scanner", "network_board", "nas_chassis"}
    source_rows = {
        x["concept_id"]: x for x in cohort.get("records") or []
        if x.get("source_class") == "used_equipment_marketplace"
    }
    for family in ("barcode_scanner", "network_board"):
        candidates = [
            r for r in donor_candidates
            if source_rows.get(r["concept_id"], {}).get("family") == family
        ]
        if candidates:
            candidates.sort(key=lambda r: (
                source_rows[r["concept_id"]].get("source_ask_range") or [float("inf")]
            )[0])
            wave.append(candidates[0]["concept_id"])
    wave += pick(lambda x: "historical_regional_product_route" in x["source_classes"]
                 and "TWD" in x["native_currencies"]
                 and x["concept_id"] != "benchhmi-v0", 2)
    wave += pick(lambda x: "historical_regional_product_route" in x["source_classes"]
                 and "CNY" in x["native_currencies"], 2)
    if len(wave) != len(set(wave)):
        raise ValueError("validation wave has duplicate concepts")
    if len(out) != cohort["distinct_named_concepts_after_known_lineage_aliases"]:
        raise ValueError("backlog lineage mismatch")
    return {
        "schema_version": SCHEMA,
        "status": "NON_PURCHASE_RESEARCH_QUEUE",
        "record_count": len(out),
        "source_records_covered": cohort["total_source_records"],
        "entries": out,
        "first_evidence_wave": wave,
        "wave_selection_basis": (
            "Research coverage across one positive-paper salvage case, a new "
            "Product Factory design, two low-cost Taiwan donor families, two "
            "Taiwan industrial-product hypotheses and two CNY regional concepts. "
            "Not a claim of best profitability or purchase authorization."
        ),
        "unpriced_concepts": sum(1 for e in out if e["model_expected_net"] is None),
        "verified_profitable_concepts": 0,
        "purchase_authorized": False,
    }
