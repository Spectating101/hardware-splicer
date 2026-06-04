from __future__ import annotations

from pathlib import Path

from src.api.v1 import main as main_module
from src.engines.board_intelligence import analyze_board_intelligence
from src.engines.circuit_board_graph import analyze_circuit_design, analyze_circuit_session
from src.intelligence.board_session_store import BoardSessionStore


ROOT = Path(__file__).resolve().parents[4]
DEMO_NETLIST = ROOT / "examples" / "main_ctrl_esp32_servo.net"


SENSOR_NETLIST = """
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


ESP32_BAD_POWER_NETLIST = """
(export (version "E")
  (components
    (comp (ref "U1")
      (value "ESP32-WROOM-32")
      (footprint "RF_Module:ESP32-WROOM-32"))
    (comp (ref "J1")
      (value "VIN")
      (footprint "Connector_JST:JST_XH_B2B-XH-A"))
  )
  (nets
    (net (code "1") (name "+12V")
      (node (ref "J1") (pin "1"))
      (node (ref "U1") (pin "1")))
    (net (code "2") (name "GND")
      (node (ref "J1") (pin "2"))
      (node (ref "U1") (pin "15")))
  )
)
""".strip()


def test_circuit_graph_builds_board_contract_and_measurement_plan():
    result = analyze_circuit_design(
        {
            "board": {
                "board_id": "main_ctrl",
                "board_name": "Main Controller",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            }
        }
    )

    assert result["mode"] == "circuit_ai_circuit_graph"
    assert result["scope"] == "circuit_only"
    assert result["overall_readiness"] in {"blocked_until_measurements", "measurement_ready"}
    assert result["workflow_state"]["stage"] == "measurement_closure"

    board = result["boards"][0]
    assert board["graph"]["summary"]["component_count"] >= 8
    assert board["graph"]["summary"]["net_count"] >= 10
    assert any(net["net"] == "+3V3" for net in board["nets"])
    assert any(row["connector_ref"] == "J3" for row in board["connector_contracts"])
    assert any("SERVO_5V" in row["prompt"] for row in board["measurement_plan"])
    assert board["component_intelligence"]["known_pinout_count"] >= 3
    esp32 = next(row for row in board["component_intelligence"]["components"] if row["ref"] == "U1")
    assert esp32["resolution"] == "known_pinout"
    assert any(pin["pin_name"] == "GPIO0" for pin in esp32["pin_maps"])
    assert board["splice_contract"]["mode"] == "circuit_board_splice_contract"
    assert board["workflow_state"]["forbidden_actions"]
    assert board["splice_contract"]["do_not_connect_until"]
    assert any(adapter["name"] == "actuation/load interface" for adapter in board["splice_contract"]["adapter_requirements"])
    assert result["next_evidence_tasks"]


def test_circuit_graph_emits_functional_salvage_contract():
    result = analyze_circuit_design(
        {
            "board": {
                "board_id": "main_ctrl",
                "board_name": "Main Controller",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            }
        }
    )

    board = result["boards"][0]
    salvage = board["functional_salvage"]
    blocks = salvage["reusable_blocks"]

    assert result["functional_salvage"]["mode"] == "functional_salvage_portfolio"
    assert result["functional_salvage"]["reusable_block_count"] == len(blocks)
    assert salvage["schema_version"] == "functional_salvage.v1"
    assert salvage["verdict"] == "blocked_until_evidence"
    assert any(block["function_type"] == "controller_core" for block in blocks)
    assert any(block["function_type"] == "power_regulation" and block["extractability"]["class"] == "board_section_cut_candidate" for block in blocks)

    j2 = next(
        block
        for block in blocks
        if block["function_type"] == "external_interface" and "J2" in block.get("connector_refs", [])
    )
    assert j2["extractability"]["class"] == "connector_reuse"
    assert {"connector", "power"}.issubset(set(j2["capabilities"]))
    assert j2["status"] == "blocked_until_evidence"
    assert any("J2" in gate["prompt"] for gate in j2["evidence_gates"])
    assert not any("J3" in gate["prompt"] for gate in j2["evidence_gates"])
    assert "reuse_ready_requires" in salvage["safety_policy"]


def test_circuit_graph_builds_electrical_viability_budget():
    result = analyze_circuit_design(
        {
            "board": {
                "board_id": "main_ctrl",
                "board_name": "Main Controller",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            }
        }
    )
    board = result["boards"][0]
    viability = board["electrical_viability"]
    servo_budget = next(row for row in viability["rail_budgets"] if row["rail"] == "SERVO_5V")
    solver = viability["solver_model"]

    assert viability["mode"] == "circuit_electrical_viability"
    assert viability["verdict"] == "blocked_missing_source_limits"
    assert servo_budget["status"] == "missing_source_limit"
    assert servo_budget["nominal_v"] == 5.0
    assert servo_budget["estimated_load_a"] >= 0.65
    assert any(load["load_id"] == "J3:servo_sg90" for load in viability["load_estimates"])
    assert not any(load["load_id"] == "J4:servo_sg90" for load in viability["load_estimates"])
    assert any(row["type"] == "current_limit" and row["target"] == "SERVO_5V" for row in board["measurement_plan"])
    assert solver["available"] is True
    assert "VBUS" in solver["node_voltages"]
    assert "+3V3" in solver["node_voltages"]


def test_circuit_session_source_limit_closes_servo_budget(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    created = main_module.circuit_boards_analyze_design(
        {
            "description": "Servo source limit closure case",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        store=store,
    )
    session_id = created["session"]["session_id"]
    store.add_measurement(
        session_id,
        {"type": "current_limit", "target": "J4 SERVO_5V", "value": 1.0, "unit": "A", "notes": "bench supply limit for servo input"},
    )

    result = analyze_circuit_session(store.get_session(session_id))
    board = result["boards"][0]
    servo_budget = next(row for row in board["electrical_viability"]["rail_budgets"] if row["rail"] == "SERVO_5V")

    assert servo_budget["status"] == "ok"
    assert servo_budget["available_current_a"] == 1.0
    assert servo_budget["margin_a"] > 0.3
    assert board["electrical_viability"]["verdict"] != "blocked_missing_source_limits"
    assert all(risk["topic"] != "source_limit_missing" for risk in board["electrical_risks"])


def test_circuit_session_low_source_limit_holds_viability(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    created = main_module.circuit_boards_analyze_design(
        {
            "description": "Servo source limit too low",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        store=store,
    )
    session_id = created["session"]["session_id"]
    store.add_measurement(
        session_id,
        {"type": "current_limit", "target": "J4 SERVO_5V", "value": 0.4, "unit": "A", "notes": "bench supply limit for servo input"},
    )

    result = analyze_circuit_session(store.get_session(session_id))
    board = result["boards"][0]
    servo_budget = next(row for row in board["electrical_viability"]["rail_budgets"] if row["rail"] == "SERVO_5V")

    assert result["overall_readiness"] == "electrical_viability_hold"
    assert result["workflow_state"]["stage"] == "electrical_viability_hold"
    assert board["electrical_viability"]["verdict"] == "overcurrent_blocked"
    assert servo_budget["status"] == "overcurrent"
    assert servo_budget["margin_a"] < 0
    assert any(risk["topic"] == "rail_overcurrent" for risk in board["electrical_risks"])


def test_circuit_graph_builds_inter_board_splice_contract(tmp_path):
    sensor_path = tmp_path / "sensor.net"
    sensor_path.write_text(SENSOR_NETLIST, encoding="utf-8")

    result = analyze_circuit_design(
        {
            "machine_name": "controller_sensor_stack",
            "boards": [
                {
                    "board_id": "main_ctrl",
                    "path": str(DEMO_NETLIST),
                    "kind": "netlist",
                },
                {
                    "board_id": "sensor_io",
                    "path": str(sensor_path),
                    "kind": "netlist",
                },
            ],
        }
    )

    contract = result["system_contract"]

    assert result["board_count"] == 2
    assert any(row["interface"] == "i2c" for row in contract["candidate_interconnects"])
    assert any(row["rail"] == "+3V3" for row in contract["candidate_power_tree"])
    power_link = next(row for row in contract["system_power_viability"]["links"] if row["sink_board"] == "sensor_io")
    assert power_link["status"] == "ok"
    assert power_link["sink_estimated_load_a"] > 0
    assert power_link["margin_after_link_a"] > 0.6
    assert contract["wiring_contracts"]
    assert contract["pin_level_splice_plans"]
    plan = next(row for row in contract["pin_level_splice_plans"] if row["plan_id"] == "main_ctrl:J2->sensor_io:J1")
    pin_pairs = {(row["category"], row["function"]): row for row in plan["pin_pairs"]}
    assert plan["status"] == "blocked_until_evidence"
    assert plan["summary"]["wire_count"] == 4
    assert ("ground", "GND") in pin_pairs
    assert ("power", "rail:+3V3") in pin_pairs
    assert ("signal", "SCL") in pin_pairs
    assert ("signal", "SDA") in pin_pairs
    assert pin_pairs[("power", "rail:+3V3")]["from"]["pin"] == "3"
    assert pin_pairs[("power", "rail:+3V3")]["to"]["pin"] == "3"
    assert pin_pairs[("signal", "SCL")]["from"]["pin"] == "2"
    assert pin_pairs[("signal", "SCL")]["to"]["pin"] == "1"
    assert pin_pairs[("signal", "SDA")]["from"]["pin"] == "1"
    assert pin_pairs[("signal", "SDA")]["to"]["pin"] == "2"
    assert pin_pairs[("power", "rail:+3V3")]["budget_status"] == "ok"
    assert not any("Record source current limit or supply capability for +3V3" in blocker["prompt"] for blocker in plan["blockers"])
    assert not any("SERVO_5V" in blocker["prompt"] or "J3" in blocker["prompt"] or "J4" in blocker["prompt"] for blocker in plan["blockers"])
    assert any("main_ctrl:+3V3" in blocker["prompt"] for blocker in plan["blockers"])
    wires = {row["function"]: row for row in plan["wire_bom"]}
    assert wires["GND"]["color"] == "black"
    assert wires["rail:+3V3"]["color"] == "orange"
    assert wires["SCL"]["color"] == "yellow"
    assert wires["SDA"]["color"] == "green"
    assert [row["step"] for row in plan["execution_sequence"][:4]] == ["close_blockers", "connect_reference", "connect_power", "connect_signals"]
    assert any("Confirm" in item and "+3V3" in item for item in contract["do_not_connect_until"])


def test_circuit_graph_uses_known_pinout_to_flag_bad_power_pin(tmp_path):
    path = tmp_path / "bad_esp32.net"
    path.write_text(ESP32_BAD_POWER_NETLIST, encoding="utf-8")

    result = analyze_circuit_design(
        {
            "board": {
                "board_id": "bad_esp32",
                "path": str(path),
                "kind": "netlist",
            }
        }
    )
    board = result["boards"][0]

    assert board["component_intelligence"]["known_pinout_count"] == 1
    assert any(risk["topic"] == "pinout_voltage_expectation" for risk in board["electrical_risks"])
    esp32 = board["component_intelligence"]["components"][0]
    pin1 = next(pin for pin in esp32["pin_maps"] if pin["pin"] == "1")
    assert pin1["status"] == "needs_review"


def test_circuit_session_can_advance_from_board_intelligence(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    intelligence = analyze_board_intelligence(
        {
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            }
        }
    )
    session = store.create_session(
        {
            "description": "Main controller circuit work",
            "route": "board_intelligence",
            "analysis": intelligence,
            "source": "design_evidence",
        },
        user_id="operator-1",
    )

    result = analyze_circuit_session(store.get_session(session["session_id"]))

    assert result["mode"] == "circuit_ai_circuit_graph"
    assert result["session_context"]["session_id"] == session["session_id"]
    assert result["boards"][0]["connector_contracts"]
    assert result["boards"][0]["measurement_plan"]


def test_circuit_session_closes_specific_measurement_gates(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    created = main_module.circuit_boards_analyze_design(
        {
            "description": "Servo splice closure case",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        store=store,
    )
    session_id = created["session"]["session_id"]
    before = created["circuit"]["boards"][0]["measurement_closure"]

    store.add_measurement(
        session_id,
        {"type": "voltage", "target": "J3 SERVO_5V", "value": 5.02, "unit": "V", "notes": "servo rail powered by current-limited bench supply"},
    )
    store.add_measurement(
        session_id,
        {"type": "continuity", "target": "J3 ground", "value": "pass", "notes": "J3 ground pin has continuity to board ground"},
    )

    result = analyze_circuit_session(store.get_session(session_id))
    board = result["boards"][0]
    closure = board["measurement_closure"]
    servo_gate = next(row for row in board["measurement_plan"] if row["target"] == "J3:SERVO_5V")
    ground_gate = next(row for row in board["measurement_plan"] if row["type"] == "continuity" and row["target"] == "J3")

    assert closure["closed_gate_count"] > before["closed_gate_count"]
    assert board["workflow_state"]["stage"] == "measurement_closure"
    assert servo_gate["status"] == "closed"
    assert ground_gate["status"] == "closed"
    assert "Measure J3 power net SERVO_5V to ground at the connector." not in board["splice_contract"]["do_not_connect_until"]
    assert all(task["gate_id"] != servo_gate["measurement_id"] for task in result["next_evidence_tasks"])


def test_circuit_session_failed_measurement_holds_readiness(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    created = main_module.circuit_boards_analyze_design(
        {
            "description": "Bad rail case",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user={"user_id": "operator-1"},
        store=store,
    )
    session_id = created["session"]["session_id"]
    store.add_measurement(
        session_id,
        {"type": "voltage", "target": "+3V3", "value": 1.2, "unit": "V", "notes": "rail low under current limit"},
    )

    result = analyze_circuit_session(store.get_session(session_id))
    rail_gate = next(row for row in result["boards"][0]["measurement_plan"] if row["target"] == "+3V3")

    assert result["overall_readiness"] == "failed_measurement_hold"
    assert result["workflow_state"]["stage"] == "fault_hold"
    assert rail_gate["status"] == "failed"
    assert "outside expected" in rail_gate["closure_reason"]


def test_circuit_api_can_commit_session_and_append_advance(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")
    user = {"user_id": "user-1"}

    created = main_module.circuit_boards_analyze_design(
        {
            "description": "Circuit graph case",
            "board": {
                "board_id": "main_ctrl",
                "path": str(DEMO_NETLIST),
                "kind": "netlist",
            },
        },
        commit_session=True,
        current_user=user,
        store=store,
    )
    session_id = created["session"]["session_id"]

    response = main_module.circuit_sessions_advance(
        session_id,
        {},
        commit_analysis=True,
        current_user=user,
        store=store,
    )

    saved = store.get_session(session_id)

    assert created["status"] == "success"
    assert created["circuit"]["mode"] == "circuit_ai_circuit_graph"
    assert response["status"] == "success"
    assert saved["analyses"][-1]["source"] == "circuit_session_advance"
    assert any(task["source"].startswith("circuit_graph") for task in saved["evidence_tasks"])
