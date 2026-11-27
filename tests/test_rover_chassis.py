"""Rover chassis: the Pololu 25D build is unchanged, and the TT-motor build (HS-ROVER-A's cheap drive tier) passes."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from hardware_splicer.digital_project import native_python

ROOT = Path(__file__).resolve().parents[1]
TT = {"drive": "2wd_caster", "motor": "tt", "caster": "pololu_953", "wheel_d": 65, "wheel_w": 18, "hub_offset": 3.0,
      "wheel_mass_g": 31.5, "battery_mass_g": 165, "caster_mass_g": 9}


def chassis(tmp_path, params):
    python = native_python()
    if subprocess.run([python, "-c", "import cadquery"], capture_output=True).returncode:
        pytest.skip("native CAD interpreter lacks cadquery")
    (tmp_path / "p.json").write_text(json.dumps(params))
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    run = subprocess.run([python, "-m", "hardware_splicer.rover_chassis", "--params", str(tmp_path / "p.json"), "--out", str(tmp_path)],
                         capture_output=True, text=True, env=env, timeout=300, check=True)
    return json.loads(run.stdout)


def test_pololu_build_is_unchanged(tmp_path):
    res = chassis(tmp_path, {"drive": "2wd_caster", "wheel_d": 90, "hub_offset": 3.5, "battery_mass_g": 165})
    assert res["problems"] == [] and res["motor"] == "pololu_25d"
    assert res["ground_clearance_mm"] == 30.5 and round(min(res["static_tip_angle_deg"].values())) == 27


def test_tt_build_passes_and_is_lighter(tmp_path):
    res = chassis(tmp_path, TT)
    assert res["problems"] == [], res["problems"]
    assert res["ground_clearance_mm"] == pytest.approx(65 / 2 - 22.44 / 2, abs=0.1)
    assert res["caster_boss_mm"] == pytest.approx(65 / 2 - 22.44 / 2 - 13.5, abs=0.1)
    assert res["all_up_mass_g"] < 450 and min(res["static_tip_angle_deg"].values()) > 30
    tight = chassis(tmp_path / "tight", dict(TT, hub_offset=1.0)) if (tmp_path / "tight").mkdir() is None else None
    assert any("wheel to plate gap" in p for p in tight["problems"])


def test_committed_tt_variant_is_under_budget_with_every_price_cited():
    bom = json.loads((ROOT / "projects/hs-rover-a/tt-variant/bom.json").read_text())
    assert all(line["source"].startswith("https://") for line in bom)
    total = sum(line["qty"] * line["unit_usd"] for line in bom)
    assert total < 250
