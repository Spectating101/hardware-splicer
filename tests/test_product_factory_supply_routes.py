from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments" / "product_factory" / "evaluate_supply_route.py"
SPEC = importlib.util.spec_from_file_location("pf_supply", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FIXTURE = json.loads(
    (ROOT / "experiments" / "product_factory" / "fixtures" / "hybrid_donor_route_acceptance.json").read_text()
)


def clone(value):
    return json.loads(json.dumps(value))


def test_hybrid_donor_route_can_beat_all_new_build_after_real_labor_and_yield() -> None:
    result = MODULE.evaluate_supply_route(FIXTURE)
    assert result["decision"] == "ADVANCE_DONOR_PROTOTYPE"
    assert result["effective_cogs_per_sellable_usd"] < FIXTURE["all_new_reference_cogs_usd"]
    assert result["savings_vs_all_new_fraction"] >= FIXTURE["minimum_donor_savings_fraction"]
    assert result["gross_margin_fraction"] >= FIXTURE["minimum_target_gross_margin_fraction"]
    assert result["authority"]["physical_rework_authorized"] is False


def test_bad_yield_can_destroy_apparent_ewaste_bargain() -> None:
    route = clone(FIXTURE)
    route["donor"]["usable_yield_fraction"] = 0.25
    result = MODULE.evaluate_supply_route(route)
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert result["checks"]["donor_savings_floor"] is False or result["checks"]["margin_floor"] is False


def test_component_harvest_is_not_free_when_labor_is_large() -> None:
    route = clone(FIXTURE)
    route["mode"] = "COMPONENT_HARVEST"
    route["donor"]["rework_minutes_per_sellable"] = 90
    route["donor"]["final_qa_minutes_per_sellable"] = 30
    result = MODULE.evaluate_supply_route(route)
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert result["effective_cogs_per_sellable_usd"] > FIXTURE["all_new_reference_cogs_usd"]


def test_unknown_or_high_risk_donor_hardware_fails_closed() -> None:
    route = clone(FIXTURE)
    route["donor"]["hazards"]["modifies_lithium_battery"] = True
    result = MODULE.evaluate_supply_route(route)
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert "hazard_boundary" in result["blockers"]


def test_donor_variant_identity_is_required() -> None:
    route = clone(FIXTURE)
    route["donor"]["identity_control"]["revision_or_board_id_captured"] = False
    result = MODULE.evaluate_supply_route(route)
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert "identity_control" in result["blockers"]


def test_shallow_secondhand_supply_does_not_scale_by_assumption() -> None:
    route = clone(FIXTURE)
    route["donor"]["observed_available_units"] = 50
    result = MODULE.evaluate_supply_route(route)
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert "supply_depth" in result["blockers"]
