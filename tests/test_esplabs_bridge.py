"""esp-labs' 32 lessons imported as data and checked against Espressif's ESP32-S3-WROOM-1 datasheet."""

from __future__ import annotations

import copy

import pytest

from hardware_splicer.esplabs_bridge import S3_FACTS, lessons_for_kit, review_esplabs, review_lesson, snapshot


def test_the_snapshot_is_pinned_and_licensed():
    meta = snapshot()["meta"]
    assert len(meta["commit"]) == 40 and meta["license"].startswith("MIT") and meta["counts"]["lessons"] == 32


def test_esp_labs_wiring_passes_the_datasheet_and_its_statuses_stay_its_own():
    result = review_esplabs()
    assert result["lessons"] == 32
    assert result["findings_by_rule"] == {"strapping_pin": 27}  # every one is GPIO0, the DevKitC-1's BOOT button
    assert all(f["pin"] == 0 for r in result["reviews"] for f in r["findings"])
    assert sum(result["status_by_rung"].values()) == 32
    assert all(r["status"]["provenance"].startswith("esp-labs' own report") for r in result["reviews"])
    assert result["physical_correctness"] == "UNPROVEN"


def test_a_pin_taken_by_octal_psram_is_an_error_on_an_r8_module_only():
    lesson = copy.deepcopy(snapshot()["lessons"]["02"])
    lesson["pins"].append({"pin": "36", "role": "LED 2", "side": "R"})
    assert [f["rule"] for f in review_lesson(lesson)["findings"]] == ["pin_taken_by_octal_psram"]
    assert review_lesson(lesson, octal_psram=False)["findings"] == []
    assert "IO35, IO36, and IO37" in S3_FACTS["octal_psram"]["quote"]


def test_wirestudios_s3_board_file_is_cross_checked_against_the_datasheet():
    missing = {(d["pin"], d["missing"].split(" (")[0]) for d in review_esplabs()["board_data_disagreements"]}
    assert (3, "strap tag") in missing
    assert {p for p, _ in missing} >= {35, 36, 37}


def test_lessons_for_a_kit():
    result = lessons_for_kit(["tft", "rc522"])
    assert {"00", "01", "03", "R1"} <= set(result["ready"])
    assert {"lesson": "R2", "missing_one_of": [["tags"]]} in result["one_item_away"]
    with pytest.raises(ValueError, match="not esp-labs kit items"):
        lessons_for_kit(["flux-capacitor"])
