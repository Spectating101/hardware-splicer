from __future__ import annotations

from src.mecha_splicer.bundle import generate_bundle


def test_generate_enclosure_bundle(tmp_path):
    spec = {
        "project_name": "t1",
        "mode": "prototype",
        "process": "fdm",
        "enclosure": {
            "name": "box",
            "inner_w_mm": 50.0,
            "inner_d_mm": 30.0,
            "inner_h_mm": 15.0,
            "wall_mm": 2.4,
            "floor_mm": 2.0,
            "lid_mm": 2.0,
            "clearance_mm": 0.5,
            "lid_style": "screw",
            "fastener": "m3",
            "cutouts": [
                {
                    "kind": "rect",
                    "label": "usb",
                    "face": "front",
                    "rect": {"x_mm": 10.0, "y_mm": 5.0, "w_mm": 12.0, "h_mm": 8.0},
                }
            ],
        },
    }
    bundle = generate_bundle(spec, out_dir=tmp_path)
    assert bundle["project_name"] == "t1"
    assert "enclosure.scad" in bundle["outputs"]
    assert (tmp_path / "bom.csv").exists()


def test_runner_emits_dist_ready_files(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "t3",
        "mode": "prototype",
        "process": "fdm",
        "enclosure": {"name": "box", "inner_w_mm": 50.0, "inner_d_mm": 30.0, "inner_h_mm": 15.0},
    }
    run(spec, out_dir=tmp_path)
    assert (tmp_path / "MANIFEST.json").exists()
    assert (tmp_path / "BUILD_RECIPE.md").exists()
    assert (tmp_path / "MECH_CHECK.md").exists()
    assert (tmp_path / "PARTS.json").exists()
    assert (tmp_path / "PRINT_PLAN.md").exists()
    assert (tmp_path / "DESIGN_DECISIONS.md").exists()
    assert (tmp_path / "SIM_RESULTS.json").exists()
    assert (tmp_path / "RISK_REGISTER.md").exists()
    assert (tmp_path / "REVISION_NOTES.md").exists()


def test_invalid_bracket_blocks():
    spec = {
        "project_name": "t2",
        "mode": "prototype",
        "process": "fdm",
        "bracket": {
            "name": "bad",
            "w_mm": 10.0,
            "d_mm": 10.0,
            "t_mm": 3.0,
            "hole_d_mm": 3.2,
            "hole_spacing_mm": 50.0,
        },
    }
    bundle = generate_bundle(spec)
    assert bundle["blockers"] is True


def test_servo_mount_generates_scad(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "servo",
        "servo_mount": {
            "servo_type": "sg90",
            "plate_w_mm": 80.0,
            "plate_h_mm": 40.0,
            "plate_t_mm": 6.0,
            "clearance_mm": 0.6,
            "hole_d_mm": 2.2,
        },
    }
    out = run(spec, out_dir=tmp_path)
    assert "servo_mount.scad" in out["outputs"]
    assert (tmp_path / "servo_mount.scad").exists()
