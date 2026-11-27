"""The open reference design record stays pinned, licensed and honest about what it is."""

from __future__ import annotations

import json
import re
from pathlib import Path

RECORD = Path(__file__).resolve().parents[1] / "examples/reference_designs/open_reference_designs_20261125.json"


def test_every_reference_board_is_pinned_and_carries_its_licence():
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    assert record["schema"] == "hardware_splicer.open_reference_designs.v1"
    assert "Nothing was built or measured" in record["claim_boundary"] and "not a false-positive rate" in record["hs_rule_tuning"]
    assert {b["product_class"] for b in record["boards"]} == {"fielddeck", "drone", "power_station", "logger"}
    for board in record["boards"]:
        source = board["source"]
        assert re.fullmatch(r"[0-9a-f]{40}", source.get("commit", "")) or re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", "")), board["repository"]
        assert source["licence"], board["repository"]
        assert board["blocks"] and board["what"]
        assert set(board["checkers"]) == {"kicad_erc", "kicad_happy_deterministic", "hs_kicad_design_review"}
