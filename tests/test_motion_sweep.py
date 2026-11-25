"""The range-of-motion sweep on a mechanism with a known answer: an arm swinging into a post."""

from __future__ import annotations

import json
import math
import subprocess

import pytest

from hardware_splicer import motion_sweep
from hardware_splicer.digital_project import native_python

# An arm (a 60 x 10 x 10 mm bar from the pivot along +x) turns about z from 0 to 180 degrees over a base plate.
# A 10 mm post stands at (0, 40) mm. The bar's leading face (5 mm off its centre line) first meets the post's corner
# at (5, 35) mm, which lies at atan2(35, 5) = 81.9 degrees and 35.36 mm out: contact at 81.9 - asin(5/35.36) = 73.7
# degrees, and by symmetry the bar is clear again after 106.3. A hinge pin shared by both links overlaps them at every angle and must not count as a clash.
BUILD = r"""
import sys, trimesh
out = sys.argv[1]
def save(mesh, name):
    mesh.apply_scale(0.001)  # URDF units are metres
    mesh.export(f"{out}/{name}.stl")
bar = trimesh.creation.box(extents=[60, 10, 10]); bar.apply_translation([30, 0, 30]); save(bar, "bar")
post = trimesh.creation.box(extents=[10, 10, 50]); post.apply_translation([0, 40, 25]); save(post, "post")
plate = trimesh.creation.box(extents=[20, 20, 5]); plate.apply_translation([0, 0, 2.5]); save(plate, "plate")
pin = trimesh.creation.cylinder(radius=3, height=40, sections=48); pin.apply_translation([0, 0, 20]); save(pin, "pin")
"""
URDF = """<robot name="swing">
  <link name="base">
    <collision><geometry><mesh filename="post.stl"/></geometry></collision>
    <collision><geometry><mesh filename="plate.stl"/></geometry></collision>
    <collision><geometry><mesh filename="pin.stl"/></geometry></collision>
  </link>
  <link name="arm">
    <collision><geometry><mesh filename="bar.stl"/></geometry></collision>
    <collision><geometry><mesh filename="pin.stl"/></geometry></collision>
  </link>
  <joint name="swing" type="revolute"><parent link="base"/><child link="arm"/>
    <origin xyz="0 0 0" rpy="0 0 0"/><axis xyz="0 0 1"/><limit lower="0" upper="3.14159"/></joint>
</robot>
"""


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    python = native_python()
    if subprocess.run([python, "-c", "import trimesh, scipy, manifold3d"], capture_output=True).returncode != 0:
        pytest.skip("native CAD interpreter lacks trimesh, scipy or manifold3d")
    work = tmp_path_factory.mktemp("swing")
    subprocess.run([python, "-c", BUILD, str(work)], check=True)
    (work / "swing.urdf").write_text(URDF)
    done = subprocess.run([python, "-I", motion_sweep.__file__, "--urdf", str(work / "swing.urdf"), "--steps", "37"],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def test_the_arm_is_clear_until_it_reaches_the_post(report):
    swing = report["sweeps"][0]
    lo, hi = swing["clear_range"]
    assert lo == 0
    assert abs(hi - math.radians(70)) < 1e-3  # 5-degree steps: the last clear step before 73.7 degrees
    assert swing["worst_clash"]["a"].startswith("base/post") and swing["worst_clash"]["b"].startswith("arm/bar")
    assert not swing["worst_clash"]["joined"] or swing["worst_clash"]["over_start_mm3"] > 1


def test_clashes_stop_once_the_arm_has_passed_the_post(report):
    swing = report["sweeps"][0]
    angles = sorted({clash_at for clash_at in _clash_angles(report)})
    assert angles and abs(angles[0] - math.radians(75)) < 1e-3 and abs(angles[-1] - math.radians(105)) < 1e-3
    assert swing["clash_steps"] == len(angles)


def test_the_shared_hinge_pin_is_not_a_clash(report):
    assert not any("pin" in pair for pair in report["sweeps"][0]["clashing_pairs"])


def _clash_angles(report):
    # clash steps sit between the clear stretch and the far side; recompute them from the step count and range
    swing = report["sweeps"][0]
    step = (swing["range"][0][1] - swing["range"][0][0]) / (swing["steps"] - 1)
    hi = swing["clear_range"][1]
    return [hi + step * (i + 1) for i in range(swing["clash_steps"])]


def test_urdf_parsing_and_kinematics_without_meshes(tmp_path):
    path = tmp_path / "swing.urdf"
    path.write_text(URDF)
    model = motion_sweep.parse_urdf(path)
    assert [j["name"] for j in model["joints"]] == ["swing"] and len(model["links"]["base"]) == 3
    tip = motion_sweep.link_poses(model, {"swing": math.pi / 2})["arm"] @ [0.06, 0, 0, 1]
    assert abs(tip[0]) < 1e-9 and abs(tip[1] - 0.06) < 1e-9
