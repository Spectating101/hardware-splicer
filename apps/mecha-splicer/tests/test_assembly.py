from __future__ import annotations


def test_assembly_emits_scad(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm",
        "rotary_joint": {"bearing": "608zz", "shaft_d_mm": 8.0},
        "assembly": {
            "instances": [
                {
                    "id": "base",
                    "output_file": "rj_bearing_block.scad",
                    "module": "rj_bearing_block",
                    "fixed": True,
                    "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0},
                },
                {"id": "arm", "output_file": "rj_arm.scad", "module": "rj_arm", "transform": {"x_mm": 50, "y_mm": 0, "z_mm": 0}},
            ],
            "mates": [
                {
                    "name": "arm_to_block_origin",
                    "a_instance": "base",
                    "a_anchor": "center",
                    "b_instance": "arm",
                    "b_anchor": "origin",
                    "offset": {"x_mm": 60, "y_mm": 0, "z_mm": 0},
                }
            ]
        },
    }
    out = run(spec, out_dir=tmp_path)
    assert "ASSEMBLY.scad" in out["outputs"]
    assert (tmp_path / "ASSEMBLY.scad").exists()
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "use <rj_bearing_block.scad>;" in scad
    assert "use <rj_arm.scad>;" in scad


def test_assembly_auto_anchors_allow_mating_without_manual_anchors(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm2",
        "linear_axis": {"rod_d_mm": 8.0, "rod_spacing_mm": 40.0, "rod_length_mm": 320.0, "travel_mm": 200.0, "belt_width_mm": 6.0, "pulley_teeth": 20},
        "assembly": {
            "instances": [
                {"id": "m", "output_file": "motor_mount.scad", "module": "motor_mount", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "i", "output_file": "idler_mount.scad", "module": "idler_mount", "transform": {"x_mm": 999, "y_mm": 999, "z_mm": 0}},
            ],
            "mates": [
                {"name": "align_rods", "a_instance": "m", "a_anchor": "rod_left", "b_instance": "i", "b_anchor": "rod_left", "offset": {"x_mm": 80, "y_mm": 0, "z_mm": 0}}
            ],
        },
    }
    out = run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    # The idler mount should not keep its explicit 999,999 placement once the mate is solved.
    assert "999.000" not in scad


def test_mate_kind_shaft_into_bearing_defaults(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm3",
        "rotary_joint": {"bearing": "608zz", "shaft_d_mm": 8.0},
        "assembly": {
            "instances": [
                {"id": "blk", "output_file": "rj_bearing_block.scad", "module": "rj_bearing_block", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "arm", "output_file": "rj_arm.scad", "module": "rj_arm", "transform": {"x_mm": 999, "y_mm": 999, "z_mm": 0}},
            ],
            "mates": [
                {
                    "name": "shaft_in_bearing",
                    "kind": "shaft_into_bearing",
                    "a_instance": "blk",
                    "a_anchor": "",
                    "b_instance": "arm",
                    "b_anchor": "",
                    "offset": {"x_mm": 0, "y_mm": 0, "z_mm": 0},
                }
            ],
        },
    }
    run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "999.000" not in scad


def test_mate_kind_mount_plane_flush(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm4",
        "linear_axis": {"rod_d_mm": 8.0, "rod_spacing_mm": 40.0, "rod_length_mm": 320.0, "travel_mm": 200.0, "belt_width_mm": 6.0, "pulley_teeth": 20},
        "belt_reduction": {"center_distance_mm": 60.0, "motor_pulley_teeth": 20, "driven_pulley_teeth": 60},
        "assembly": {
            "instances": [
                {"id": "mm", "output_file": "motor_mount.scad", "module": "motor_mount", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "br", "output_file": "br_reduction_plate.scad", "module": "br_reduction_plate", "transform": {"x_mm": 999, "y_mm": 0, "z_mm": 50}},
            ],
            "mates": [
                {
                    "name": "flush_planes",
                    "kind": "mount_plane_flush",
                    "a_instance": "mm",
                    "a_anchor": "",
                    "b_instance": "br",
                    "b_anchor": "",
                    "offset": {"x_mm": 140, "y_mm": 0, "z_mm": 0},
                }
            ],
        },
    }
    run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "999.000" not in scad


def test_mate_kind_bolt_pattern_nema17(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm5",
        "linear_axis": {"rod_d_mm": 8.0, "rod_spacing_mm": 40.0, "rod_length_mm": 320.0, "travel_mm": 200.0, "belt_width_mm": 6.0, "pulley_teeth": 20},
        "belt_reduction": {"center_distance_mm": 60.0, "motor_pulley_teeth": 20, "driven_pulley_teeth": 60},
        "assembly": {
            "instances": [
                {"id": "mm", "output_file": "motor_mount.scad", "module": "motor_mount", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "br", "output_file": "br_reduction_plate.scad", "module": "br_reduction_plate", "transform": {"x_mm": 999, "y_mm": 999, "z_mm": 0}},
            ],
            "mates": [
                {"name": "match_ne_bolt", "kind": "bolt_pattern", "a_instance": "mm", "a_anchor": "", "b_instance": "br", "b_anchor": "", "params": {"pattern": "nema17", "hole": "ne"}},
            ],
        },
    }
    run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "999.000" not in scad


