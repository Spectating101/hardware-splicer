from src.intelligence.diy_project_session import DIYProjectSessionStore


def test_diy_project_session_accumulates_goal_budget_and_resources(tmp_path):
    store = DIYProjectSessionStore(tmp_path / "sessions.json")

    first = store.update_from_turn(
        {
            "user_message": "I need something that waters my plants while I am away. I have random old electronics and about $10.",
            "strategy_mode": "hybrid",
        }
    )
    session_id = first["diy_project_session"]["session_id"]

    assert session_id.startswith("diy_")
    assert first["diy_project_engineering"]["project_intent"]["profile_id"] == "automatic_plant_watering"
    assert first["diy_project_session"]["intake_state"]["constraints"]["budget_usd"] == 10

    second = store.update_from_turn(
        {
            "session_id": session_id,
            "user_message": "I found a little 5V pump, a USB charger, some jumper wires, and no ESP32 yet.",
            "strategy_mode": "hybrid",
        }
    )
    session = second["diy_project_session"]
    intake = session["intake_state"]
    resource_names = {row["name"] for row in intake["available_resources"]}
    absent_names = {row["name"] for row in intake["known_absent_resources"]}
    selected_names = {row["name"] for row in second["diy_project_engineering"]["resource_plan"]["selected_resources"]}

    assert session["conversation"]["turn_count"] == 2
    assert "5V mini pump" in resource_names
    assert "USB power source" in resource_names
    assert "hookup/jumper wire" in resource_names
    assert "ESP32 dev board" in absent_names
    assert "5V mini pump" in selected_names
    assert "USB power source" in selected_names
    assert "hookup/jumper wire" in resource_names
    assert second["diy_project_engineering"]["requirements"]["constraints"]["budget_usd"] == 10
    assert second["design_test_kit"]["release_gate"]["decision"]
    assert second["diy_project_session"]["latest_test_kit"]["simulation_available"] is False
    assert "waters my plants" in intake["project_brief"]
    assert "5V pump" in intake["project_brief"]


def test_diy_project_session_persists_between_store_instances(tmp_path):
    path = tmp_path / "sessions.json"
    first_store = DIYProjectSessionStore(path)
    result = first_store.update_from_turn({"user_message": "Make a USB powered desk light from LEDs and a switch."})
    session_id = result["diy_project_session"]["session_id"]

    second_store = DIYProjectSessionStore(path)
    resumed = second_store.update_from_turn(
        {
            "session_id": session_id,
            "user_message": "The LED strip says 5V and I have a USB charger.",
        }
    )
    intake = resumed["diy_project_session"]["intake_state"]

    assert resumed["diy_project_session"]["session_id"] == session_id
    assert resumed["diy_project_session"]["conversation"]["turn_count"] == 2
    assert "5V low-voltage LED/light load" in {row["name"] for row in intake["available_resources"]}
    assert any(measurement["raw"].lower() == "5v" for measurement in intake["measurements"])
    assert resumed["diy_project_engineering"]["project_intent"]["profile_id"] == "task_light_or_indicator"


def test_diy_project_session_records_pinout_labels(tmp_path):
    store = DIYProjectSessionStore(tmp_path / "sessions.json")

    result = store.update_from_turn(
        {
            "user_message": "I have a moisture sensor labeled VCC GND SIG and an ESP32.",
            "diy_project": "Build automatic plant watering.",
        }
    )
    labels = set(result["diy_project_session"]["intake_state"]["observed_labels"])

    assert {"VCC", "GND", "SIG"}.issubset(labels)
    assert result["diy_project_engineering"]["project_intent"]["profile_id"] == "automatic_plant_watering"
