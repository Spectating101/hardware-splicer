from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = json.loads((ROOT / "experiments" / "product_factory" / "run-001-proofpod.json").read_text())

STAGES = [
    "DISCOVER", "SELECT", "SPECIFY", "DESIGN_SCHEMATIC", "VERIFY_SCHEMATIC",
    "DESIGN_PCB", "VERIFY_PCB", "SOURCE", "BUILD", "PROVE", "BENCHMARK",
    "SELL", "LEARN",
]


def test_product_factory_has_complete_ordered_stage_chain() -> None:
    assert [stage["id"] for stage in RUN["stages"]] == STAGES
    assert RUN["schema"] == "hardware_splicer.product_factory_run.v1"
    assert RUN["run_id"] == "PF-001"


def test_factory_does_not_confuse_selection_with_commercial_proof() -> None:
    by_id = {stage["id"]: stage for stage in RUN["stages"]}
    assert by_id["SELECT"]["state"] == "PASS"
    assert by_id["SELECT"]["decision"] == "ADVANCE_TO_SCHEMATIC"
    assert by_id["BUILD"]["state"] == "QUEUED_AFTER_SOURCE_AND_HUMAN_AUTHORITY"
    assert not by_id["BUILD"]["state"].startswith("PASS")
    assert by_id["PROVE"]["state"].startswith("BLOCKED")
    assert by_id["SELL"]["state"].startswith("BLOCKED")
    assert "not evidence of physical correctness" in RUN["claim_boundary"]


def test_factory_keeps_economics_machine_readable() -> None:
    metrics = RUN["metrics"]
    assert metrics["target_board_msrp_usd"] > metrics["target_board_cogs_ceiling_usd_at_100"]
    assert metrics["target_kit_msrp_usd"] > metrics["target_kit_cogs_ceiling_usd_at_100"]
    assert metrics["preliminary_board_budget_usd"] <= metrics["target_board_cogs_ceiling_usd_at_100"]
    assert metrics["target_min_gross_margin_fraction"] >= 0.65
