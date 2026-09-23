#!/usr/bin/env python3
"""Evaluate new-build, donor-reuse and hybrid Product Factory supply substrates.

This is an economics/authority gate only. It does not establish donor safety,
electrical correctness, legal ownership, regulatory compliance, or physical
authorization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


SUPPORTED_MODES = {
    "NEW_BUILD",
    "DONOR_RETROFIT",
    "MODULE_REUSE",
    "COMPONENT_HARVEST",
    "HYBRID",
}


def _money(value: float) -> float:
    return round(float(value), 4)


def evaluate_supply_route(route: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(route.get("mode") or "").strip()
    if mode not in SUPPORTED_MODES:
        raise ValueError(f"unsupported supply mode: {mode!r}")

    target_msrp = float(route.get("target_msrp_usd") or 0.0)
    margin_floor = float(route.get("minimum_target_gross_margin_fraction") or 0.0)
    all_new_cogs = float(route.get("all_new_reference_cogs_usd") or 0.0)
    intended_units = int(route.get("intended_build_units") or 0)

    if target_msrp <= 0 or not 0 < margin_floor < 1 or intended_units <= 0:
        raise ValueError("positive target MSRP, margin floor and intended units are required")

    if mode == "NEW_BUILD":
        cogs = float(route.get("new_build_cogs_usd") or all_new_cogs)
        margin = 1 - cogs / target_msrp if cogs > 0 else -1.0
        return {
            "schema": "hardware_splicer.supply_route_evaluation.v1",
            "mode": mode,
            "decision": "ADVANCE_SUPPLY_ROUTE" if margin >= margin_floor else "HOLD_SUPPLY_ROUTE",
            "effective_cogs_per_sellable_usd": _money(cogs),
            "gross_margin_fraction": round(margin, 6),
            "savings_vs_all_new_fraction": 0.0,
            "checks": {
                "margin_floor": margin >= margin_floor,
                "identity_control": True,
                "supply_depth": True,
                "hazard_boundary": True,
                "yield_evidence": True,
            },
            "authority": {
                "sourcing_investigation_authorized": margin >= margin_floor,
                "physical_rework_authorized": False,
                "fabrication_authorized": False,
            },
        }

    donor = route.get("donor")
    if not isinstance(donor, Mapping):
        raise ValueError("donor economics are required for non-new supply routes")

    acquisition = float(donor.get("acquisition_cost_usd_per_donor") or 0.0)
    inbound = float(donor.get("inbound_shipping_usd_per_donor") or 0.0)
    inspection_minutes = float(donor.get("inspection_minutes_per_donor") or 0.0)
    labor_rate = float(donor.get("labor_rate_usd_per_hour") or 0.0)
    pass_yield = float(donor.get("usable_yield_fraction") or 0.0)
    donor_pool = int(donor.get("observed_available_units") or 0)
    required_supply_multiple = float(donor.get("required_supply_depth_multiple") or 2.0)

    if not 0 < pass_yield <= 1:
        raise ValueError("usable_yield_fraction must be in (0, 1]")
    if min(acquisition, inbound, inspection_minutes, labor_rate) < 0:
        raise ValueError("donor cost inputs cannot be negative")

    rework_minutes = float(donor.get("rework_minutes_per_sellable") or 0.0)
    rework_materials = float(donor.get("rework_materials_usd_per_sellable") or 0.0)
    new_parts = float(donor.get("new_parts_usd_per_sellable") or 0.0)
    final_qa_minutes = float(donor.get("final_qa_minutes_per_sellable") or 0.0)
    warranty_reserve = float(donor.get("warranty_reserve_usd_per_sellable") or 0.0)
    reject_disposal = float(donor.get("reject_disposal_usd_per_reject") or 0.0)
    reject_recovery_credit = float(donor.get("reject_recovery_credit_usd_per_reject") or 0.0)

    expected_donors = intended_units / pass_yield
    expected_rejects = expected_donors - intended_units

    inspection_labor_per_donor = inspection_minutes / 60.0 * labor_rate
    donor_lot_cost = expected_donors * (acquisition + inbound + inspection_labor_per_donor)
    reject_net_cost = expected_rejects * (reject_disposal - reject_recovery_credit)

    per_sellable_processing = (
        rework_minutes / 60.0 * labor_rate
        + rework_materials
        + new_parts
        + final_qa_minutes / 60.0 * labor_rate
        + warranty_reserve
    )
    processing_cost = intended_units * per_sellable_processing
    effective_cogs = (donor_lot_cost + reject_net_cost + processing_cost) / intended_units

    gross_margin = 1 - effective_cogs / target_msrp
    savings = (
        (all_new_cogs - effective_cogs) / all_new_cogs
        if all_new_cogs > 0
        else 0.0
    )

    hazards = donor.get("hazards") or {}
    opens_mains = bool(hazards.get("opens_mains_voltage"))
    modifies_lithium = bool(hazards.get("modifies_lithium_battery"))
    unknown_contamination = bool(hazards.get("unknown_contamination"))
    intact_certified_power = bool(hazards.get("intact_certified_external_power_only", False))
    hazard_ok = not (opens_mains or modifies_lithium or unknown_contamination)
    if intact_certified_power:
        hazard_ok = hazard_ok and True

    identity = donor.get("identity_control") or {}
    exact_model = bool(identity.get("exact_model_or_approved_variant"))
    revision_capture = bool(identity.get("revision_or_board_id_captured"))
    variant_test = bool(identity.get("variant_specific_acceptance_test"))
    identity_ok = exact_model and revision_capture and variant_test

    yield_basis = str(donor.get("yield_evidence_basis") or "").strip()
    yield_ok = bool(yield_basis)

    supply_multiple = donor_pool / expected_donors if expected_donors > 0 else 0.0
    supply_ok = donor_pool > 0 and supply_multiple >= required_supply_multiple

    minimum_savings = float(route.get("minimum_donor_savings_fraction") or 0.15)
    savings_ok = all_new_cogs <= 0 or savings >= minimum_savings

    checks = {
        "margin_floor": gross_margin >= margin_floor,
        "donor_savings_floor": savings_ok,
        "identity_control": identity_ok,
        "supply_depth": supply_ok,
        "hazard_boundary": hazard_ok,
        "yield_evidence": yield_ok,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    decision = "ADVANCE_DONOR_PROTOTYPE" if not blockers else "HOLD_SUPPLY_ROUTE"

    return {
        "schema": "hardware_splicer.supply_route_evaluation.v1",
        "mode": mode,
        "decision": decision,
        "effective_cogs_per_sellable_usd": _money(effective_cogs),
        "gross_margin_fraction": round(gross_margin, 6),
        "savings_vs_all_new_fraction": round(savings, 6),
        "expected_donors_required": round(expected_donors, 3),
        "expected_rejects": round(expected_rejects, 3),
        "observed_supply_depth_multiple": round(supply_multiple, 3),
        "cost_breakdown": {
            "donor_lot_cost_usd": _money(donor_lot_cost),
            "reject_net_cost_usd": _money(reject_net_cost),
            "sellable_processing_cost_usd": _money(processing_cost),
            "inspection_labor_usd_per_donor": _money(inspection_labor_per_donor),
            "processing_usd_per_sellable": _money(per_sellable_processing),
        },
        "checks": checks,
        "blockers": blockers,
        "authority": {
            "sourcing_investigation_authorized": decision == "ADVANCE_DONOR_PROTOTYPE",
            "donor_disassembly_authorized": False,
            "physical_rework_authorized": False,
            "fabrication_authorized": False,
        },
        "boundary": (
            "ADVANCE_DONOR_PROTOTYPE means the donor/hybrid route is economically worth a bounded prototype. "
            "It does not establish donor safety, legal ownership, regulatory compliance, electrical correctness, "
            "repeatable supply, physical authorization, or a sellable remanufactured product."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("route", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.route.read_text(encoding="utf-8"))
    result = evaluate_supply_route(payload)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
