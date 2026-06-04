from __future__ import annotations


def test_pan_tilt_outputs(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "pt",
        "pan_tilt": {"pan_servo": "sg90", "tilt_servo": "sg90"},
    }
    out = run(spec, out_dir=tmp_path)
    assert "pt_base.scad" in out["outputs"]
    assert "pt_bracket.scad" in out["outputs"]
    assert "pt_platform.scad" in out["outputs"]
    assert (tmp_path / "pt_base.scad").exists()

