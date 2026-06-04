from __future__ import annotations


def test_rotary_joint_bundle_outputs(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "rj",
        "rotary_joint": {
            "bearing": "608zz",
            "shaft_d_mm": 8.0,
            "wall_mm": 4.0,
            "clearance_mm": 0.3,
            "block_w_mm": 50.0,
            "block_d_mm": 25.0,
            "block_h_mm": 18.0,
        },
    }
    out = run(spec, out_dir=tmp_path)

    assert "rj_bearing_block.scad" in out["outputs"]
    assert "rj_arm.scad" in out["outputs"]
    assert (tmp_path / "rj_bearing_block.scad").exists()
    assert (tmp_path / "rj_arm.scad").exists()

    bom_items = [b.get("item") for b in (out.get("bom") or [])]
    assert "bearing" in bom_items

