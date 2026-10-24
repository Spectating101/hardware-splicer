"""Portfolio-wide commercial coverage report: evidence first, profits last.

Records are frozen research snapshots, not current listings or inventory.
A positive screen cannot be elevated into a customer order or purchase permit.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

# Manually reviewed lineage equivalence. No automatic fuzzy deduplication:
# similar device names do not establish equivalent models or underlying lots.
KNOWN_CONCEPT_ALIASES = {
    "TW-PF-HMI-001": "benchhmi-v0",
}


def build_commercial_cohort(dossier: Mapping[str, Any]) -> dict[str, Any]:
    if dossier.get("schema_version") != "hardware_splicer.commercial_convergence_dossier.v0":
        raise ValueError("wrong convergence dossier version")
    discovery: list[dict[str, Any]] = []
    for cat in dossier.get("donor_discovery_catalogs") or []:
        for item in cat.get("listings") or []:
            discovery.append({
                "candidate_id": item.get("candidate_id"),
                "concept_id": item.get("candidate_id"),
                "source_class": "used_equipment_marketplace",
                "market": "Taiwan",
                "currency": "TWD",
                "source_ref": item.get("source_ref"),
                "source_url": item.get("listing_url"),
                "family": item.get("family"),
                "source_ask_range": item.get("advertised_ask_range"),
                "price_evidence": "HISTORICAL_ADVERTISED_ASK_ONLY",
                "modeled_net": None,
                "decision": "UNPRICED_DISCOVERY",
                "missing_evidence": [
                    "matched completed sale or measured productive use",
                    "condition, parts yield, fabrication/repair BOM and test",
                    "all-in purchase, logistics, warranty and labor",
                ],
                "purchase_authorized": False,
            })
    screened: list[dict[str, Any]] = []
    for item in dossier.get("historical_salvage_economics") or []:
        screened.append({
            "candidate_id": item["candidate_id"],
            "concept_id": item["candidate_id"],
            "source_class": "salvage_economics",
            "market": "Taiwan",
            "currency": "TWD",
            "source_ref": item["source_ref"],
            "source_url": item["source_market_links"][0] if item["source_market_links"] else None,
            "price_evidence": item["price_quality"],
            "modeled_net": item["modeled_expected_net_twd"],
            "modeled_bid_at_target_profit": item["modeled_target_profit_max_bid_twd"],
            "source_ask": item["source_ask_twd"],
            "downside_wins_of_nine": sum(1 for point in item["nine_point_sensitivity"]
                                           if point["expected_net_twd"] > 0),
            "failure_mode_gate": item["failure_mode_gate"],
            "decision": (
                "RESEARCH_ONLY_POSITIVE_MODEL" if item["modeled_expected_net_twd"] > 0
                else "REJECT_CURRENT_MODEL"
            ),
            "missing_evidence": [
                "same-model completed sales not advertised prices",
                "verified repair yield and actual defect",
                "actual labor/freight/warranty, and legal purchase conditions",
            ],
            "purchase_authorized": False,
        })
    pf: list[dict[str, Any]] = []
    for item in dossier.get("product_factory_experiments") or []:
        pf.append({
            "candidate_id": item.get("candidate_id"),
            "concept_id": item.get("candidate_id"),
            "source_class": "product_factory",
            "market": "Taiwan" if str(item.get("candidate_id")) in {"benchhmi-v0", "fielddeck-v0"}
                      else "unconfirmed",
            "currency": "TWD" if str(item.get("candidate_id")) in {"benchhmi-v0", "fielddeck-v0"}
                        else "USD",
            "source_ref": item.get("source_ref"),
            "price_evidence": "TARGET_MSRP_NOT_BUYER_PRICE",
            "modeled_net": None,
            "decision": "UNPRICED_PRODUCT_CONCEPT",
            "missing_evidence": [
                "physical manufactured sample and acceptance evidence",
                "landed BOM including failed donor fraction and sales/warranty",
                "actual qualified buyer and paid order or metered use",
            ],
            "purchase_authorized": False,
        })
    regional: list[dict[str, Any]] = []
    for item in dossier.get("regional_product_concepts") or []:
        regional.append({
            "candidate_id": item["candidate_id"],
            "concept_id": KNOWN_CONCEPT_ALIASES.get(item["candidate_id"], item["candidate_id"]),
            "source_class": "historical_regional_product_route",
            "market": item["market"],
            "currency": item["currency"],
            "source_ref": item.get("source_ref"),
            "price_evidence": "ILLUSTRATIVE_TARGET_VS_COST_NOT_FULL_CONTRIBUTION",
            "modeled_net": None,
            "decision": "UNPRICED_PRODUCT_CONCEPT",
            "missing_evidence": [
                "matching supplier quotes, full BOM and conditional yield",
                "payment/logistics/quality and use/sale demand",
                "technical proof and product compliance",
            ],
            "purchase_authorized": False,
        })
    all_records = discovery + screened + pf + regional
    ids = [f"{x['source_class']}:{x['candidate_id']}" for x in all_records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate source records")
    concepts = {x["concept_id"] for x in all_records}
    classes = Counter(x["source_class"] for x in all_records)
    counts = Counter(x["decision"] for x in all_records)
    validation = {
        "real_completed_purchases": 0,
        "physically_qualified_donors": 0,
        "verified_supplier_quotes": 0,
        "verified_paid_customers": 0,
        "measured_profitable_products": 0,
    }
    # Refuse to assert factual zero in arbitrary external datasets; these
    # counters only describe the preserved input cohort's evidence scope.
    return {
        "schema_version": "hardware_splicer.commercial_cohort_review.v1",
        "status": "DISCOVERY_AND_HYPOTHETICAL_SCREEN_ONLY",
        "total_source_records": len(all_records),
        "distinct_named_concepts_after_known_lineage_aliases": len(concepts),
        "lineage_aliases": KNOWN_CONCEPT_ALIASES,
        "by_source_class": dict(sorted(classes.items())),
        "by_decision": dict(sorted(counts.items())),
        "historically_priced_salvage_screens": len(screened),
        "positive_modeled_salvage_screens": sum(x["modeled_net"] > 0 for x in screened),
        "nonpositive_modeled_salvage_screens": sum(x["modeled_net"] <= 0 for x in screened),
        "records": all_records,
        "explicitly_unsupported_proofs": validation,
        "purchase_authorized": False,
        "claims": [
            "No real-world profitable hardware arbitrage is demonstrated by these source snapshots.",
            "Modeled salvage returns belong to five historical PR #147 screens, not the 17 unrelated donor listings.",
            "PF-002's separate illustrative material-validated case does not produce a realized product margin.",
            "Six regional alternatives expand beyond e-waste into reused industrial compute and touch hardware.",
            "Source record count is not a count of independent products or transaction-ready orders.",
        ],
    }
