from __future__ import annotations


def test_linear_axis_bundle_outputs(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "axis",
        "linear_axis": {
            "travel_mm": 200.0,
            "rod_d_mm": 8.0,
            "rod_spacing_mm": 40.0,
            "rod_length_mm": 320.0,
            "belt_width_mm": 6.0,
            "pulley_teeth": 20,
            "payload_n": 10.0,
        },
    }
    out = run(spec, out_dir=tmp_path)
    assert "motor_mount.scad" in out["outputs"]
    assert "idler_mount.scad" in out["outputs"]
    assert "carriage.scad" in out["outputs"]
    assert "belt_clamp.scad" in out["outputs"]
    # Optional parts are on by default in spec; runner defaults should include them for full demo.
    assert (tmp_path / "motor_mount.scad").exists()
    assert (tmp_path / "idler_mount.scad").exists()
    assert (tmp_path / "carriage.scad").exists()
    assert (tmp_path / "belt_clamp.scad").exists()
