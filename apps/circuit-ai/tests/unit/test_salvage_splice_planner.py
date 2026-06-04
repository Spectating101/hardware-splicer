from src.api.v1 import main as main_module
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


def test_splice_planner_turns_usb_fan_into_reuse_build_plan():
    planner = SalvageSplicePlanner()

    plan = planner.plan(
        {
            "title": "USB fan salvage",
            "goal": "reuse as fume extractor",
            "available_parts": [
                "5V USB cable",
                "small DC motor and fan blade",
                "on/off switch",
                "wire harness connector",
                "plastic enclosure",
            ],
        }
    )

    assert plan["verdict"] in {"ready_after_measurements", "reuse_ready"}
    assert plan["target"]["recommended_build_id"] in {"usb_fume_extractor", "low_voltage_motor_test_jig"}
    assert {"power", "motor_or_load", "connector"}.issubset(set(plan["capability_summary"]))
    assert any("motor/load resistance" in item for item in plan["splice_plan"]["required_measurements"])
    assert any("current-limited" in item for item in plan["splice_plan"]["wiring_steps"])
    assert plan["value_tracking"]["goal"] == "salvage_to_build"


def test_splice_planner_holds_swollen_battery_pack_as_unsafe():
    planner = SalvageSplicePlanner()

    plan = planner.plan(
        {
            "title": "swollen lithium power bank",
            "goal": "reuse cells for a gadget",
            "available_parts": ["swollen battery pack", "USB board", "case"],
        }
    )

    assert plan["verdict"] == "unsafe_hold"
    assert any("swollen" in item.lower() for item in plan["stop_conditions"])
    assert plan["build_candidates"][0]["score"] < 0.6


def test_splice_planner_uses_analysis_connector_and_interface_evidence():
    planner = SalvageSplicePlanner()

    plan = planner.plan(
        {
            "title": "relay controller board",
            "goal": "turn it into low voltage load controller",
            "analysis": {
                "salvage_opportunities": {
                    "asset_summary": {
                        "capabilities": {"controller": 1, "actuator_driver": 1, "power": 1},
                        "parts": {"esp32": 1, "relay": 1},
                        "connector_count": 2,
                        "evidence": ["part marking: esp32", "interface: power"],
                    }
                },
                "machine_connection_map": {
                    "connector_count": 2,
                    "interfaces": [{"type": "power", "confidence": 0.72}, {"type": "uart_serial", "confidence": 0.68}],
                    "splice_plan": {
                        "safest_entry_points": ["conn_0_connector"],
                        "required_measurements": ["logic high voltage"],
                    },
                },
            },
        }
    )

    assert plan["target"]["recommended_build_id"] == "smart_relay_box"
    assert "conn_0_connector" in plan["splice_plan"]["safest_entry_points"]
    assert "logic high voltage" in plan["splice_plan"]["required_measurements"]
    assert any(adapter["name"] == "logic-to-load interface" for adapter in plan["splice_plan"]["adapter_circuits"])


def test_splice_planner_routes_scanner_parts_to_inspection_fixture():
    planner = SalvageSplicePlanner()

    plan = planner.plan(
        {
            "title": "flatbed scanner",
            "goal": "reuse light bar, stepper, and rails for an inspection fixture",
            "available_parts": ["stepper motor", "LED light bar", "linear rail", "optical sensor", "12V adapter", "limit switch"],
        }
    )

    assert plan["target"]["recommended_build_id"] == "inspection_motion_fixture"
    assert any(adapter["name"] == "motion-and-light fixture harness" for adapter in plan["splice_plan"]["adapter_circuits"])
    assert "first_demo" in plan["integration_contract"]
    assert any("light bar" in step for step in plan["splice_plan"]["wiring_steps"])


