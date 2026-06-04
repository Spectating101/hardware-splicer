from src.api.v1 import main as main_module
from src.intelligence.board_session_store import BoardSessionStore
from src.intelligence.repair_case_evaluator import RepairCase, RepairCaseEvaluator
from src.intelligence.repair_encyclopedia import RepairEncyclopedia
from src.intelligence.repair_market_coverage import RepairMarketCoverage
from src.intelligence.repair_video_playbook import RepairVideoPlaybookBuilder


def test_repair_case_evaluator_scores_real_cases_and_session_tasks(tmp_path):
    evaluator = RepairCaseEvaluator(session_store=BoardSessionStore(tmp_path / "sessions.json"))
    report = evaluator.evaluate_cases(
        [
            RepairCase(
                case_id="controller",
                title="Xbox controller stick drift",
                device_hint="Xbox controller",
                symptoms=["stick drift", "thumbstick unreliable"],
                source_url="https://www.ifixit.com/example",
                observed_actions=["clean joystick", "replace analog stick if needed"],
            ),
            RepairCase(
                case_id="coffee",
                title="Coffee maker not hot enough",
                device_hint="coffee maker",
                symptoms=["coffee maker not heating", "not hot enough"],
                source_url="https://www.ifixit.com/example",
                observed_actions=["check thermal fuse", "measure heating element"],
            ),
        ],
    )

    assert report["summary"]["case_count"] == 2
    assert report["summary"]["average_workflow_score"] > 0.45
    controller = report["cases"][0]
    assert controller["repair_guide"]["top_fault"] == "analog_stick_or_button_contact_fault"
    assert controller["board_session"]["task_count"] > 0
    coffee = report["cases"][1]
    assert coffee["repair_guide"]["safety_risk"] == "high"
    assert coffee["board_session"]["route"] == "safety"


def test_repair_case_eval_api_returns_report(tmp_path):
    evaluator = RepairCaseEvaluator(
        encyclopedia=RepairEncyclopedia(),
        coverage=RepairMarketCoverage(),
        playbook_builder=RepairVideoPlaybookBuilder(RepairEncyclopedia()),
        session_store=BoardSessionStore(tmp_path / "sessions.json"),
    )

    response = main_module.repair_case_eval(
        {
            "cases": [
                {
                    "case_id": "toothbrush",
                    "title": "Electric toothbrush not charging",
                    "device_hint": "electric toothbrush charging dock",
                    "symptoms": ["not charging", "battery does not hold charge"],
                    "source_url": "https://www.ifixit.com/example",
                }
            ]
        },
        current_user={"user_id": "user-1"},
        evaluator=evaluator,
    )

    assert response["metadata"]["user_id"] == "user-1"
    assert response["case_eval"]["cases"][0]["repair_guide"]["family"] == "battery_charging_gadget"
