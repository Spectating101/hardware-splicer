from __future__ import annotations


def test_gripper_outputs(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "gr",
        "gripper": {"servo_type": "sg90"},
    }
    out = run(spec, out_dir=tmp_path)
    assert "gr_base.scad" in out["outputs"]
    assert "gr_jaw_left.scad" in out["outputs"]
    assert "gr_jaw_right.scad" in out["outputs"]
    assert (tmp_path / "gr_base.scad").exists()

