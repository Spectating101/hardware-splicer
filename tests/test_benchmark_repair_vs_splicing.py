import pytest
from scripts.benchmark_repair_vs_splicing import CASES, evaluate_one, summarize

def result(build_id="usb_uart_debug_adapter"):
    return {"evaluation":{"passed":True},"metrics":{"drc_pass":True,"build_id":build_id}}

def plan(verified=False):
    blocks=[{"source":"operator_inventory","name":"unverified source"}]
    if verified:
        blocks.append({"source":"circuit_functional_salvage","name":"fixture block"})
    return {"splice_plan":{"verdict":"reuse_ready","reusable_blocks":blocks}}

def test_repair_drc_pass_not_restored_scanner():
    row=evaluate_one("repair_unverified",result(),plan())
    assert row["reported_pipeline_pass"] and row["carrier_drc_pass"]
    assert row["pipeline_pass_is_not_mission_pass"]
    assert row["mission_success"] is False
    assert row["verified_components_from_listings"]==0
    assert "NOT scanner" in row["reason"]

def test_multi_donor_drc_pass_not_verified_product():
    row=evaluate_one("splice_unverified",result("inspection_motion_fixture"),plan())
    assert len(row["marketplace_listing_ids"])==4
    assert row["verified_components_from_listings"]==0
    assert row["mission_success"] is False
    assert row["physical_authority_from_run"] is False

def test_fixture_cannot_pass_physical_mission():
    row=evaluate_one("repair_fixture",result("robot_drive_base"),plan(verified=True))
    assert row["circuit_backed_donor_blocks"]==1
    assert row["mission_success"] is None
    assert not row["physical_testing_done"]

def test_suite_separates_compiler_and_mission_verdict():
    rows=[evaluate_one(k,result(),plan()) for k in CASES]
    outcome=summarize(rows)
    assert (outcome["fixture_compiles_passed"],outcome["market_compiles_passed"])==(2,2)
    assert outcome["market_pipeline_reported_pass"]==2
    assert outcome["market_missions_proved"]==0
    assert outcome["tested_physical_devices"]==0

def test_all_four_required():
    with pytest.raises(ValueError):
        summarize([])

def test_unknown_case_refused():
    with pytest.raises(ValueError):
        evaluate_one("fake_measured_repair",result(),plan())
