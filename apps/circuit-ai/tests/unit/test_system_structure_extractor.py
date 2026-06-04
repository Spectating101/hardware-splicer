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


POWER_HUB_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "7805")
      (footprint "Package_TO_SOT_THT:TO-220-3"))
    (comp (ref "P1")
      (value "LiPo_IN")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
    (comp (ref "P2")
      (value "Balance_Board")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x08"))
  )
  (nets
    (net (code "1") (name "+12V")
      (node (ref "P1") (pin "1"))
      (node (ref "U1") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "P1") (pin "2"))
      (node (ref "U1") (pin "2"))
      (node (ref "P2") (pin "1")))
    (net (code "3") (name "+5V")
      (node (ref "U1") (pin "3"))
      (node (ref "P2") (pin "2")))
    (net (code "4") (name "/TXD1")
      (node (ref "P2") (pin "3")))
    (net (code "5") (name "/RXD1")
      (node (ref "P2") (pin "4")))
  )
)
""".strip()


MOTOR_NODE_NETLIST = """
(export (version "E")
  (components
    (comp (ref "MD1")
      (value "Motor_Driver")
      (footprint "POLULU_MOTOR_DRIVER"))
    (comp (ref "P1")
      (value "Power_And_UART")
      (footprint "Connector_PinHeader_2.54mm:PinHeader_1x08"))
    (comp (ref "M1")
      (value "Motor")
      (footprint "POLULU_MOTOR_CONN"))
  )
  (nets
    (net (code "1") (name "+5V")
      (node (ref "P1") (pin "2"))
      (node (ref "MD1") (pin "1"))
      (node (ref "M1") (pin "4")))
    (net (code "2") (name "GND")
      (node (ref "P1") (pin "1"))
      (node (ref "MD1") (pin "2"))
      (node (ref "M1") (pin "3")))
    (net (code "3") (name "/TXD1")
      (node (ref "P1") (pin "3")))
    (net (code "4") (name "/RXD1")
      (node (ref "P1") (pin "4")))
    (net (code "5") (name "OUTA")
      (node (ref "MD1") (pin "3"))
      (node (ref "M1") (pin "1")))
    (net (code "6") (name "OUTB")
      (node (ref "MD1") (pin "4"))
      (node (ref "M1") (pin "2")))
  )
)
""".strip()


LOCAL_REGULATED_NODE_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "7805")
      (footprint "Package_TO_SOT_THT:TO-220-3"))
    (comp (ref "P1")
      (value "Local_Power")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
  )
  (nets
    (net (code "1") (name "+12V")
      (node (ref "P1") (pin "1"))
      (node (ref "U1") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "P1") (pin "2"))
      (node (ref "U1") (pin "2")))
    (net (code "3") (name "/5V")
      (node (ref "U1") (pin "3")))
  )
)
""".strip()


BRIDGE_NODE_NETLIST = """
(export (version "E")
  (components
    (comp (ref "P1")
      (value "Upstream")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
    (comp (ref "P2")
      (value "Downstream")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
  )
  (nets
    (net (code "1") (name "+12V")
      (node (ref "P1") (pin "1"))
      (node (ref "P2") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "P1") (pin "2"))
      (node (ref "P2") (pin "2")))
  )
)
""".strip()


SINK_NODE_NETLIST = """
(export (version "E")
  (components
    (comp (ref "P1")
      (value "Power_Input")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
  )
  (nets
    (net (code "1") (name "+12V")
      (node (ref "P1") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "P1") (pin "2")))
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


def test_synthesize_machine_topology_prefers_power_hub_for_legacy_shared_rail(tmp_path):
    hub_path = _write_netlist(tmp_path / "power_hub.net", POWER_HUB_NETLIST)
    motor_path = _write_netlist(tmp_path / "motor_node.net", MOTOR_NODE_NETLIST)

    power_hub = extract_board_structure(str(hub_path), board_id="power_hub", kind="netlist")
    motor_node = extract_board_structure(str(motor_path), board_id="motor_node", kind="netlist")

    balance = next(row for row in power_hub["connectors"] if row["ref"] == "P2")
    interfaces = {row["interface"] for row in (balance.get("interfaces") or [])}
    assert "uart" in interfaces

    result = synthesize_machine_topology([power_hub, motor_node], machine_name="LegacyRig")

    assert any(row["source"] == "power_hub:+5V" and row["board_id"] == "motor_node" for row in (result.get("candidate_power_tree") or []))
    pack = result.get("motor_control_pack") or {}
    assert pack.get("status") == "integrated"
    assert pack.get("topology") == "single_motor_control"
    assert any(row.get("board_id") == "motor_node" for row in (pack.get("actuation_boards") or []))
    assert any(row.get("source") == "power_hub:+5V" for row in (pack.get("power_feeds") or []))
    assert pack.get("bring_up_focus")


def test_synthesize_machine_topology_skips_voltage_only_links_when_both_boards_regulate_locally(tmp_path):
    hub_path = _write_netlist(tmp_path / "power_hub.net", POWER_HUB_NETLIST)
    local_path = _write_netlist(tmp_path / "local_regulated.net", LOCAL_REGULATED_NODE_NETLIST)

    power_hub = extract_board_structure(str(hub_path), board_id="power_hub", kind="netlist")
    local_node = extract_board_structure(str(local_path), board_id="local_node", kind="netlist")

    result = synthesize_machine_topology([power_hub, local_node], machine_name="IsolatedPower")

    assert not any(row["board_id"] == "local_node" and row["voltage_v"] == 5.0 for row in (result.get("candidate_power_tree") or []))


def test_synthesize_machine_topology_prunes_duplicate_downstream_power_candidates(tmp_path):
    source_path = _write_netlist(tmp_path / "source_hub.net", POWER_HUB_NETLIST)
    bridge_path = _write_netlist(tmp_path / "bridge.net", BRIDGE_NODE_NETLIST)
    sink_path = _write_netlist(tmp_path / "sink.net", SINK_NODE_NETLIST)

    source = extract_board_structure(str(source_path), board_id="source_hub", kind="netlist")
    bridge = extract_board_structure(str(bridge_path), board_id="bridge", kind="netlist")
    sink = extract_board_structure(str(sink_path), board_id="sink", kind="netlist")

    result = synthesize_machine_topology([source, bridge, sink], machine_name="PowerTree")

    sink_edges = [row for row in (result.get("candidate_power_tree") or []) if row["board_id"] == "sink" and row["rail"] == "+12V"]
    assert len(sink_edges) == 1
    assert sink_edges[0]["source"] == "source_hub:+12V"


def test_synthesize_machine_topology_skips_ambiguous_power_questions_for_unlinked_sink_boards(tmp_path):
    sink_a_path = _write_netlist(tmp_path / "sink_a.net", SINK_NODE_NETLIST)
    sink_b_path = _write_netlist(tmp_path / "sink_b.net", SINK_NODE_NETLIST)

    sink_a = extract_board_structure(str(sink_a_path), board_id="sink_a", kind="netlist")
    sink_b = extract_board_structure(str(sink_b_path), board_id="sink_b", kind="netlist")

    result = synthesize_machine_topology([sink_a, sink_b], machine_name="LooseRails")

    assert not result.get("candidate_power_tree")
    assert not any("source direction is ambiguous" in str(question) for question in (result.get("questions") or []))
    assert (result.get("motor_control_pack") or {}).get("status") == "not_applicable"
