from __future__ import annotations


def test_belt_reduction_outputs(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "br",
        "belt_reduction": {
            "motor_pulley_teeth": 20,
            "driven_pulley_teeth": 60,
            "center_distance_mm": 60.0,
        },
    }
    out = run(spec, out_dir=tmp_path)
    assert "br_reduction_plate.scad" in out["outputs"]
    assert (tmp_path / "br_reduction_plate.scad").exists()