def test_bolt_pattern_full_alignment(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm6",
        "linear_axis": {"rod_d_mm": 8.0, "rod_spacing_mm": 40.0, "rod_length_mm": 320.0, "travel_mm": 200.0, "belt_width_mm": 6.0, "pulley_teeth": 20},
        "belt_reduction": {"center_distance_mm": 60.0, "motor_pulley_teeth": 20, "driven_pulley_teeth": 60},
        "assembly": {
            "instances": [
                {"id": "mm", "output_file": "motor_mount.scad", "module": "motor_mount", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "br", "output_file": "br_reduction_plate.scad", "module": "br_reduction_plate", "transform": {"x_mm": 999, "y_mm": 999, "z_mm": 0}},
            ],
            "mates": [
                {
                    "name": "full_pattern",
                    "kind": "bolt_pattern",
                    "priority": 10,
                    "a_instance": "mm",
                    "a_anchor": "",
                    "b_instance": "br",
                    "b_anchor": "",
                    "params": {"pattern": "nema17", "align": "full", "a1": "ne", "a2": "nw", "b1": "ne", "b2": "nw"},
                }
            ],
        },
    }
    run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "999.000" not in scad


def test_conflict_resolution_priority_override(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm7",
        "linear_axis": {"rod_d_mm": 8.0, "rod_spacing_mm": 40.0, "rod_length_mm": 320.0, "travel_mm": 200.0, "belt_width_mm": 6.0, "pulley_teeth": 20},
        "assembly": {
            "instances": [
                {"id": "m", "output_file": "motor_mount.scad", "module": "motor_mount", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "i", "output_file": "idler_mount.scad", "module": "idler_mount", "transform": {"x_mm": 5, "y_mm": 5, "z_mm": 0}},
            ],
            "mates": [
                # Low priority: place idler far away
                {"name": "low", "priority": 1, "kind": "anchor", "a_instance": "m", "a_anchor": "center", "b_instance": "i", "b_anchor": "center", "offset": {"x_mm": 10, "y_mm": 0, "z_mm": 0}},
                # High priority: contradict and override
                {"name": "high", "priority": 99, "kind": "anchor", "a_instance": "m", "a_anchor": "center", "b_instance": "i", "b_anchor": "center", "offset": {"x_mm": 200, "y_mm": 0, "z_mm": 0}},
            ],
        },
    }
    run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "Conflict:" in scad


def test_bolt_pattern_best_fit(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm8",
        "linear_axis": {"rod_d_mm": 8.0, "rod_spacing_mm": 40.0, "rod_length_mm": 320.0, "travel_mm": 200.0, "belt_width_mm": 6.0, "pulley_teeth": 20},
        "belt_reduction": {"center_distance_mm": 60.0, "motor_pulley_teeth": 20, "driven_pulley_teeth": 60},
        "assembly": {
            "instances": [
                {"id": "mm", "output_file": "motor_mount.scad", "module": "motor_mount", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "br", "output_file": "br_reduction_plate.scad", "module": "br_reduction_plate", "transform": {"x_mm": 999, "y_mm": 999, "z_mm": 0, "rz_deg": 33}},
            ],
            "mates": [
                {
                    "name": "bestfit",
                    "kind": "bolt_pattern",
                    "priority": 10,
                    "a_instance": "mm",
                    "a_anchor": "",
                    "b_instance": "br",
                    "b_anchor": "",
                    "params": {"pattern": "nema17", "align": "best_fit", "holes": ["ne", "nw", "se", "sw"]},
                }
            ],
        },
    }
    run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "999.000" not in scad


def test_axis_collinear_places_arm(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "asm9",
        "rotary_joint": {"bearing": "608zz", "shaft_d_mm": 8.0},
        "assembly": {
            "instances": [
                {"id": "blk", "output_file": "rj_bearing_block.scad", "module": "rj_bearing_block", "fixed": True, "transform": {"x_mm": 0, "y_mm": 0, "z_mm": 0}},
                {"id": "arm", "output_file": "rj_arm.scad", "module": "rj_arm", "transform": {"x_mm": 999, "y_mm": 999, "z_mm": 0}},
            ],
            "mates": [
                {"name": "col", "kind": "axis_collinear", "priority": 10, "a_instance": "blk", "a_anchor": "", "b_instance": "arm", "b_anchor": "", "offset": {"x_mm": 0, "y_mm": 0, "z_mm": 0}}
            ],
        },
    }
    run(spec, out_dir=tmp_path)
    scad = (tmp_path / "ASSEMBLY.scad").read_text(encoding="utf-8")
    assert "999.000" not in scad
