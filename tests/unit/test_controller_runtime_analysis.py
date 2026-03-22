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


TINYPICO_MODULE_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "Tinypico")
      (footprint "Custom:Tinypico"))
    (comp (ref "U2")
      (value "MCP1642B")
      (footprint "Package_SO:MSOP-8"))
    (comp (ref "J1")
      (value "SERVO_PORT")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x03"))
  )
  (nets
    (net (code "1") (name "VBAT_Rail")
      (node (ref "U1") (pin "1"))
      (node (ref "U2") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "U1") (pin "2"))
      (node (ref "U2") (pin "2"))
      (node (ref "J1") (pin "1")))
    (net (code "3") (name "3V3_Rail")
      (node (ref "U1") (pin "3")))
    (net (code "4") (name "5V_Rail")
      (node (ref "U2") (pin "3"))
      (node (ref "J1") (pin "2")))
    (net (code "5") (name "ServoPWM")
      (node (ref "U1") (pin "4"))
      (node (ref "J1") (pin "3")))
    (net (code "6") (name "Reset")
      (node (ref "U1") (pin "5")))
  )
)
""".strip()


ESP32_MOTOR_CTRL_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "ESP32-WROOM-32")
      (footprint "RF_Module:ESP32-WROOM-32"))
    (comp (ref "U2")
      (value "CP2102")
      (footprint "Package_QFN:QFN-28"))
    (comp (ref "U3")
      (value "LM5101A")
      (footprint "WSON-8:WSON-8"))
    (comp (ref "U4")
      (value "INA240A2")
      (footprint "Housings_SSOP:TSSOP-8_4.4x3mm_Pitch0.65mm"))
    (comp (ref "J1")
      (value "USB_CONN")
      (footprint "Connector_USB:USB_Micro-B"))
  )
  (nets
    (net (code "1") (name "VBUS")
      (node (ref "J1") (pin "1"))
      (node (ref "U2") (pin "7"))
      (node (ref "U2") (pin "8")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "15"))
      (node (ref "U1") (pin "38"))
      (node (ref "U2") (pin "3"))
      (node (ref "U3") (pin "7"))
      (node (ref "U4") (pin "1"))
      (node (ref "U4") (pin "4"))
      (node (ref "U4") (pin "6")))
    (net (code "3") (name "USB_D+")
      (node (ref "J1") (pin "3"))
      (node (ref "U2") (pin "4")))
    (net (code "4") (name "USB_D-")
      (node (ref "J1") (pin "4"))
      (node (ref "U2") (pin "5")))
    (net (code "5") (name "+3V3")
      (node (ref "U1") (pin "1"))
      (node (ref "U2") (pin "6"))
      (node (ref "U4") (pin "5")))
    (net (code "6") (name "EN")
      (node (ref "U1") (pin "2")))
    (net (code "7") (name "GPIO0")
      (node (ref "U1") (pin "25")))
    (net (code "8") (name "UART_TX")
      (node (ref "U1") (pin "34"))
      (node (ref "U2") (pin "23")))
    (net (code "9") (name "UART_RX")
      (node (ref "U1") (pin "35"))
      (node (ref "U2") (pin "22")))
    (net (code "10") (name "+12V")
      (node (ref "U3") (pin "1")))
    (net (code "11") (name "/Power_FET/PH_A")
      (node (ref "U3") (pin "4")))
    (net (code "12") (name "/Motor/PWM_H_A")
      (node (ref "U1") (pin "30"))
      (node (ref "U3") (pin "5")))
    (net (code "13") (name "/Motor/PWM_L_A")
      (node (ref "U1") (pin "31"))
      (node (ref "U3") (pin "6")))
    (net (code "14") (name "/Motor/I_SENS_A")
      (node (ref "U1") (pin "32"))
      (node (ref "U4") (pin "7")))
    (net (code "15") (name "/Motor/FAULT_A")
      (node (ref "U1") (pin "33")))
    (net (code "16") (name "Net-(R26-Pad3)")
      (node (ref "U4") (pin "2")))
    (net (code "17") (name "Net-(R26-Pad4)")
      (node (ref "U4") (pin "3")))
    (net (code "18") (name "Net-(R30-Pad1)")
      (node (ref "U4") (pin "8")))
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
    firmware_surface = runtime["firmware_surface"]
    assert firmware_surface["flash_strategy"]["primary_method"] == "usb_uart_bridge"
    assert "firmware_update" in (firmware_surface.get("runtime_functions") or [])
    assert "i2c_expansion" in (firmware_surface.get("runtime_functions") or [])
    assert any(row["connector_ref"] == "J1" for row in (firmware_surface.get("external_interfaces") or []))

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


def test_controller_runtime_infers_module_usb_path_for_dev_board_modules(tmp_path):
    board_path = _write(tmp_path / "tinypico_module.net", TINYPICO_MODULE_NETLIST)

    result = extract_board_structure(str(board_path), board_id="tinypico_module", kind="netlist")

    runtime = result["controller_runtime"]
    controller = runtime["controllers"][0]
    assert controller["dev_module"] is True
    assert controller["controller_family"] == "esp32_family"
    assert any(path["type"] == "module_usb" for path in (runtime.get("programming_paths") or []))


def test_controller_runtime_emits_firmware_surface_for_motor_control_boards(tmp_path):
    board_path = _write(tmp_path / "esp32_motor_ctrl.net", ESP32_MOTOR_CTRL_NETLIST)

    result = extract_board_structure(str(board_path), board_id="esp32_motor_ctrl", kind="netlist")

    runtime = result["controller_runtime"]
    firmware_surface = runtime["firmware_surface"]
    assert firmware_surface["runtime_role"] == "motor_controller"
    assert firmware_surface["flash_strategy"]["primary_method"] == "usb_uart_bridge"
    assert "motor_drive_control" in (firmware_surface.get("runtime_functions") or [])
    assert "closed_loop_feedback" in (firmware_surface.get("runtime_functions") or [])
    assert (firmware_surface.get("attached_peripherals") or {}).get("gate_drivers") == ["U3"]
    assert (firmware_surface.get("attached_peripherals") or {}).get("current_sense_amps") == ["U4"]
    signal_inventory = firmware_surface.get("signal_inventory") or {}
    assert signal_inventory.get("pwm_nets")
    assert signal_inventory.get("analog_nets")
