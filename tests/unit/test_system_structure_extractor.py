from __future__ import annotations

from pathlib import Path

from src.engines.system_structure_extractor import extract_board_structure, synthesize_machine_topology


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
    (comp (ref "R1")
      (value "4K7")
      (footprint "Resistor_SMD:R_0603"))
    (comp (ref "R2")
      (value "4K7")
      (footprint "Resistor_SMD:R_0603"))
    (comp (ref "C1")
      (value "10uF")
      (footprint "Capacitor_SMD:C_0805"))
  )
  (nets
    (net (code "1") (name "VIN")
      (node (ref "J1") (pin "1"))
      (node (ref "U2") (pin "1"))
      (node (ref "C1") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "10"))
      (node (ref "U2") (pin "2"))
      (node (ref "C1") (pin "2"))
      (node (ref "J2") (pin "4")))
    (net (code "3") (name "+3V3")
      (node (ref "U2") (pin "3"))
      (node (ref "U1") (pin "1"))
      (node (ref "J2") (pin "3"))
      (node (ref "R1") (pin "1"))
      (node (ref "R2") (pin "1")))
    (net (code "4") (name "SCL")
      (node (ref "U1") (pin "23"))
      (node (ref "J2") (pin "1"))
      (node (ref "R1") (pin "2")))
    (net (code "5") (name "SDA")
      (node (ref "U1") (pin "24"))
      (node (ref "J2") (pin "2"))
      (node (ref "R2") (pin "2")))
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
    (comp (ref "C1")
      (value "100nF")
      (footprint "Capacitor_SMD:C_0603"))
  )
  (nets
    (net (code "1") (name "GND")
      (node (ref "J1") (pin "4"))
      (node (ref "U1") (pin "8"))
      (node (ref "C1") (pin "2")))
    (net (code "2") (name "+3V3")
      (node (ref "J1") (pin "3"))
      (node (ref "U1") (pin "1"))
      (node (ref "C1") (pin "1")))
    (net (code "3") (name "SCL")
      (node (ref "J1") (pin "1"))
      (node (ref "U1") (pin "6")))
    (net (code "4") (name "SDA")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "5")))
  )
)
""".strip()


def _write_netlist(path: Path, contents: str) -> Path:
    path.write_text(contents + "\n", encoding="utf-8")
    return path


def test_extract_board_structure_detects_connectors_roles_and_regulator(tmp_path):
    main_path = _write_netlist(tmp_path / "main_ctrl.net", MAIN_CTRL_NETLIST)

    result = extract_board_structure(str(main_path), board_id="main_ctrl", board_name="Main Controller", kind="netlist")

    assert result["board_id"] == "main_ctrl"
    assert result["primary_role"] == "controller"
    assert {row["ref"] for row in result["connectors"]} == {"J1", "J2"}
    assert any(row["net"] == "VIN" for row in result["power"]["rails"])
    assert any(row["net"] == "+3V3" for row in result["power"]["rails"])

    regulators = result["power"]["regulators"]
    assert regulators
    assert regulators[0]["ref"] == "U2"
    assert regulators[0]["vin_net"] == "VIN"
    assert regulators[0]["vout_net"] == "+3V3"

    j2 = next(row for row in result["connectors"] if row["ref"] == "J2")
    interfaces = {row["interface"] for row in j2["interfaces"]}
    assert "i2c" in interfaces
    assert "power" in interfaces


def test_synthesize_machine_topology_matches_i2c_and_power(tmp_path):
    main_path = _write_netlist(tmp_path / "main_ctrl.net", MAIN_CTRL_NETLIST)
    sensor_path = _write_netlist(tmp_path / "sensor_io.net", SENSOR_IO_NETLIST)

    main_board = extract_board_structure(str(main_path), board_id="main_ctrl", kind="netlist")
    sensor_board = extract_board_structure(str(sensor_path), board_id="sensor_io", kind="netlist")

    result = synthesize_machine_topology([main_board, sensor_board], machine_name="BenchBot")

    interconnects = result["candidate_interconnects"]
    assert interconnects
    assert any(row["interface"] == "i2c" for row in interconnects)
    i2c = next(row for row in interconnects if row["interface"] == "i2c")
    assert i2c["from_board"] == "main_ctrl"
    assert i2c["to_board"] == "sensor_io"
    assert {"SCL", "SDA"}.issubset(set(i2c["signals"]))

    power_tree = result["candidate_power_tree"]
    assert power_tree
    power_row = power_tree[0]
    assert power_row["source"] == "main_ctrl:+3V3"
    assert power_row["board_id"] == "sensor_io"
    assert power_row["rail"] == "+3V3"

    compiled = result["compiled_preview"]
    assert (compiled.get("machine") or {}).get("board_count") == 2
    assert (compiled.get("system") or {}).get("interconnects")
