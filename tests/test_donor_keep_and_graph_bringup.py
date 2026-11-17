"""Donor-keep honesty + post-compile graph-true bring-up."""

from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.integrations.qwen_workshop_review import apply_workshop_review
from hardware_splicer.module_resolver import fill_salvage_gaps
from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake
from hardware_splicer.salvage_intelligence import build_bringup_card
from hardware_splicer.scratch_pipeline import merge_goal_modules_with_inventory

ROOT = Path(__file__).resolve().parents[1]


def test_fill_salvage_gaps_strips_gap_fill_driver_when_donor_bound() -> None:
    rows = [
        {
            "module_id": "l298n",
            "role": "drv",
            "source": "donor_functional_salvage",
            "part_name": "donor H-bridge",
            "connector_refs": ["J_MOTOR_L"],
        },
        {
            "module_id": "l298n",
            "role": "drv",
            "source": "gap_fill",
            "part_name": "motor driver (gap fill)",
        },
        {"module_id": "dc_motor_3v_6v", "role": "mot", "source": "user_inventory"},
    ]
    out = fill_salvage_gaps(rows, parts=[{"name": "motor", "type": "dc_motor"}])
    assert any(r.get("source") == "donor_functional_salvage" for r in out)
    assert not any(r.get("source") == "gap_fill" and r.get("module_id") == "l298n" for r in out)


def test_goal_picker_skips_catalog_driver_when_donor_bound() -> None:
    resolved = [
        {
            "module_id": "l298n",
            "role": "drv",
            "source": "donor_functional_salvage",
        },
        {"module_id": "esp32-devkit", "role": "mcu", "source": "user_inventory"},
    ]
    merged = merge_goal_modules_with_inventory(
        "build a robot drive base with two DC motors",
        resolved,
        constrained=False,
    )
    drivers = [r for r in merged if r.get("module_id") == "l298n"]
    assert len(drivers) == 1
    assert drivers[0].get("source") == "donor_functional_salvage"
    assert not any(
        r.get("source") == "goal_picker" and r.get("module_id") in {"l298n", "a4988-stepper"}
        for r in merged
    )


def test_workshop_review_refuses_driver_when_donor_bound() -> None:
    resolved = [
        {
            "module_id": "l298n",
            "role": "drv",
            "source": "donor_functional_salvage",
        }
    ]
    review = {
        "ok": True,
        "confidence": 0.9,
        "add_modules": [{"module_id": "a4988-stepper", "role": "drv", "reason": "buy stepper drv"}],
    }
    out = apply_workshop_review(resolved, review)
    assert not any(r.get("module_id") == "a4988-stepper" for r in out)


def test_bringup_from_compiled_graph_marks_sourced() -> None:
    graph = {
        "nodes": [
            {"id": "n1", "moduleId": "esp32-devkit", "role": "mcu"},
            {"id": "n2", "moduleId": "l298n", "role": "drv"},
        ],
        "wires": [
            {"from": {"nodeId": "n1", "pinId": "D2"}, "to": {"nodeId": "n2", "pinId": "IN1"}},
            {"from": {"nodeId": "n1", "pinId": "D3"}, "to": {"nodeId": "n2", "pinId": "IN2"}},
        ],
    }
    card = build_bringup_card(
        goal="robot",
        resolved_modules=[{"module_id": "esp32-devkit"}, {"module_id": "l298n"}],
        build_graph=graph,
    )
    assert card.get("sourced_from_graph") is True
    pins = {(r.get("from_pin"), r.get("to_pin")) for r in card.get("connections") or []}
    assert ("D2", "IN1") in pins
    assert ("D3", "IN2") in pins
    assert "compiled build_graph" in " ".join(card.get("bench_checks") or [])


def test_enabot_post_compile_bringup_matches_graph(tmp_path: Path) -> None:
    intake = load_project_intake(ROOT / "examples" / "intakes" / "splice_vibe_enabot_lite_brief.json")
    result = splice_and_build_from_intake(
        intake,
        out_dir=tmp_path / "enabot",
        export_gerber=False,
        request_id="enabot_bringup",
    )
    assert result.get("ok") is True
    bringup = result.get("bringup_card") or {}
    assert bringup.get("sourced_from_graph") is True

    bringup_disk = json.loads((tmp_path / "enabot" / "BRINGUP_CARD.json").read_text(encoding="utf-8"))
    assert bringup_disk.get("sourced_from_graph") is True

    wiring = (tmp_path / "enabot" / "WIRING_GUIDE.md").read_text(encoding="utf-8")
    assert "compiled build_graph" in wiring or "Bench hookup" in wiring

    gpio = bringup.get("gpio_assignments") or []
    assert gpio, bringup
    # Control pins should surface as IN1–IN4 on the driver side
    to_pins = {str(r.get("to_pin") or "").upper() for r in gpio}
    from_pins = {str(r.get("from_pin") or "").upper() for r in gpio}
    assert {"IN1", "IN2", "IN3", "IN4"} & (to_pins | from_pins)
