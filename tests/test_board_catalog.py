"""PlatformIO's board definitions in HS, and what they let HS check."""

from __future__ import annotations

import copy

from hardware_splicer.board_catalog import catalog_rows, find_board, octal_psram, snapshot, wirestudio_board_disagreements


def test_the_snapshot_is_pinned_and_licensed():
    meta = snapshot()["meta"]
    assert meta["license"].startswith("Apache-2.0") and all(len(c) == 40 for c in meta["commits"].values())
    assert meta["counts"]["boards"] == len(snapshot()["boards"]) > 500


def test_octal_psram_comes_only_from_platformio_s_memory_type():
    devkitc = find_board("esp32-s3-devkitc-1")
    assert devkitc["name"].endswith("No PSRAM)") and octal_psram(devkitc) is None  # the default N8 board says nothing
    octal = [b for b in snapshot()["boards"].values() if octal_psram(b)]
    assert len(octal) >= 30 and all(b["memory_type"] in {"qio_opi", "opi_opi"} and b["mcu"] == "esp32s3" for b in octal)
    assert octal_psram(find_board("esp32dev")) is None


def test_an_octal_psram_s3_design_wiring_gpio35_is_an_error():
    from hardware_splicer.wirestudio_bridge import review_design
    from hardware_splicer.wirestudio_bridge import snapshot as ws

    octal_id = next(b["id"] for b in snapshot()["boards"].values() if octal_psram(b))
    design = copy.deepcopy(ws()["examples"]["s3-devkitc"])
    design["connections"].append({"component_id": design["components"][0]["id"], "pin_role": "DIN", "target": {"kind": "gpio", "pin": "GPIO35"}})
    original = ws()["boards"]["esp32-s3-devkitc-1"]["platformio_board"]
    try:
        ws()["boards"]["esp32-s3-devkitc-1"]["platformio_board"] = octal_id
        rules = [f["rule"] for f in review_design(design)["findings"]]
    finally:
        ws()["boards"]["esp32-s3-devkitc-1"]["platformio_board"] = original
    assert "pin_taken_by_octal_psram" in rules
    assert "pin_taken_by_octal_psram" not in [f["rule"] for f in review_design(design)["findings"]]


def test_wirestudio_boards_are_cross_checked_and_borrowed_ids_are_informational():
    rows = wirestudio_board_disagreements()
    assert rows and all(r.get("severity", "info") == "info" or "PlatformIO has no board" in r["issue"] for r in rows)
    assert any(r["wirestudio_board"] == "esp32-s3-supermini" for r in rows)


def test_catalog_rows():
    rows = catalog_rows()
    assert len(rows) == len(snapshot()["boards"]) and all(r["capabilities"] == ["board_metadata"] for r in rows)
    assert sum(1 for r in rows if r.get("octal_psram")) >= 30