def test_splice_planner_does_not_invent_title_blocks_when_inventory_is_explicit():
    planner = SalvageSplicePlanner()

    plan = planner.plan(
        {
            "title": "flatbed scanner",
            "goal": "reuse light bar, stepper, and rails for an inspection fixture",
            "available_parts": ["stepper motor", "LED light bar", "linear rail", "optical sensor", "12V adapter", "limit switch"],
        }
    )

    assert len(plan["reusable_blocks"]) == 6
    assert {block["source"] for block in plan["reusable_blocks"]} == {"operator_inventory"}
    assert not any(block["name"] == "small motor/load" for block in plan["reusable_blocks"])


def test_splice_plan_api_returns_reuse_plan():
    response = main_module.salvage_splice_plan(
        {
            "title": "USB fan",
            "goal": "reuse as cooling fan",
            "available_parts": ["5V USB cable", "small DC motor", "switch", "connector"],
        },
        current_user={"user_id": "user-1"},
        planner=SalvageSplicePlanner(),
    )

    assert response["metadata"]["user_id"] == "user-1"
    assert response["splice_plan"]["mode"] == "salvage_splice_reuse_plan"
    assert response["splice_plan"]["build_candidates"]


def test_splice_plan_can_create_board_session_with_reuse_tasks(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")

    response = main_module.salvage_splice_plan(
        {
            "title": "LED strip controller",
            "goal": "reuse MOSFET board as low voltage light controller",
            "available_parts": ["12V adapter", "MOSFET driver board", "IR remote", "LED strip scraps", "wire connectors", "plastic case"],
        },
        commit_session=True,
        current_user={"user_id": "user-1"},
        planner=SalvageSplicePlanner(),
        store=store,
    )

    session = response["session"]
    assert response["metadata"]["committed_session"] is True
    assert session["route"] == "salvage"
    assert session["case_file"]["kind"] == "salvage_splice_reuse"
    assert session["salvage_splice_plan"]["target"]["recommended_build_id"] == "smart_relay_box"
    assert session["evidence_tasks"]
    assert any(task["source"].startswith("salvage_splice") for task in session["evidence_tasks"])
    assert session["metrics"]["measurement_count_required"] > 0
    assert store.get_session(session["session_id"]) is not None


def test_splice_case_api_creates_tracked_reuse_session(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")

    response = main_module.salvage_splice_case(
        {
            "title": "USB fan",
            "goal": "reuse as fume extractor",
            "available_parts": ["5V USB cable", "small DC motor", "fan blade", "switch", "connector", "plastic case"],
        },
        current_user={"user_id": "user-2"},
        planner=SalvageSplicePlanner(),
        store=store,
    )

    session = response["session"]
    assert response["metadata"]["committed"] is True
    assert response["metadata"]["user_id"] == "user-2"
    assert response["splice_plan"]["target"]["recommended_build_id"] in {"usb_fume_extractor", "low_voltage_motor_test_jig"}
    assert session["route"] == "salvage"
    assert session["case_file"]["kind"] == "salvage_splice_reuse"
    assert session["salvage_splice_plan"]["mode"] == "salvage_splice_reuse_plan"
    assert any(task["type"] == "measurement" for task in session["evidence_tasks"])


def test_splice_case_api_turns_hazardous_items_into_safety_queue(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")

    response = main_module.salvage_splice_case(
        {
            "title": "microwave oven",
            "goal": "reuse turntable motor",
            "available_parts": ["microwave oven", "high voltage capacitor", "magnetron", "turntable motor", "mains transformer"],
        },
        current_user={"user_id": "user-2"},
        planner=SalvageSplicePlanner(),
        store=store,
    )

    session = response["session"]
    assert response["splice_plan"]["verdict"] == "unsafe_hold"
    assert session["route"] == "safety"
    assert session["evidence_tasks"][0]["source"] == "salvage_splice_safety_gate"
    assert session["evidence_tasks"][0]["type"] == "review"
    assert not any(task["type"] == "measurement" for task in session["evidence_tasks"])
