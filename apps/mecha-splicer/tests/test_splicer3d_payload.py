from __future__ import annotations

from src.mecha_splicer.runner import _to_3d_splicer_description
from src.mecha_splicer.spec import ProjectSpec


def test_to_3d_splicer_description_matches_schema_shape():
    project = ProjectSpec.model_validate(
        {
            "project_name": "payload_shape",
            "electronics": {
                "device": "demo_board",
                "pcb_w_mm": 80.0,
                "pcb_h_mm": 50.0,
                "pcb_t_mm": 1.6,
                "ports": [
                    {
                        "kind": "rect",
                        "label": "usb_c",
                        "face": "front",
                        "rect": {"x_mm": 0.0, "y_mm": 18.0, "w_mm": 9.0, "h_mm": 4.0},
                    },
                    {
                        "kind": "rect",
                        "label": "hdmi",
                        "face": "back",
                        "rect": {"x_mm": 60.0, "y_mm": 46.0, "w_mm": 14.0, "h_mm": 5.0},
                    },
                ],
                "mounts": [
                    {"x_mm": 6.0, "y_mm": 6.0, "d_mm": 2.2},
                    {"x_mm": 74.0, "y_mm": 44.0, "d_mm": 2.2},
                ],
            },
            "enclosure": {
                "name": "box",
                "inner_w_mm": 90.0,
                "inner_d_mm": 60.0,
                "inner_h_mm": 24.0,
                "wall_mm": 2.4,
                "lid_mm": 2.0,
                "clearance_mm": 0.6,
            },
        }
    )

    desc = _to_3d_splicer_description(project)

    assert desc["version"] == "v1"
    assert desc["device"] == "demo_board"
    assert desc["pcb"]["width_mm"] == 80.0
    assert desc["pcb"]["height_mm"] == 50.0
    assert desc["pcb"]["thickness_mm"] == 1.6
    assert "corner_radius_mm" in desc["pcb"]
    assert "lip_mm" in desc["enclosure"]
    assert "fillet_mm" in desc["enclosure"]

    assert len(desc["ports"]) == 2
    assert desc["ports"][0]["name"] == "usb_c"
    assert desc["ports"][0]["side"] == "bottom"  # front -> bottom
    assert desc["ports"][1]["side"] == "top"  # back -> top
    assert desc["ports"][0]["type"] == "rect"
    assert "x_mm" in desc["ports"][0] and "w_mm" in desc["ports"][0]

    assert len(desc["mounts"]) == 2
    assert "diameter_mm" in desc["mounts"][0]


def test_runner_falls_back_to_script_when_stl_render_fails(monkeypatch, tmp_path):
    import src.mecha_splicer.runner as runner

    class FakeClient:
        def splice_stl(self, payload):
            raise RuntimeError("cadquery missing")

        def splice_script(self, payload):
            return {"ok": True, "device": payload["device"], "script": "result = case"}

    monkeypatch.setattr(runner, "Splicer3DClient", lambda: FakeClient())

    bundle = runner.run(
        {
            "project_name": "fallback",
            "electronics": {
                "device": "demo_board",
                "pcb_w_mm": 80,
                "pcb_h_mm": 50,
                "pcb_t_mm": 1.6,
            },
        },
        out_dir=tmp_path,
        use_3d_splicer=True,
        render_stl=True,
        simulation_fidelity="starter",
    )

    assert bundle["splicer3d"]["ok"] is False
    assert bundle["splicer3d"]["mode"] == "script_fallback"
    assert bundle["splicer3d"]["script"] == "result = case"
    assert (tmp_path / "splicer3d.json").exists()
