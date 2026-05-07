from src.api.v1 import main as main_module
from src.intelligence.salvage_portfolio_planner import SalvagePortfolioPlanner
from src.intelligence.salvage_splice_planner import SalvageSplicePlanner


def _pile_payload():
    return {
        "title": "weekend salvage pile",
        "goal": "build useful shop gadgets from a pile of electronics",
        "items": [
            {
                "title": "flatbed scanner",
                "goal": "reuse rail and light for inspection",
                "available_parts": ["stepper motor", "LED light bar", "linear rail", "optical sensor", "12V adapter", "limit switch"],
            },
            {
                "title": "USB fan",
                "goal": "reuse as fume extractor",
                "available_parts": ["5V USB cable", "small DC motor", "fan blade", "switch", "plastic case"],
            },
            {
                "title": "WiFi router",
                "goal": "reuse LEDs and network parts",
                "available_parts": ["12V adapter", "WiFi antenna", "LED indicators", "Ethernet connectors", "plastic enclosure"],
            },
            {
                "title": "microwave oven",
                "goal": "recover useful low voltage pieces only",
                "available_parts": ["microwave oven", "high voltage capacitor", "magnetron", "turntable motor", "mains transformer"],
            },
        ],
    }


def test_portfolio_planner_combines_pile_into_ranked_builds_and_safety_holds():
    planner = SalvagePortfolioPlanner()

    plan = planner.plan(_pile_payload())

    assert plan["mode"] == "salvage_reuse_portfolio_plan"
    assert plan["summary"]["item_count"] == 4
    assert plan["summary"]["safety_hold_count"] == 1
    assert plan["summary"]["build_count"] >= 3
    assert plan["summary"]["top_build_id"] in {"inspection_motion_fixture", "usb_fume_extractor", "network_status_indicator"}
    assert any(row["build_id"] == "inspection_motion_fixture" for row in plan["build_portfolio"])
    inspection = next(row for row in plan["build_portfolio"] if row["build_id"] == "inspection_motion_fixture")
    assert inspection["source_items"] == ["flatbed scanner"]
    assert {block["name"] for block in inspection["allocated_blocks"]} >= {"stepper motor", "LED light bar", "linear rail", "12V adapter"}
    assert any(row["title"] == "microwave oven" for row in plan["safety_holds"])
    assert plan["aggregate_inventory"]["reusable_block_count"] == 16
    assert plan["work_order"]["first_build"]
    assert any("voltage" in step.lower() for step in plan["work_order"]["steps"])
    demos = {row["build_id"]: row["first_proof_demo"] for row in plan["build_portfolio"]}
    if {"inspection_motion_fixture", "network_status_indicator"}.issubset(demos):
        assert demos["inspection_motion_fixture"] != demos["network_status_indicator"]


def test_portfolio_planner_reports_capability_gaps_for_sparse_pile():
    planner = SalvagePortfolioPlanner()

    plan = planner.plan(
        {
            "title": "sparse pile",
            "items": [
                {"title": "buttons and case", "available_parts": ["push buttons", "plastic case"]},
                {"title": "loose speaker", "available_parts": ["speaker driver"]},
            ],
        }
    )

    assert plan["summary"]["item_count"] == 2
    assert plan["build_portfolio"]
    assert plan["capability_gaps"]
    assert any(gap["source_options"] for gap in plan["capability_gaps"])


def test_portfolio_plan_api_returns_user_scoped_plan():
    response = main_module.salvage_portfolio_plan(
        _pile_payload(),
        current_user={"user_id": "operator-1"},
        planner=SalvagePortfolioPlanner(SalvageSplicePlanner()),
    )

    assert response["metadata"]["user_id"] == "operator-1"
    assert response["portfolio_plan"]["summary"]["verdict"] == "build_portfolio_ready"
