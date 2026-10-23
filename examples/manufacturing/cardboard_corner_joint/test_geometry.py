"""Digital acceptance and rejection cases for a low-load FDM alignment joint."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("challenge", Path(__file__).with_name("generate.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_nominal_and_clearance_sweep():
    for clearance in [0.15, 0.30, 0.45]:
        for thickness in [2.7, 3.0, 3.3]:
            p = dict(mod.PARAMETERS, stock_thickness_mm=thickness, per_side_clearance_mm=clearance)
            part, gap = mod.connector(p)
            assert abs(gap - thickness-2*clearance)<1e-7
            assert part.val().isValid()
            assert len(part.solids().vals())==1
            assert part.val().Volume()>0


def test_invalid_clearance_rejected():
    for values in [
        {"per_side_clearance_mm":0.0},
        {"per_side_clearance_mm":-0.1},
        {"stock_thickness_mm":0.0},
        {"wall_mm":1.0},
        {"insertion_stop_mm":4.0},
        {"arm_end_mm":17.0},
    ]:
        with pytest.raises(ValueError):
            mod.connector(dict(mod.PARAMETERS,**values))


def test_real_exports_are_watertight_and_negative_fit_detected(tmp_path):
    result=mod.run(tmp_path)
    assert result["collision_checks"]["all_digital_checks_pass"]
    assert result["collision_checks"]["nominal_x_sheet_overlap_mm3"] == 0
    assert result["collision_checks"]["nominal_y_sheet_overlap_mm3"] == 0
    assert result["collision_checks"]["oversize_sheet_overlap_mm3"] > 1
    assert result["connector"]["watertight"]
    assert all(c["watertight"] for c in result["fit_coupons"].values())
    assert not result["physical_fit_verified"]
    assert not result["fabrication_tested"]
