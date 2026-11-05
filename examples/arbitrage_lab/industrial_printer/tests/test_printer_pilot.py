from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("hs_printer_pilot", ROOT / "printer_pilot.py")
pilot = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pilot)


def load_case():
    return json.loads((ROOT / "sources_20261105.json").read_text())


def test_public_source_and_unknown_actual_condition():
    source = load_case()
    assert source["target"]["price"] == 1200
    assert source["target"]["listing_url"].startswith("https://www.ruten.com.tw/item/")
    assert source["resale"]["achieved_sales_verified"] is False
    assert source["resale"]["same_dpi_as_target_known"] is False


def test_unit_economics_are_conditional():
    result = pilot.scenario(load_case(), 6500, 0.5)
    assert result["conditional_success_profit_twd"] == 2025
    assert result["failed_unit_loss_twd"] == -2100
    assert result["expected_value_twd"] == -38
    assert result["max_purchase_offer_for_target_ev_twd"] == 662


def test_printhead_replacement_violates_economics():
    source = load_case()
    for price in source["resale"]["price_scenarios"]:
        result = pilot.scenario(source, price, 1.0, replaced_head=True)
        assert result["conditional_success_profit_twd"] < 0


@pytest.mark.parametrize("probability", [-0.5, 1.5])
def test_invalid_probability_rejected(probability):
    with pytest.raises(ValueError):
        pilot.scenario(load_case(), 6500, probability)


def test_missing_head_tsc_negative_control():
    control = pilot.tsc_missing_head_control(load_case())
    assert control["compatible_printhead_cost_verified"] is False
    assert control["optimistic_profit_before_printhead_and_tax_twd"] < 0
    assert control["break_even_printhead_budget_twd"] == 0


def test_offline_label_source_is_synthetic_only():
    label = pilot.render_zpl()
    assert label.startswith("^XA")
    assert label.endswith("^XZ\n")
    assert "HSZT230QC001" in label
    assert label.count("^XA") == 1


def test_report_has_no_actual_device_or_sales_evidence():
    r = json.loads((ROOT / "evidence/industrial_refurb_screen.json").read_text())
    assert r["device_acquired"] is False
    assert r["physical_prints_made"] == 0
    assert r["passed_evidence_gates"] == []
    assert r["hardware_splicer_backend"]["physical_repair_authority"] is False
    assert "NO_PURCHASE" in r["decision"]
