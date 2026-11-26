"""HS-ARM-A's build closes its own design loop: one-piece printable parts, held loads, swept joint limits."""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from hardware_splicer.digital_project import native_python

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects" / "hs-arm-a"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    python = native_python()
    probe = subprocess.run([python, "-c", "import cadquery, trimesh"], capture_output=True)
    if probe.returncode:
        pytest.skip("native CAD interpreter lacks cadquery or trimesh")
    out = tmp_path_factory.mktemp("arm")
    shutil.copy(PROJECT / "joint_limits.json", out / "joint_limits.json")
    subprocess.run([python, "-I", str(PROJECT / "build_arm.py"), "--out", str(out)], check=True, capture_output=True, timeout=600)
    return out


def test_every_printed_part_is_one_valid_body_that_fits_the_bed(built) -> None:
    parts = json.loads((built / "verification.json").read_text())["parts"]
    assert set(parts) == {"base_housing", "turntable", "upper_arm", "forearm", "wrist", "gripper_base", "gripper_jaw"}
    for name, part in parts.items():
        assert part["single_body"] and part["valid_solid"] and part["fits_bed"], name
        assert (built / "print" / f"{name}.stl").is_file() and (built / "print" / f"{name}.step").is_file()


def test_pitch_joints_hold_the_payload_within_half_of_stall(built) -> None:
    v = json.loads((built / "verification.json").read_text())
    assert set(v["static_torque"]) == {"shoulder", "elbow", "wrist_pitch"}
    assert all(t["pass"] and t["stall_share"] <= 0.5 for t in v["static_torque"].values())
    assert v["reach_mm"]["tool_from_yaw_axis"] >= 300
    # the turntable ring exists because the horn alone could not carry the overturning moment
    assert v["base_yaw_overturning"]["ratio_if_horn_carried_it"] > 1
    assert v["tip_over"]["free_standing_stable"] is False  # the README says to clamp the base


def test_urdf_limits_are_the_swept_ones(built) -> None:
    limits = json.loads((PROJECT / "joint_limits.json").read_text())
    root = ET.parse(built / "urdf" / "hs_arm_a.urdf").getroot()
    for joint in root.findall("joint"):
        lo, hi = limits[joint.get("name")]
        lim = joint.find("limit")
        assert float(lim.get("lower")) == pytest.approx(math.radians(lo), abs=1e-4)
        assert float(lim.get("upper")) == pytest.approx(math.radians(hi), abs=1e-4)


def test_committed_sweep_found_no_clash_inside_the_limits() -> None:
    sweep = json.loads((PROJECT / "motion_sweep.json").read_text())
    assert len(sweep["sweeps"]) == 6 and all(s["clash_steps"] == 0 for s in sweep["sweeps"])


@pytest.fixture(scope="module")
def built_rev_b(tmp_path_factory):
    python = native_python()
    if subprocess.run([python, "-c", "import cadquery, trimesh"], capture_output=True).returncode:
        pytest.skip("native CAD interpreter lacks cadquery or trimesh")
    out = tmp_path_factory.mktemp("arm_b")
    shutil.copy(PROJECT / "joint_limits.json", out / "joint_limits.json")
    subprocess.run([python, "-I", str(PROJECT / "build_arm.py"), "--servo", "sts3215", "--out", str(out)], check=True,
                   capture_output=True, timeout=600)
    return out


def test_rev_b_is_built_around_the_measured_sts3215_and_reports_its_shoulder_honestly(built_rev_b) -> None:
    v = json.loads((built_rev_b / "verification.json").read_text())
    assert v["servo_geometry"]["body_mm"] == [45.4, 24.8, 35.4] and v["servo_geometry"]["horn_offset_mm"] == 12.5
    assert v["servo_geometry"]["cheek_boss_mm"] == {"horn_side": 3.0, "idler_side": 4.0}
    assert all(p["single_body"] and p["valid_solid"] and p["fits_bed"] for p in v["parts"].values())
    t = v["static_torque"]
    assert t["elbow"]["pass"] and t["wrist_pitch"]["pass"]
    assert not t["shoulder"]["pass"] and 0.5 < t["shoulder"]["stall_share"] < 0.8  # over HS's rule, under SO-101's practice
    assert v["reach_mm"]["tool_from_yaw_axis"] >= 300


def test_committed_rev_b_sweep_is_clash_free_over_rev_a_ranges_and_cheaper() -> None:
    sweep = json.loads((PROJECT / "rev-b" / "motion_sweep.json").read_text())
    assert len(sweep["sweeps"]) == 6 and all(s["clash_steps"] == 0 for s in sweep["sweeps"])
    bom_a = json.loads((PROJECT / "BOM.json").read_text())
    bom_b = json.loads((PROJECT / "rev-b" / "BOM.json").read_text())
    assert bom_b["total"] < bom_a["total"] / 5
