from __future__ import annotations

import json
from pathlib import Path

import pytest

from hardware_splicer.project_intake import load_project_intake, splice_and_build_from_intake
from hardware_splicer.salvage_bridge import build_intake_salvage_package
from hardware_splicer.scratch_pipeline import (
    compile_scratch_build,
    merge_goal_modules_with_inventory,
    prove_module_ids,
    should_use_scratch_compose,
)
from hardware_splicer.plan_to_graph import splice_plan_to_build_graph


ROOT = Path(__file__).resolve().parents[1]


def test_should_use_scratch_for_nl_goal_without_named_catalog() -> None:
    assert should_use_scratch_compose(
        goal="something that measures temperature",
        build_id="generic_low_voltage_build",
        resolved_modules=[],
        strategy_mode="constrained",
    )


def test_should_not_scratch_for_plant_watering_catalog() -> None:
    assert not should_use_scratch_compose(
        goal="automatic plant waterer with soil sensor",
        build_id="automatic_plant_watering",
        resolved_modules=[{"module_id": "esp32-devkit"}, {"module_id": "soil_moisture"}],
        strategy_mode="constrained",
    )


def test_merge_goal_modules_adds_picker_ids() -> None:
    merged = merge_goal_modules_with_inventory(
        "need something that senses distance",
        [{"module_id": "usb-power-5v", "role": "pwr", "source": "user_inventory"}],
    )
    ids = [row["module_id"] for row in merged]
    assert "usb-power-5v" in ids
    assert "hc-sr04" in ids
    assert "esp32-devkit" in ids


def test_merge_goal_modules_skips_picker_when_constrained() -> None:
    merged = merge_goal_modules_with_inventory(
        "need something that senses distance",
        [
            {"module_id": "usb-power-5v", "role": "pwr", "source": "user_inventory"},
            {"module_id": "esp32-devkit", "role": "mcu", "source": "user_inventory"},
        ],
        constrained=True,
    )
    assert [row["module_id"] for row in merged] == ["usb-power-5v", "esp32-devkit"]


def test_salvage_package_scratch_mode_for_nl_brief() -> None:
    package = build_intake_salvage_package(
        goal="something that measures temperature",
        parts=[],
        constraints={"graph_mode": "scratch"},
    )
    assert package.get("graph_mode") == "scratch"
    assert package.get("recommended_build_id") == "generic_low_voltage_build"
    assert package.get("graph_input", {}).get("compose_from_inventory") is True
    assert len(package.get("compose_module_ids") or []) >= 2


def test_capability_fallback_auto_wires_when_recipe_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import hardware_splicer.plan_to_graph as plan_to_graph

    data = dict(plan_to_graph.load_catalog_data())
    recipes = dict(data.get("recipes") or {})
    recipes.pop("indicator_or_task_light", None)
    data["recipes"] = recipes
    plan_to_graph.load_catalog_data.cache_clear()
    monkeypatch.setattr(plan_to_graph, "load_catalog_data", lambda: data)

    graph, build_id, _notes, warnings = splice_plan_to_build_graph(
        {"target": {"recommended_build_id": "indicator_or_task_light"}}
    )

    assert build_id == "indicator_or_task_light"
    assert len(graph.get("nodes") or []) >= 2
    assert len(graph.get("wires") or []) >= 2
    assert any("auto-wired" in w for w in warnings)


def test_compile_scratch_build_phrase(tmp_path: Path) -> None:
    result = compile_scratch_build(
        out_dir=str(tmp_path / "scratch"),
        goal="switch a lamp with a relay",
        export_gerber=False,
    )
    assert result.ok is True, result.error
    assert "relay-1ch-5v" in result.module_ids
    assert result.compile_result is not None
    assert result.compile_result.design_quality.get("drc_pass") is True


def test_prove_module_ids() -> None:
    proof = prove_module_ids(["usb-power-5v", "esp32-devkit", "dht22"])
    assert proof["ok"] is True
    assert proof["wires"] >= 3


def test_splice_build_intake_scratch_brief(tmp_path: Path) -> None:
    intake = load_project_intake(ROOT / "examples" / "intakes" / "scratch_compose_brief.json")
    result = splice_and_build_from_intake(intake, out_dir=tmp_path, export_gerber=False)
    assert result.get("ok") is True
    salvage = result.get("salvage_package") or {}
    assert salvage.get("graph_mode") == "scratch"
    graph_path = result.get("artifacts", {}).get("build_graph")
    assert graph_path and Path(graph_path).is_file()
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    assert len(graph.get("nodes") or []) >= 3
    assert len(graph.get("wires") or []) >= 3
