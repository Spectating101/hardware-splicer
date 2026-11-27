"""The Black Wire pinout collection in HS, and its second reading of HS's Adafruit module pins."""

from __future__ import annotations

from hardware_splicer.blackwire_bridge import catalog_rows, corroborate_planner_pins, snapshot


def test_the_snapshot_is_pinned_attributed_and_licensed():
    meta = snapshot()["meta"]
    assert len(meta["commit"]) == 40 and meta["license"].startswith("CC-BY-4.0") and "Valleytech" in meta["attribution"]
    assert meta["counts"] == {"boards": 595, "pin_rows": 20363, "parts": 600}


def test_hs_adafruit_modules_agree_with_black_wire_where_both_have_the_product():
    rows = {r["module"]: r for r in corroborate_planner_pins()}
    for module in ("adafruit-bme280-stemma-qt", "adafruit-ds3231-stemma-qt", "adafruit-ina219-stemma-qt", "adafruit-oled-1.3-128x64-stemma-qt"):
        assert rows[module]["only_in_hs"] == [], module
        assert {"GND", "SDA", "SCL"} <= set(rows[module]["agree"]) or {"GND", "SDI", "SCK"} <= set(rows[module]["agree"])


def test_catalog_rows_keep_the_review_level():
    rows = catalog_rows()
    assert sum(r["capabilities"] == ["pinout"] for r in rows) == 595 and sum(r["capabilities"] == ["pin_labels"] for r in rows) == 600
    assert all("not electrical verification" in r["evidence"] for r in rows if r["capabilities"] == ["pinout"])
