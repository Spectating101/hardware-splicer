from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "hardware" / "reference_designs" / "proofpod_v0"
SCAN = ROOT / "experiments" / "commercial_arbitrage" / "market_scan_2026-09-23.json"


def test_proofpod_remains_pre_schematic_and_unproven() -> None:
    contract = json.loads((PILOT / "product_contract.json").read_text())
    assert contract["status"] == "CONCEPT_CONTRACT"
    assert contract["authority"] == {
        "schematic_complete": False,
        "pcb_complete": False,
        "fabrication_ready": False,
        "physical_correctness": "UNPROVEN",
        "commercial_claims_validated": False,
    }


def test_proofpod_economics_have_real_margin_headroom() -> None:
    contract = json.loads((PILOT / "product_contract.json").read_text())
    economics = contract["economics"]
    board_margin = 1 - economics["board_only_landed_cogs_ceiling_usd_at_100"] / economics["board_only_msrp_usd"]
    kit_margin = 1 - economics["kit_landed_cogs_ceiling_usd_at_100"] / economics["kit_msrp_usd"]
    assert board_margin >= economics["minimum_target_gross_margin_fraction"]
    assert kit_margin >= economics["minimum_target_gross_margin_fraction"]


def test_proofpod_safe_defaults_are_not_negotiable() -> None:
    scope = json.loads((PILOT / "product_contract.json").read_text())["v0_scope"]
    assert scope["signal_outputs_default_disabled"] is True
    assert scope["target_power_default_off"] is True
    assert scope["writes_default_disabled"] is True
    assert scope["physical_write_arm_required"] is True
    assert scope["target_current_limit_ma_max"] <= 250
    assert scope["protocols"] == ["SPI master", "I2C master"]


def test_market_scan_contains_low_and_professional_price_anchors() -> None:
    scan = json.loads(SCAN.read_text())
    prices = {row["id"]: row for row in scan["benchmarks"]}
    assert prices["adafruit-ft232h"]["price"] < 20
    assert prices["dediprog-sf100"]["price"] >= 250
    assert prices["total-phase-aardvark"]["price"] >= 350
    assert scan["candidate_products"][0]["id"] == "proofpod-v0"


def test_bom_target_stays_below_board_cogs_ceiling_before_quote() -> None:
    rows = list(csv.DictReader((PILOT / "BOM_TARGET.csv").open()))
    total = next(row for row in rows if row["Category"] == "TOTAL BOARD TARGET")
    contract = json.loads((PILOT / "product_contract.json").read_text())
    assert float(total["100-unit unit-cost budget USD"]) <= contract["economics"]["board_only_landed_cogs_ceiling_usd_at_100"]
