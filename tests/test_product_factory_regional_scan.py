from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = json.loads(
    (ROOT / "experiments" / "product_factory" / "regional_scans" / "taiwan_china_2026-09-24.json").read_text()
)


def test_regional_scan_preserves_native_market_roles() -> None:
    assert SCAN["regions"] == ["Taiwan", "Mainland China"]
    assert "finished-product" in SCAN["thesis"]
    assert "donor/substrate" in SCAN["thesis"]


def test_china_scan_rejects_simple_gateway_arbitrage() -> None:
    avoid = set(SCAN["mainland_china"]["avoid"])
    assert "simple RS485/RS232-to-Ethernet clone" in avoid
    floor = SCAN["mainland_china"]["commodity_price_floor"]
    assert min(row.get("observed_price_rmb", 10**9) for row in floor) <= 56


def test_taiwan_scan_contains_touch_pos_and_industrial_price_umbrella() -> None:
    pos = next(
        row for row in SCAN["taiwan"]["observed_donors"]
        if row["category"] == "retired_pos_touch_terminal"
    )
    assert min(item["observed_price_twd"] for item in pos["examples"]) <= 1000
    assert max(
        item.get("price_twd", max(item.get("price_twd_range", [0])))
        for item in SCAN["taiwan"]["finished_product_anchors"]
    ) >= 20000


def test_cross_border_scrap_is_not_implicitly_authorized() -> None:
    boundary = SCAN["cross_border_boundary"]
    assert boundary["default"] == "SOURCE_AND_TRANSFORM_WITHIN_THE_SAME_MARKET"
    assert boundary["authority"].startswith("UNVERIFIED")
