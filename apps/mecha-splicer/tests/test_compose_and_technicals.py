from __future__ import annotations


def test_auto_compose_quadruped_adds_modules(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "q_auto",
        "auto_compose": True,
        "system_goal": {"application": "quadruped", "payload_kg": 1.2, "environment": "outdoor"},
    }
    out = run(spec, out_dir=tmp_path)
    assert out["composition"]["applied"] is True
    assert "rotary_joint" in out["composition"]["added_modules"]
    assert "servo_mount.scad" in out["outputs"]
    assert "rj_bearing_block.scad" in out["outputs"]
    assert "gr_base.scad" in out["outputs"]


def test_runner_emits_sim_control_safety_sections(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "robot_pack",
        "linear_axis": {"travel_mm": 180.0, "rod_length_mm": 300.0, "rod_spacing_mm": 40.0, "rod_d_mm": 8.0, "payload_n": 12.0},
        "pan_tilt": {"pan_servo": "sg90", "tilt_servo": "sg90", "max_payload_n": 3.0, "payload_offset_mm": 35.0},
    }
    out = run(spec, out_dir=tmp_path)
    assert isinstance(out.get("simulation"), list)
    assert isinstance(out.get("safety"), list)
    assert isinstance(out.get("control_profile"), dict)
    mech = (tmp_path / "MECH_CHECK.md").read_text(encoding="utf-8")
    assert "## Simulation Hints" in mech
    assert "## Safety Checks" in mech


def test_high_fidelity_simulation_mode(tmp_path):
    from src.mecha_splicer.runner import run

    spec = {
        "project_name": "hf_pack",
        "simulation_fidelity": "high",
        "linear_axis": {
            "travel_mm": 160.0,
            "rod_length_mm": 280.0,
            "rod_spacing_mm": 40.0,
            "rod_d_mm": 8.0,
            "payload_n": 16.0,
            "target_speed_mm_s": 90.0,
        },
        "pan_tilt": {"pan_servo": "mg996r", "tilt_servo": "mg996r", "max_payload_n": 8.0, "payload_offset_mm": 50.0},
    }
    out = run(spec, out_dir=tmp_path)
    sim = out.get("simulation") or []
    assert any(s.get("model") == "high" for s in sim)
    assert any(s.get("domain") == "linear_axis" for s in sim)
    assert any(s.get("model") in {"pybullet_linear_axis", "pybullet_pan_tilt", "pybullet_skip"} for s in sim)
