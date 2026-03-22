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


BLDC_GATE_CTRL_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "STM32F446")
      (footprint "Package_QFP:LQFP-64"))
    (comp (ref "U2")
      (value "LM22675-5.0")
      (footprint "Package_SO:HSOP-8"))
    (comp (ref "U3")
      (value "AZ1117CR-3.3")
      (footprint "Package_TO_SOT_SMD:SOT89-3"))
    (comp (ref "U4")
      (value "LM5101A")
      (footprint "Package_DFN_QFN:WSON-8"))
    (comp (ref "U5")
      (value "LM5101A")
      (footprint "Package_DFN_QFN:WSON-8"))
    (comp (ref "U6")
      (value "LM5101A")
      (footprint "Package_DFN_QFN:WSON-8"))
    (comp (ref "U7")
      (value "INA240A2")
      (footprint "Package_SO:TSSOP-8"))
    (comp (ref "U8")
      (value "INA240A2")
      (footprint "Package_SO:TSSOP-8"))
    (comp (ref "U9")
      (value "INA240A2")
      (footprint "Package_SO:TSSOP-8"))
    (comp (ref "J1")
      (value "BAT_IN")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
  )
  (nets
    (net (code "1") (name "VPP")
      (node (ref "J1") (pin "1"))
      (node (ref "U2") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U2") (pin "2"))
      (node (ref "U3") (pin "2"))
      (node (ref "U4") (pin "2"))
      (node (ref "U5") (pin "2"))
      (node (ref "U6") (pin "2"))
      (node (ref "U7") (pin "2"))
      (node (ref "U8") (pin "2"))
      (node (ref "U9") (pin "2")))
    (net (code "3") (name "+5V")
      (node (ref "U2") (pin "3"))
      (node (ref "U3") (pin "1")))
    (net (code "4") (name "+3V3")
      (node (ref "U3") (pin "3"))
      (node (ref "U1") (pin "1"))
      (node (ref "U7") (pin "1"))
      (node (ref "U8") (pin "1"))
      (node (ref "U9") (pin "1")))
    (net (code "5") (name "+12V")
      (node (ref "U4") (pin "1"))
      (node (ref "U5") (pin "1"))
      (node (ref "U6") (pin "1")))
    (net (code "6") (name "/Power_FET/PH_A")
      (node (ref "U4") (pin "3")))
    (net (code "7") (name "/Power_FET/PH_B")
      (node (ref "U5") (pin "3")))
    (net (code "8") (name "/Power_FET/PH_C")
      (node (ref "U6") (pin "3")))
    (net (code "9") (name "/Microcontroller/PWM_H_A")
      (node (ref "U4") (pin "4")))
    (net (code "10") (name "/Microcontroller/PWM_L_A")
      (node (ref "U4") (pin "5")))
    (net (code "11") (name "/Microcontroller/PWM_H_B")
      (node (ref "U5") (pin "4")))
    (net (code "12") (name "/Microcontroller/PWM_L_B")
      (node (ref "U5") (pin "5")))
    (net (code "13") (name "/Microcontroller/PWM_H_C")
      (node (ref "U6") (pin "4")))
    (net (code "14") (name "/Microcontroller/PWM_L_C")
      (node (ref "U6") (pin "5")))
    (net (code "15") (name "/Power_FET/I_SENSE_A")
      (node (ref "U7") (pin "3")))
    (net (code "16") (name "/Power_FET/I_SENSE_B")
      (node (ref "U8") (pin "3")))
    (net (code "17") (name "/Power_FET/I_SENSE_C")
      (node (ref "U9") (pin "3")))
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
    assert motor_stage["topology"] == "h_bridge"
    assert "J2" in motor_stage["actuator_connectors"]
    assert "R1" in motor_stage["current_sense_refs"]
    assert "D1" in (analysis.get("protection_refs") or [])


def test_power_control_analysis_skips_false_regulator_and_detects_real_7805_stage(tmp_path):
    board_path = _write(
        tmp_path / "legacy_power.net",
        """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "7805")
      (footprint "Package_TO_SOT_THT:TO-220-3"))
    (comp (ref "IC3")
      (value "XBee_Explorer_Regulated")
      (footprint "XBEE_EXPLORER_REGULATED"))
    (comp (ref "P1")
      (value "LiPo_IN")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
    (comp (ref "P2")
      (value "Balance_Board")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x08"))
  )
  (nets
    (net (code "1") (name "/Bot_V+")
      (node (ref "P1") (pin "1"))
      (node (ref "U1") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "P1") (pin "2"))
      (node (ref "U1") (pin "2"))
      (node (ref "P2") (pin "1"))
      (node (ref "IC3") (pin "1")))
    (net (code "3") (name "+5V")
      (node (ref "U1") (pin "3"))
      (node (ref "P2") (pin "2"))
      (node (ref "IC3") (pin "2")))
    (net (code "4") (name "/XBee-Tx")
      (node (ref "P2") (pin "3"))
      (node (ref "IC3") (pin "3")))
    (net (code "5") (name "/XBee-Rx")
      (node (ref "P2") (pin "4"))
      (node (ref "IC3") (pin "4")))
  )
)
""".strip()
        + "\n",
    )

    result = extract_board_structure(str(board_path), board_id="legacy_power", kind="netlist")

    regulators = result["power"]["regulators"]
    assert [row["ref"] for row in regulators] == ["U1"]
    assert regulators[0]["vin_net"] == "/Bot_V+"
    assert regulators[0]["vout_net"] == "+5V"


def test_power_control_analysis_detects_gate_driver_and_current_feedback_stages(tmp_path):
    board_path = _write(tmp_path / "bldc_gate_ctrl.net", BLDC_GATE_CTRL_NETLIST)

    result = extract_board_structure(str(board_path), board_id="bldc_gate_ctrl", kind="netlist")

    assert result["primary_role"] == "motor_control"
    analysis = result["power_control_analysis"]
    assert any(stage["kind"] == "buck_like" for stage in (analysis.get("power_stages") or []))
    assert any(stage["kind"] == "ldo" for stage in (analysis.get("power_stages") or []))
    gate_stages = [stage for stage in (analysis.get("control_stages") or []) if stage["kind"] == "gate_driver"]
    assert len(gate_stages) == 3
    assert all(stage["topology"] == "bldc_gate_driver" for stage in gate_stages)
    assert all(len(stage["current_feedback_refs"]) == 1 for stage in gate_stages)
    assert all(len(stage["phase_tags"]) == 1 for stage in gate_stages)
    assert len({tuple(stage["phase_tags"]) for stage in gate_stages}) == 3
    assert len({stage["current_feedback_refs"][0] for stage in gate_stages}) == 3
    assert (analysis.get("summary") or {}).get("gate_driver_count") == 3
    assert (analysis.get("summary") or {}).get("current_sense_amp_count") == 3
