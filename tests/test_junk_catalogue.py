"""The junk catalogue: vacuum donors carry OOMWOO's module data, and a mapping rover can come from two donors."""
from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.junk_catalogue import DATA, catalogue, lookup

OOMWOO = DATA.parent / "third_party" / "oomwoo"


def test_a_mapping_rover_comes_from_a_lidar_vacuum_and_a_phone():
    plan = lookup(["lidar_2d", "drive_motors_encoded", "battery_pack", "camera", "wifi_compute"])
    assert not plan["not_covered_by_junk"]
    assert [step["device"] for step in plan["donor_plan"]] == ["robot-vacuum-lidar-xiaomi-roborock", "phone-android-cracked"]
    assert set(plan["donor_plan"][0]["covers"]) == {"lidar_2d", "drive_motors_encoded", "battery_pack"}


def test_every_capability_a_device_gives_is_declared_and_used():
    cat = catalogue()
    given = {c for d in cat["devices"] for c in d["gives"]}
    assert given <= set(cat["capabilities"])
    assert set(cat["capabilities"]) <= given


def test_oomwoo_modules_are_attributed_and_match_the_catalogue():
    snap = json.loads((OOMWOO / "SNAPSHOT.json").read_text())
    assert snap["license"].startswith("Apache-2.0") and (OOMWOO / "LICENSE").read_text().lstrip().startswith("Apache License")
    modules = json.loads((OOMWOO / "parts.json").read_text())["modules"]
    caps = set(catalogue()["capabilities"])
    for m in modules:
        assert m["capability"] in caps and m["source"].startswith("https://github.com/makerspet/oomwoo/blob/")
        if "cad" in m:
            assert len(m["cad_sha256"]) == 64 and len(m["envelope_mm"]) == 3
    fans = [m for m in modules if m["capability"] == "suction_fan"]
    assert all(lo <= hi for m in fans for lo, hi in [m["rated_kpa"]])
