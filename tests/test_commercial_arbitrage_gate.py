from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATOR_PATH = ROOT / "experiments" / "commercial_arbitrage" / "evaluate.py"
SPEC = importlib.util.spec_from_file_location("commercial_arbitrage", EVALUATOR_PATH)
EVALUATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVALUATOR)

SCAN = json.loads((ROOT / "experiments" / "commercial_arbitrage" / "market_scan_2026-09-23.json").read_text())
CONTRACT = json.loads((ROOT / "hardware" / "reference_designs" / "proofpod_v0" / "product_contract.json").read_text())


def test_proofpod_advances_only_to_schematic() -> None:
    result = EVALUATOR.evaluate(SCAN, CONTRACT)
    assert result["decision"] == "ADVANCE_TO_SCHEMATIC"
    assert result["blockers"] == []
    assert set(result["computed"]["professional_anchor_ids"]) == {
        "dediprog-sf100",
        "total-phase-aardvark",
    }
    assert "adafruit-ft232h" in result["computed"]["low_cost_floor_ids"]
    assert "design work only" in result["boundary"]


def test_weak_margin_fails_closed() -> None:
    contract = json.loads(json.dumps(CONTRACT))
    contract["economics"]["kit_landed_cogs_ceiling_usd_at_100"] = 60
    result = EVALUATOR.evaluate(SCAN, contract)
    assert result["decision"] == "HOLD"
    assert "kit_margin" in result["blockers"]


def test_hard_precision_category_does_not_sneak_through() -> None:
    contract = json.loads(json.dumps(CONTRACT))
    contract["product_id"] = "powerpod-v0"
    result = EVALUATOR.evaluate(SCAN, contract)
    assert result["decision"] == "HOLD"
    assert "build_difficulty_bounded" in result["blockers"]
    assert "calibration_burden_bounded" in result["blockers"]


def test_market_gap_cannot_ignore_cheap_competitor_floor() -> None:
    scan = json.loads(json.dumps(SCAN))
    scan["benchmarks"] = [
        row for row in scan["benchmarks"]
        if not (row["currency"] == "USD" and row.get("price", 9999) <= 20)
    ]
    result = EVALUATOR.evaluate(scan, CONTRACT)
    assert result["decision"] == "HOLD"
    assert "low_cost_floor_acknowledged" in result["blockers"]
