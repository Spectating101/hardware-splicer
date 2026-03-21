from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import api_server


MAIN_CTRL_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "STM32F405")
      (footprint "Package_QFP:LQFP-64"))
    (comp (ref "U2")
      (value "AMS1117-3.3")
      (footprint "Package_TO_SOT_SMD:SOT-223"))
    (comp (ref "J1")
      (value "BAT_IN")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
    (comp (ref "J2")
      (value "SENSOR_PORT")
      (footprint "Connector_JST:JST_SH_SM04B"))
  )
  (nets
    (net (code "1") (name "VIN")
      (node (ref "J1") (pin "1"))
      (node (ref "U2") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "10"))
      (node (ref "U2") (pin "2"))
      (node (ref "J2") (pin "4")))
    (net (code "3") (name "+3V3")
      (node (ref "U2") (pin "3"))
      (node (ref "U1") (pin "1"))
      (node (ref "J2") (pin "3")))
    (net (code "4") (name "SCL")
      (node (ref "U1") (pin "23"))
      (node (ref "J2") (pin "1")))
    (net (code "5") (name "SDA")
      (node (ref "U1") (pin "24"))
      (node (ref "J2") (pin "2")))
  )
)
""".strip()


SENSOR_IO_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "BME280")
      (footprint "Package_LGA:LGA-8"))
    (comp (ref "J1")
      (value "MAIN_CTRL")
      (footprint "Connector_JST:JST_SH_SM04B"))
  )
  (nets
    (net (code "1") (name "GND")
      (node (ref "J1") (pin "4"))
      (node (ref "U1") (pin "8")))
    (net (code "2") (name "+3V3")
      (node (ref "J1") (pin "3"))
      (node (ref "U1") (pin "1")))
    (net (code "3") (name "SCL")
      (node (ref "J1") (pin "1"))
      (node (ref "U1") (pin "6")))
    (net (code "4") (name "SDA")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "5")))
  )
)
""".strip()


