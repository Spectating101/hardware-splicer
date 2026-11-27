"""Fit check of an outside STEP assembly: names from the STEP tree, exact overlaps, loose parts, masses."""
import os
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parent / "fixtures" / "step_fit" / "overlap_demo.step"


def _native():
    py = os.environ.get("HARDWARE_SPLICER_DIGITAL_PYTHON")
    if not py or not Path(py).is_file():
        pytest.skip("needs HARDWARE_SPLICER_DIGITAL_PYTHON (CadQuery, trimesh, manifold3d)")


def test_a_step_assembly_reports_its_overlaps_loose_part_and_mass():
    # The fixture (made with CadQuery): a 40x30x5 plate, a 10x10x20 servo sunk 1.5 mm into it, an 8 mm bracket
    # overlapping the servo by 5x8x8 mm, and a hub in a sub-assembly floating 25 mm above everything.
    _native()
    from hardware_splicer import engineering_toolbelt as tb

    env = tb.call("hs_step_fit", {"step": str(DEMO), "density_g_cm3": {"*": 1.24}})
    res = env["result"]
    assert [p["part"] for p in res["parts"]] == ["demo/base_plate", "demo/servo", "demo/bracket", "demo/arm/hub"]
    overlaps = {frozenset((p["a"], p["b"])): p["overlap_mm3"] for p in res["fit"]["pairs"] if p["kind"] == "overlap"}
    assert overlaps[frozenset(("demo/bracket", "demo/servo"))] == pytest.approx(320, rel=0.01)
    assert overlaps[frozenset(("demo/servo", "demo/base_plate"))] == pytest.approx(150, rel=0.01)
    assert res["fit"]["loose_parts"] == ["demo/arm/hub"]
    assert res["summary"]["mass_g"] == pytest.approx((6000 + 2000 + 512 + 113.1) / 1000 * 1.24, abs=0.1)
    assert not env["ok"] or env["problems"]  # overlaps are reported as problems
