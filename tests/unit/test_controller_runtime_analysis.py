from __future__ import annotations

from pathlib import Path

from src.engines.system_structure_extractor import extract_board_structure, synthesize_machine_topology


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
    (comp (ref "J2")
      (value "SENSOR_PORT")
      (footprint "Connector_JST:JST_SH_SM04B"))
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
      (node (ref "U3") (pin "1"))
      (node (ref "J2") (pin "4")))
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
      (node (ref "J2") (pin "3"))
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
    (net (code "10") (name "SDA")
      (node (ref "U1") (pin "30"))
      (node (ref "J2") (pin "1")))
    (net (code "11") (name "SCL")
      (node (ref "U1") (pin "31"))
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


def _write(path: Path, contents: str) -> Path:
    path.write_text(contents + "\n", encoding="utf-8")
    return path


def test_controller_runtime_detects_usb_uart_boot_bias_and_bringup(tmp_path):
    board_path = _write(tmp_path / "esp32_ctrl.net", ESP32_CTRL_NETLIST)

    result = extract_board_structure(str(board_path), board_id="esp32_ctrl", board_name="ESP32 Control", kind="netlist")

    runtime = result["controller_runtime"]
    assert runtime["controllers"]
    controller = runtime["controllers"][0]
    assert controller["part_number"] == "ESP32-WROOM-32"

    programming_paths = runtime["programming_paths"]
    assert programming_paths
    usb_uart = next(path for path in programming_paths if path["type"] == "usb_uart_bridge")
    assert usb_uart["bridge_ref"] == "U2"
    assert usb_uart["usb_connector_refs"] == ["J1"]

    boot_constraints = runtime["boot_constraints"]
    assert any(row["pin_name"] == "GPIO0" and row["status"] == "ok" for row in boot_constraints)
    assert any(row["pin_name"] == "EN" and row["status"] == "ok" for row in boot_constraints)

    buses = runtime["bus_inventory"]
    assert any(row["bus"] == "i2c" and row["exposed_on_connector"] for row in buses)

    plan = result["bring_up_plan"]
    assert any("USB-UART" in step["title"] for step in plan)
    assert any("I2C" in step["title"] for step in plan)


def test_machine_topology_includes_board_bringup_sequence(tmp_path):
    ctrl_path = _write(tmp_path / "esp32_ctrl.net", ESP32_CTRL_NETLIST)
    sensor_path = _write(tmp_path / "sensor_io.net", SENSOR_IO_NETLIST)

    ctrl = extract_board_structure(str(ctrl_path), board_id="main_ctrl", kind="netlist")
    sensor = extract_board_structure(str(sensor_path), board_id="sensor_io", kind="netlist")
    result = synthesize_machine_topology([ctrl, sensor], machine_name="BenchDrone")

    sequence = result["machine_bring_up_sequence"]
    assert sequence
    assert sequence[0]["board_id"] == "main_ctrl"
    assert sequence[0]["first_steps"]

    power_tree = result["candidate_power_tree"]
    assert any(row["source"] == "main_ctrl:+3V3" and row["board_id"] == "sensor_io" for row in power_tree)
