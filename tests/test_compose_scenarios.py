"""End-to-end compose + wire + DRC scenarios (Python engine, no Node)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Optional

import pytest

from hardware_splicer.auto_wire import (
    compose_build_graph_from_canvas_nodes,
    compose_build_graph_from_module_ids,
)
from hardware_splicer.module_picker import pick_modules_for_goal
from hardware_splicer.pcb.build_to_geometry import build_graph_to_geometry
from hardware_splicer.pcb.drc import run_drc
from hardware_splicer.pcb.safety_rules import analyze_build


def _module_id_for_node(graph: Mapping[str, Any], node_id: str) -> Optional[str]:
    for node in graph.get("nodes") or []:
        if node.get("id") == node_id:
            return node.get("moduleId")
    return None


def _has_wire(graph: Mapping[str, Any], module_id: str, pin_id: str) -> bool:
    for wire in graph.get("wires") or []:
        from_mod = _module_id_for_node(graph, wire["from"]["nodeId"])
        to_mod = _module_id_for_node(graph, wire["to"]["nodeId"])
        if wire["from"]["pinId"] == pin_id and from_mod == module_id:
            return True
        if wire["to"]["pinId"] == pin_id and to_mod == module_id:
            return True
    return False


def _mcu_gpio_to_sensor(graph: Mapping[str, Any], sensor_id: str, sensor_pin: str) -> bool:
    for wire in graph.get("wires") or []:
        from_mod = _module_id_for_node(graph, wire["from"]["nodeId"])
        to_mod = _module_id_for_node(graph, wire["to"]["nodeId"])
        involves_sensor = sensor_id in (from_mod, to_mod)
        involves_pin = sensor_pin in (wire["from"]["pinId"], wire["to"]["pinId"])
        involves_mcu = "esp32-devkit" in (from_mod, to_mod)
        if involves_sensor and involves_pin and involves_mcu:
            return True

    for wire in graph.get("wires") or []:
        from_mod = _module_id_for_node(graph, wire["from"]["nodeId"])
        to_mod = _module_id_for_node(graph, wire["to"]["nodeId"])
        to_sensor = (
            from_mod == sensor_id and wire["from"]["pinId"] == sensor_pin
        ) or (to_mod == sensor_id and wire["to"]["pinId"] == sensor_pin)
        shifter_pin = wire["from"]["pinId"] in ("HV1", "HV2", "LV1", "LV2") or wire["to"]["pinId"] in (
            "HV1", "HV2", "LV1", "LV2"
        )
        shifter_involved = "level-shifter-4ch" in (from_mod, to_mod)
        if to_sensor and shifter_involved and shifter_pin:
            return True
    return False


def _verify_compose(phrase: str, *, sensor_id: Optional[str] = None, signal_pin: Optional[str] = None) -> None:
    pick = pick_modules_for_goal(phrase)
    assert len(pick.module_ids) >= 2, f"pick too small: {pick.module_ids}"

    composed = compose_build_graph_from_module_ids(pick.module_ids)
    graph = composed["graph"]
    assert len(graph.get("nodes") or []) >= 2, "compose returned <2 nodes"
    assert len(graph.get("wires") or []) >= 3, f"only {len(graph.get('wires') or [])} wires"

    safety = analyze_build(graph)
    errors = [w for w in safety if w.get("level") == "error"]
    assert not errors, f"safety errors: {[w.get('message') for w in errors]}"

    drc = run_drc(build_graph_to_geometry(graph))
    assert drc.get("pass"), f"DRC fail: {drc.get('violations')}"

    if sensor_id and signal_pin:
        assert _mcu_gpio_to_sensor(graph, sensor_id, signal_pin), (
            f"missing MCU→{sensor_id}.{signal_pin}"
        )


def _load_compose_cases() -> list[tuple[str, dict[str, str]]]:
    data_path = Path(__file__).resolve().parent / "data" / "compose_phrases.json"
    rows = json.loads(data_path.read_text(encoding="utf-8"))
    cases: list[tuple[str, dict[str, str]]] = []
    for row in rows:
        phrase = str(row.get("phrase") or "")
        opts = {k: str(v) for k, v in row.items() if k != "phrase" and v}
        cases.append((phrase, opts))
    return cases


COMPOSE_CASES = _load_compose_cases()


@pytest.mark.parametrize("phrase,opts", COMPOSE_CASES)
def test_compose_scenario(phrase: str, opts: Mapping[str, str]) -> None:
    _verify_compose(phrase, sensor_id=opts.get("sensor_id"), signal_pin=opts.get("signal_pin"))


def test_pump_fed_through_mosfet() -> None:
    phrase = "control a 5v pump for drip irrigation"
    pick = pick_modules_for_goal(phrase)
    graph = compose_build_graph_from_module_ids(pick.module_ids)["graph"]
    pump_id = next((mid for mid in pick.module_ids if re.search(r"pump|fan", mid)), None)
    assert pump_id
    powered = any(
        (
            _module_id_for_node(graph, w["from"]["nodeId"]) == "mosfet-irlz44n"
            and w["from"]["pinId"] == "VOUT+"
            and _module_id_for_node(graph, w["to"]["nodeId"]) == pump_id
        )
        or (
            _module_id_for_node(graph, w["to"]["nodeId"]) == "mosfet-irlz44n"
            and w["to"]["pinId"] == "VOUT+"
            and _module_id_for_node(graph, w["from"]["nodeId"]) == pump_id
        )
        for w in graph.get("wires") or []
    )
    assert powered, f"{pump_id} not fed through MOSFET VOUT+"


def test_partial_add_distance_sensor() -> None:
    base = compose_build_graph_from_canvas_nodes(
        [
            {"id": "n1", "moduleId": "usb-power-5v"},
            {"id": "n2", "moduleId": "esp32-devkit"},
        ]
    )
    merged = compose_build_graph_from_canvas_nodes(
        [
            {"id": "n1", "moduleId": "usb-power-5v"},
            {"id": "n2", "moduleId": "esp32-devkit"},
            {"id": "n3", "moduleId": "hc-sr04"},
        ]
    )
    assert _mcu_gpio_to_sensor(merged, "hc-sr04", "TRIG")
    assert len(merged.get("wires") or []) > len(base.get("wires") or [])


def test_env_sensor_dedup_prefers_bme280() -> None:
    pick = pick_modules_for_goal("environmental sensor for pressure and humidity")
    assert "joystick_module" not in pick.module_ids
    assert not ("dht22" in pick.module_ids and "bme280" in pick.module_ids)
    assert "bme280" in pick.module_ids
