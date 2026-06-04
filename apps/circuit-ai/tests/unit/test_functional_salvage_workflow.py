from src.api.v1 import main as main_module
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.functional_salvage_workflow import FunctionalSalvageWorkflowRunner
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


def test_functional_salvage_golden_workflow_runs_multiple_scenarios(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")

    report = FunctionalSalvageWorkflowRunner(store=store).run(commit_sessions=True)

    assert report["mode"] == "functional_salvage_golden_workflow"
    assert report["overall_status"] == "pass"
    assert report["scenario_count"] == 4
    assert report["passed_count"] == 4
    by_id = {row["id"]: row for row in report["scenarios"]}

    verified = by_id["verified_sensor_connector"]
    assert verified["splice_readiness"] == "ready_for_first_splice"
    assert verified["recommended_first_splice"]["status"] == "reuse_ready"
    assert "main_ctrl:J2" in verified["recommended_first_splice"]["entry_points"]

    motor = by_id["motor_connector_blocked"]
    assert motor["splice_readiness"] == "blocked_until_evidence"
    assert motor["target_block"]["status"] == "blocked_until_evidence"
    assert any("SERVO_5V" in item for item in motor["target_block"]["missing_evidence"])

    regulator = by_id["regulator_section_candidate"]
    assert regulator["target_block"]["extractability"]["class"] == "board_section_cut_candidate"
    assert regulator["target_block"]["extractability"]["requires_layout_confirmation"] is True

    hazard = by_id["hazardous_lithium_hold"]
    assert hazard["verdict"] == "unsafe_hold"
    assert hazard["route"] == "safety"

    assert len(store.list_sessions(limit=20)) == 4


def test_functional_salvage_golden_workflow_api_can_run_ephemeral(tmp_path):
    store = BoardSessionStore(tmp_path / "sessions.json")

    response = main_module.salvage_functional_workflow_golden(
        {"commit_sessions": False},
        current_user={"user_id": "user-1"},
        planner=SalvageSplicePlanner(),
        store=store,
    )

    assert response["status"] == "success"
    assert response["workflow"]["overall_status"] == "pass"
    assert response["workflow"]["passed_count"] == response["workflow"]["scenario_count"]
    assert response["metadata"]["commit_sessions"] is False
    assert store.list_sessions(limit=20) == []