ESP32_CTRL_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "ESP32-WROOM-32")
      (footprint "RF_Module:ESP32-WROOM-32"))
    (comp (ref "U2")
      (value "CP2102")
      (footprint "Package_QFN:QFN-28"))
    (comp (ref "U3")
      (value "AMS1117-3.3")
      (footprint "Package_TO_SOT_SMD:SOT-223"))
    (comp (ref "J1")
      (value "USB_CONN")
      (footprint "Connector_USB:USB_Micro-B"))
    (comp (ref "R1")
      (value "10K")
      (footprint "Resistor_SMD:R_0603"))
    (comp (ref "R2")
      (value "10K")
      (footprint "Resistor_SMD:R_0603"))
  )
  (nets
    (net (code "1") (name "VBUS")
      (node (ref "J1") (pin "1"))
      (node (ref "U2") (pin "7"))
      (node (ref "U2") (pin "8"))
      (node (ref "U3") (pin "3")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "15"))
      (node (ref "U1") (pin "38"))
      (node (ref "U2") (pin "3"))
      (node (ref "U3") (pin "1")))
    (net (code "3") (name "USB_D+")
      (node (ref "J1") (pin "3"))
      (node (ref "U2") (pin "4")))
    (net (code "4") (name "USB_D-")
      (node (ref "J1") (pin "4"))
      (node (ref "U2") (pin "5")))
    (net (code "5") (name "+3V3")
      (node (ref "U1") (pin "1"))
      (node (ref "U2") (pin "6"))
      (node (ref "U3") (pin "2"))
      (node (ref "R1") (pin "1"))
      (node (ref "R2") (pin "1")))
    (net (code "6") (name "EN")
      (node (ref "U1") (pin "2"))
      (node (ref "R1") (pin "2")))
    (net (code "7") (name "GPIO0")
      (node (ref "U1") (pin "25"))
      (node (ref "R2") (pin "2")))
    (net (code "8") (name "UART_TX")
      (node (ref "U1") (pin "34"))
      (node (ref "U2") (pin "23")))
    (net (code "9") (name "UART_RX")
      (node (ref "U1") (pin "35"))
      (node (ref "U2") (pin "22")))
  )
)
""".strip()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CIRCUIT_AI_REQUIRE_API_KEY", "false")
    monkeypatch.setenv("CIRCUIT_AI_API_KEYS", "")
    monkeypatch.setenv("CIRCUIT_AI_USAGE_DB", str(tmp_path / "usage.sqlite"))
    return api_server.app.test_client()


def test_v2_system_extract_board(client, tmp_path):
    netlist_path = tmp_path / "main_ctrl.net"
    netlist_path.write_text(MAIN_CTRL_NETLIST + "\n", encoding="utf-8")

    r = client.post(
        "/api/v2/system/extract-board",
        data=json.dumps({"path": str(netlist_path), "kind": "netlist", "board_id": "main_ctrl"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    result = data.get("result") or {}
    assert result.get("primary_role") == "controller"
    assert any(row.get("interface") == "i2c" for connector in (result.get("connectors") or []) for row in (connector.get("interfaces") or []))


def test_v2_system_extract_machine(client, tmp_path):
    main_path = tmp_path / "main_ctrl.net"
    sensor_path = tmp_path / "sensor_io.net"
    main_path.write_text(MAIN_CTRL_NETLIST + "\n", encoding="utf-8")
    sensor_path.write_text(SENSOR_IO_NETLIST + "\n", encoding="utf-8")

    payload = {
        "machine_name": "BenchBot",
        "boards": [
            {"board_id": "main_ctrl", "path": str(main_path), "kind": "netlist"},
            {"board_id": "sensor_io", "path": str(sensor_path), "kind": "netlist"},
        ],
    }
    r = client.post("/api/v2/system/extract-machine", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 200
    data = r.get_json() or {}
    assert data.get("status") == "success"
    result = data.get("result") or {}
    assert any(row.get("interface") == "i2c" for row in (result.get("candidate_interconnects") or []))
    assert any(row.get("source") == "main_ctrl:+3V3" for row in (result.get("candidate_power_tree") or []))


def test_v2_system_extract_board_reports_controller_runtime(client, tmp_path):
    netlist_path = tmp_path / "esp32_ctrl.net"
    netlist_path.write_text(ESP32_CTRL_NETLIST + "\n", encoding="utf-8")

    r = client.post(
        "/api/v2/system/extract-board",
        data=json.dumps({"path": str(netlist_path), "kind": "netlist", "board_id": "esp32_ctrl"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json() or {}
    result = data.get("result") or {}
    runtime = result.get("controller_runtime") or {}
    assert (runtime.get("controllers") or [])[0]["part_number"] == "ESP32-WROOM-32"
    assert any(path.get("type") == "usb_uart_bridge" for path in (runtime.get("programming_paths") or []))


def test_v2_system_extract_board_reports_power_control_analysis(client, tmp_path):
    netlist_path = tmp_path / "high_drop_ctrl.net"
    netlist_path.write_text(
        """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "STM32F405")
      (footprint "Package_QFP:LQFP-64"))
    (comp (ref "U2")
      (value "AMS1117-3.3")
      (footprint "Package_TO_SOT_SMD:SOT-223"))
    (comp (ref "J1")
      (value "BAT_IN")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
  )
  (nets
    (net (code "1") (name "+12V")
      (node (ref "J1") (pin "1"))
      (node (ref "U2") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "10"))
      (node (ref "U2") (pin "2")))
    (net (code "3") (name "+3V3")
      (node (ref "U2") (pin "3"))
      (node (ref "U1") (pin "1")))
  )
)
""".strip()
        + "\n",
        encoding="utf-8",
    )

    r = client.post(
        "/api/v2/system/extract-board",
        data=json.dumps({"path": str(netlist_path), "kind": "netlist", "board_id": "high_drop_ctrl"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json() or {}
    result = data.get("result") or {}
    analysis = result.get("power_control_analysis") or {}
    assert any(stage.get("kind") == "ldo" for stage in (analysis.get("power_stages") or []))
    assert any(finding.get("topic") == "linear_regulator_drop" for finding in (analysis.get("risk_findings") or []))
