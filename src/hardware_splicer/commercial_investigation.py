"""Prioritized investigation queue over *existing* HS commercial evidence.

The queue proposes cheap evidence-gathering steps; it does not buy hardware,
fabricate products, contact sellers or convert listing claims into measurements.
"""
from __future__ import annotations

from typing import Any, Mapping


def build_investigation_queue(dossier: Mapping[str, Any]) -> dict[str, Any]:
    """Produce actionable, provenance-retaining work items from a convergence dossier."""
    if dossier.get("schema_version") != "hardware_splicer.commercial_convergence_dossier.v0":
        raise ValueError("unexpected convergence dossier schema")
    tasks: list[dict[str, Any]] = []
    by_id: dict[str, list[dict[str, Any]]] = {}
    for cat in dossier.get("donor_discovery_catalogs") or []:
        for candidate in cat.get("listings") or []:
            cid = str(candidate.get("candidate_id") or "")
            if not cid:
                continue
            by_id.setdefault(cid, []).append(candidate)
            tasks.append({
                "candidate_id": cid,
                "origin": "taiwan_donor_discovery",
                "currency": "TWD",
                "source_ref": candidate.get("source_ref"),
                "listing_url": candidate.get("listing_url"),
                "observed_ask_range": candidate.get("advertised_ask_range"),
                "status": "HOLD_FOR_DISCOVERY",
                "next_evidence": [
                    "Confirm exact model and variant with seller; listing may be obsolete",
                    "Establish lawful ownership and secondhand-versus-regulated-waste status",
                    "Find matched completed sale prices, not unrelated asking prices",
                    "Obtain condition photos and testability/repair feasibility",
                    "Price required materials, disposal, freight and physical QA",
                    "Identify plausible buyer or a measurable internal productive use",
                ],
                "purchase_authorized": False,
                "costly_work_authorized": False,
            })
    for raw in dossier.get("salvage_purchase_screens") or []:
        cid = str(raw.get("candidate_id") or "")
        if not cid:
            continue
        source_matches = by_id.get(cid, [])
        tasks.append({
            "candidate_id": cid,
            "origin": "taiwan_salvage_purchase_screen",
            "currency": "TWD",
            "source_ref": raw.get("source_ref"),
            "screened_net_twd": (raw.get("priced_outcome") or {}).get("expected_net_per_acquired_unit"),
            "screened_max_bid_twd": (raw.get("priced_outcome") or {}).get("target_profit_max_bid"),
            "status": "HOLD_FOR_VERIFICATION",
            "source_identity_matches": len(source_matches),
            "next_evidence": [
                "Reconcile listing/model/condition identity between screen and discovery; ID alone is not proof",
                "Recheck matching same-model sold prices and platform fees",
                "Validate repair probability, testing hours and failure recovery value",
                "Do not bid from hypothetical maximum bid estimates",
            ],
            "purchase_authorized": False,
            "costly_work_authorized": False,
        })
    for raw in dossier.get("historical_salvage_economics") or []:
        cid = str(raw.get("candidate_id") or "")
        if not cid:
            raise ValueError("historical salvage screen without ID")
        net = raw.get("modeled_expected_net_twd")
        bid = raw.get("modeled_target_profit_max_bid_twd")
        tasks.append({
            "candidate_id": cid,
            "origin": "historical_salvage_economics",
            "currency": "TWD",
            "source_ref": raw.get("source_ref"),
            "modeled_expected_net_twd": net,
            "modeled_target_profit_max_bid_twd": bid,
            "original_target_profit_per_unit_twd": raw.get("original_target_profit_per_acquired_unit_twd"),
            "positive_downside_scenarios": sum(
                1 for scenario in raw.get("nine_point_sensitivity") or []
                if scenario.get("expected_net_twd", 0) > 0
            ),
            "status": (
                "TARGET_PAPER_PASS_NO_PURCHASE" if raw.get("current_decision") == "MODELED_TARGET_PASS_UNVERIFIED"
                else "BELOW_TARGET_HOLD" if net is not None and net > 0
                else "REJECT_CURRENT_ECONOMIC_MODEL"
            ),
            "hard_stop": raw.get("failure_mode_gate"),
            "next_evidence": [
                "Prove same exact model: comparable sold transactions, not retail asks",
                "Verify reported fault and identify safety or costly failed component",
                "Re-estimate repair/parts yield and conditional hours from measured samples",
                "Do not treat modeled maximum bid as authority to buy",
            ],
            "purchase_authorized": False,
            "costly_work_authorized": False,
        })
    for raw in dossier.get("regional_product_concepts") or []:
        cid = str(raw.get("candidate_id") or "")
        if not cid:
            raise ValueError("regional product thesis without ID")
        tasks.append({
            "candidate_id": cid,
            "origin": "regional_product_concept",
            "currency": raw.get("currency"),
            "market": raw.get("market"),
            "source_ref": raw.get("source_ref"),
            "status": "HOLD_FOR_LOCAL_SUPPLIER_AND_BUYER_PRICING",
            "next_evidence": [
                "Obtain exact local donor model availability and compatible quantities",
                "Prepare materials/BOM and engineering effort for full landed cost",
                "Establish real local buyer budget or measured productive internal use",
                "Do not infer cross-border margins from target price and COGS spreads",
            ],
            "purchase_authorized": False,
            "costly_work_authorized": False,
        })
    for pf in dossier.get("product_factory_experiments") or []:
        stages = pf.get("stage_states") or {}
        open_stages = [
            k for k in ("DISCOVER", "SELECT", "SPECIFY", "DESIGN_SCHEMATIC",
                        "VERIFY_SCHEMATIC", "DESIGN_PCB", "VERIFY_PCB",
                        "SOURCE", "BUILD", "PROVE", "BENCHMARK", "SELL")
            if str(stages.get(k) or "") not in {"PASS"}
        ]
        tasks.append({
            "candidate_id": pf.get("candidate_id"),
            "origin": "product_factory",
            "currency": None,
            "source_ref": pf.get("source_ref"),
            "status": "HOLD_FOR_ENGINEERING_EVIDENCE",
            "earliest_unclosed_stage": open_stages[0] if open_stages else None,
            "next_evidence": [
                "Resolve earliest unclosed factory gate without changing frozen requirements",
                "Qualify actual donor/parts identities and effective procurement price",
                "Complete revision-bound physical acceptance before commercial claims",
                "Obtain qualified buyer demand or measured internal operating output",
            ],
            "purchase_authorized": False,
            "costly_work_authorized": False,
        })
    for src in dossier.get("salvage_discovery_reports") or []:
        for opp in src.get("opportunities") or []:
            tasks.append({
                "candidate_id": opp.get("candidate_id"),
                "origin": "circuit_ai_salvage",
                "currency": "USD" if opp.get("value_hypothesis_usd") else None,
                "source_ref": opp.get("source_ref"),
                "status": "HOLD_FOR_PHYSICAL_IDENTIFICATION",
                "next_evidence": [
                    "Verify recovered part identity and usable quantities",
                    "Perform appropriate unpowered and low-voltage testing",
                    "Find true buyer/use demand and attributable recovery labor",
                    "Distinguish illustrative value assumptions from completed transactions",
                ],
                "purchase_authorized": False,
                "costly_work_authorized": False,
            })
    for case in (dossier.get("commercial_cases") or {}).get("cases") or []:
        for route in case.get("routes") or []:
            tasks.append({
                "candidate_id": case.get("candidate_id"),
                "origin": "commercial_option",
                "route_id": route.get("route_id"),
                "currency": case.get("currency"),
                "status": "FIX_INVALID_MODEL" if route.get("status") == "INVALID"
                          else "EVIDENCE_SCREEN",
                "modeled_net": route.get("net_value"),
                "evpi_upper_bound": route.get("evpi_upper_bound"),
                "next_evidence": [
                    *(route.get("errors") or []),
                    *(route.get("blockers") or []),
                    "Check costs, acquisition feasibility and evidence references before any spend",
                ],
                "purchase_authorized": False,
                "costly_work_authorized": False,
            })
    return {
        "schema_version": "hardware_splicer.commercial_investigation_queue.v0",
        "status": "EVIDENCE_GATHERING_ONLY",
        "task_count": len(tasks),
        "tasks": tasks,
        "warnings": [
            "Identical listing IDs across unmerged branches do not prove matching devices",
            "No task authorizes spending, contacting suppliers, or claiming a working product",
            "Modeled per-asset net and theoretical EVPI are NOT observed profits",
            "E-waste collection/processing requires separate legal clearance",
        ],
        "purchase_authorized": False,
    }
