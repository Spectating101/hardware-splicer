from __future__ import annotations

from pathlib import Path

from src.engines.system_structure_extractor import extract_board_structure


HIGH_DROP_CTRL_NETLIST = """
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
    (net (code "1") (name "+12V")
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


MOTOR_CTRL_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "DRV8833")
      (footprint "Package_SO:HTSSOP-16"))
    (comp (ref "U2")
      (value "MP1584")
      (footprint "Package_SO:SOIC-8"))
    (comp (ref "J1")
      (value "BAT_IN")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
    (comp (ref "J2")
      (value "MOTOR_A")
      (footprint "Connector_JST:JST_XH_B4B-XH-A"))
    (comp (ref "L1")
      (value "10uH")
      (footprint "Inductor_SMD:L_0805"))
    (comp (ref "R1")
      (value "0R05")
      (footprint "Resistor_SMD:R_1206"))
    (comp (ref "D1")
      (value "SMBJ24A_TVS")
      (footprint "Diode_SMD:D_SMB"))
  )
  (nets
    (net (code "1") (name "VBAT")
      (node (ref "J1") (pin "1"))
      (node (ref "U1") (pin "8"))
      (node (ref "U2") (pin "1"))
      (node (ref "L1") (pin "1"))
      (node (ref "D1") (pin "1"))
      (node (ref "R1") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "9"))
      (node (ref "U2") (pin "2"))
      (node (ref "D1") (pin "2"))
      (node (ref "R1") (pin "2")))
    (net (code "3") (name "+5V")
      (node (ref "U2") (pin "3"))
      (node (ref "L1") (pin "2")))
    (net (code "4") (name "OUTA")
      (node (ref "U1") (pin "3"))
      (node (ref "J2") (pin "1")))
    (net (code "5") (name "OUTB")
      (node (ref "U1") (pin "4"))
      (node (ref "J2") (pin "2")))
  )
)
""".strip()


def _write(path: Path, contents: str) -> Path:
    path.write_text(contents + "\n", encoding="utf-8")
    return path


def test_power_control_analysis_flags_linear_drop_and_missing_input_protection(tmp_path):
    board_path = _write(tmp_path / "high_drop_ctrl.net", HIGH_DROP_CTRL_NETLIST)

    result = extract_board_structure(str(board_path), board_id="high_drop_ctrl", kind="netlist")

    analysis = result["power_control_analysis"]
    assert any(stage["kind"] == "ldo" for stage in (analysis.get("power_stages") or []))
    assert any(finding["topic"] == "linear_regulator_drop" for finding in (analysis.get("risk_findings") or []))
    assert any(
        finding["topic"] == "input_protection" and finding["status"] == "missing"
        for finding in (analysis.get("protection_findings") or [])
    )


def test_power_control_analysis_detects_motor_driver_current_sense_and_protection(tmp_path):
    board_path = _write(tmp_path / "motor_ctrl.net", MOTOR_CTRL_NETLIST)

    result = extract_board_structure(str(board_path), board_id="motor_ctrl", kind="netlist")

    analysis = result["power_control_analysis"]
    assert any(stage["kind"] == "buck_like" for stage in (analysis.get("power_stages") or []))
    motor_stage = (analysis.get("control_stages") or [])[0]
    assert motor_stage["ref"] == "U1"
    assert "J2" in motor_stage["actuator_connectors"]
    assert "R1" in motor_stage["current_sense_refs"]
    assert "D1" in (analysis.get("protection_refs") or [])
