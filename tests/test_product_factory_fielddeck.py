from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments" / "product_factory" / "evaluate_supply_route.py"
SPEC = importlib.util.spec_from_file_location("pf003_supply", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

RUN = json.loads((ROOT / "experiments" / "product_factory" / "run-003-fielddeck.json").read_text())
CONTRACT = json.loads((ROOT / "hardware" / "reference_designs" / "fielddeck_v0" / "product_contract.json").read_text())
ROUTE = json.loads((ROOT / "experiments" / "product_factory" / "donor_probes" / "fielddeck_aim8i_supply_route.json").read_text())

def test_pf003_is_a_real_cyberdeck_splice() -> None:
    assert RUN["run_id"] == "PF-003"
    assert CONTRACT["approved_donor"]["model"] == "AIM8I"
    assert CONTRACT["new_hardware"]["working_name"] == "FieldDock + FieldIO v0"
    assert "compact physical keyboard" in CONTRACT["new_hardware"]["baseline_functions"]

def test_pf003_economics_are_interesting_but_fail_closed_on_supply_and_yield() -> None:
    result = MODULE.evaluate_supply_route(ROUTE)
    assert result["gross_margin_fraction"] >= ROUTE["minimum_target_gross_margin_fraction"]
    assert result["savings_vs_all_new_fraction"] >= ROUTE["minimum_donor_savings_fraction"]
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert result["checks"]["supply_depth"] is False
    assert result["checks"]["yield_evidence"] is False

def test_pf003_does_not_claim_ruggedness_after_dock_or_heavy_compute() -> None:
    non_goals = set(CONTRACT["explicit_non_goals"])
    assert "retaining IP65 after adding an unqualified dock" in non_goals
    assert "high-performance local AI workstation" in non_goals
    assert CONTRACT["authority"]["fabrication_ready"] is False

def test_pf003_keeps_battery_modification_out_of_scope() -> None:
    splice = json.loads((ROOT / "hardware" / "reference_designs" / "fielddeck_v0" / "splice_plan.json").read_text())
    assert any("battery-cell repacking" in item for item in splice["reject_if"])
    assert splice["physical_authority"] is False
