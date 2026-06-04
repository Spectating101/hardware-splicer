from __future__ import annotations


def test_leadscrew_axis_bundle_outputs(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "ls_axis",
        "leadscrew_axis": {
            "travel_mm": 200.0,
            "screw_length_mm": 320.0,
            "rod_d_mm": 8.0,
            "rod_spacing_mm": 40.0,
            "rod_length_mm": 320.0,
            "lead_mm_per_rev": 8.0,
            "payload_n": 20.0,
        },
    }
    out = run(spec, out_dir=tmp_path)

    assert "ls_motor_mount.scad" in out["outputs"]
    assert "ls_screw_end_support.scad" in out["outputs"]
    assert "ls_carriage_nut_mount.scad" in out["outputs"]
    assert "ls_assembly_preview.scad" in out["outputs"]
    assert (tmp_path / "ls_motor_mount.scad").exists()
    assert (tmp_path / "ls_screw_end_support.scad").exists()
    assert (tmp_path / "ls_carriage_nut_mount.scad").exists()

    bom_items = [b.get("item") for b in (out.get("bom") or [])]
    assert "lead screw" in bom_items
    assert "lead screw nut" in bom_items

