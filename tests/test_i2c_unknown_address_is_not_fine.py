"""An address HS cannot determine is never read as fine."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.pcb.safety_rules import analyze_build
from hardware_splicer.product_api import create_product_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("HARDWARE_SPLICER_OUTPUT_ROOT", str(tmp_path / "out"))
    monkeypatch.setenv("HARDWARE_SPLICER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_SALVAGE", "0")
    monkeypatch.setenv("HARDWARE_SPLICER_OFFLINE_COMPOSE", "0")
    return TestClient(create_product_app())


def _graph(*module_ids: str) -> dict:
    return compose_build_graph_from_module_ids(list(module_ids), auto_repair=False)["graph"]


def _canvas(client, graph: dict) -> dict:
    return client.post(
        "/v1/compose-canvas", json={"nodes": graph["nodes"], "wires": graph["wires"], "export_gerber": False, "compact": True}
    ).json()


@pytest.mark.parametrize("parts", [("bmp280", "bmp280"), ("ds1307_rtc", "ds1307_rtc"), ("mcp4725-dac", "mcp4725-dac")])
def test_two_identical_devices_with_unknown_addresses_are_a_blocking_warning_for_a_person(parts) -> None:
    graph = _graph("esp32-devkit", *parts, "usb-power-5v")

    [unknown] = [w for w in analyze_build(graph) if w.get("code") == "i2c_address_unknown"]

    assert unknown["level"] == "warn"
    assert unknown["requires_person"] is True
    assert "cannot tell" in unknown["message"]


def test_the_compact_verdict_does_not_call_two_unknown_identical_sensors_ready(client) -> None:
    verdict = _canvas(client, _graph("esp32-devkit", "bmp280", "bmp280", "usb-power-5v"))

    assert verdict["build_ready"] is False
    assert any(step["code"] == "i2c_address_unknown" for step in verdict["needs_a_person"])
    assert any("cannot tell" in b for b in verdict["blockers"])


def test_an_unknown_part_beside_a_known_one_stays_visible_in_the_compact_verdict(client) -> None:
    verdict = _canvas(client, _graph("esp32-devkit", "bmp280", "bme280", "usb-power-5v"))

    assert any("cannot tell" in n for n in verdict["notes"] + [s["message"] for s in verdict["needs_a_person"]])


