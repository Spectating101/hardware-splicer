from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "experiments" / "product_factory" / "evaluate_supply_route.py"
SPEC = importlib.util.spec_from_file_location("pf002_supply", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

RUN = json.loads((ROOT / "experiments" / "product_factory" / "run-002-benchhmi.json").read_text())
CONTRACT = json.loads((ROOT / "hardware" / "reference_designs" / "benchhmi_v0" / "product_contract.json").read_text())
ROUTE = json.loads((ROOT / "experiments" / "product_factory" / "donor_probes" / "benchhmi_pos462_supply_route.json").read_text())

def test_pf002_is_a_splice_run_not_a_clean_sheet_clone() -> None:
    assert RUN["run_id"] == "PF-002"
    assert RUN["product_id"] == "benchhmi-v0"
    assert CONTRACT["approved_donor"]["model"] == "POS462"
    assert CONTRACT["approved_donor"]["required_motherboard"].startswith("B91")
    assert CONTRACT["new_hardware"]["connection"] == "external USB only"

def test_pf002_paper_economics_clear_margin_but_supply_gate_holds() -> None:
    result = MODULE.evaluate_supply_route(ROUTE)
    assert result["gross_margin_fraction"] >= ROUTE["minimum_target_gross_margin_fraction"]
    assert result["savings_vs_all_new_fraction"] >= ROUTE["minimum_donor_savings_fraction"]
    assert result["decision"] == "HOLD_SUPPLY_ROUTE"
    assert result["checks"]["supply_depth"] is False
    assert result["checks"]["yield_evidence"] is False

def test_pf002_does_not_open_sidecar_or_physical_authority() -> None:
    assert CONTRACT["authority"]["sidecar_design_authorized"] is False
    assert CONTRACT["authority"]["fabrication_ready"] is False
    assert CONTRACT["authority"]["physical_correctness"] == "UNPROVEN"
    assert RUN["authority"]["donor_purchase_authorized"] is False
    assert RUN["authority"]["sidecar_design_authorized"] is False

def test_pf002_rejects_mains_repair_and_wrong_board_revision() -> None:
    splice = json.loads((ROOT / "hardware" / "reference_designs" / "benchhmi_v0" / "splice_plan.json").read_text())
    joined = "\n".join(splice["reject_if"])
    assert "not B91" in joined
    assert "mains-side repair" in joined
    assert splice["physical_authority"] is False
