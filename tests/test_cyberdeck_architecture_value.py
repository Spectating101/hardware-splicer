"""HS value-engineering comparison must not convert seller asks into build authority."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from hardware_splicer.cyberdeck_architecture_value import evaluate

ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads((ROOT/"examples/cyberdeck/architecture_value/candidates.json").read_text())


def _run(data=None):
    return evaluate(DATA if data is None else data,repo_root=ROOT)


def test_replay_and_price_arithmetic_are_exact():
    result=_run()
    saved=json.loads((ROOT/"examples/cyberdeck/architecture_value/hs_decision.json").read_text())
    assert result==saved
    price={r["candidate_id"]:r["asking_price_subtotal_ntd"] for r in result["results"]}
    assert price=={
        "cm4_dual_dsi":6324, "cm4_narrow_50_dsi":8366,
        "cm4_43_dsi":5724,"cm4_narrow_custom":3728,
        "esp32_dual_43":3300,
        "radxa_cm5_dual_50":None,"intact_phone_dual_display":7200,
        "used_fold4":10000,"stripped_phone_mainboard":None
    }
    assert result["preferred_linux_research_candidate_id"] is None
    assert result["no_priced_Linux_architecture_meets_both_footprint_and_budget"]
    assert result["highest_information_gain_thin_linux_study"]=="cm4_narrow_custom"
    assert result["preferred_lowest_integrated_cost_experiment_id"]=="esp32_dual_43"


def test_no_one_has_an_all_in_price_or_approval():
    result=_run()
    assert not result["commercialization_required"]
    assert not result["any_candidate_manufacturing_authorized"]
    assert not result["any_candidate_purchasing_authorized"]
    assert not result["supplier_checkout_quote_confirmed"]
    for row in result["results"]:
        assert row["all_in_prototype_price_ntd"] is None
        assert row["unpriced_subsystems"]
        assert row["critical_unknowns"]
        assert row["machine_release"]["allowed"] is False
        assert "safety_not_closed" in row["machine_release"]["blocking_issue_codes"]
        assert "hinge_cable_bend_and_serviceability" in row["unresolved_requirements"]


def test_cm5_native_rejection_is_actually_loaded_not_copied():
    report=_run()
    cm5=next(x for x in report["results"] if x["candidate_id"]=="radxa_cm5_dual_50")
    assert cm5["pocketability"]=="failed_18mm_declared_HS_stack"
    assert cm5["native_hs_mechanical_fit_evidence"]["18mm_nominal_gap_mm"]==-0.735
    assert cm5["native_hs_mechanical_fit_evidence"]["hard_constraint_met"] is False


@pytest.mark.parametrize("key,value",[
    ("two_touchscreens_mandatory",False),
    ("physical_keyboard_forbidden",False),
    ("commercialization_required",True),
    ("security_and_safe_power_mandatory",False),
    ("max_closed_size_mm",[155,80,20]),
])
def test_user_constraints_cannot_be_relaxed(key,value):
    candidate=deepcopy(DATA)
    candidate["product_requirement"][key]=value
    with pytest.raises(ValueError):
        _run(candidate)


def test_fake_vendor_quote_cannot_promote_bid():
    d=deepcopy(DATA)
    d["candidates"][0]["manufacturer_quote_total_ntd"]=1
    with pytest.raises(ValueError,match="no candidate"):
        _run(d)


def test_duplicate_candidate_id_rejected():
    d=deepcopy(DATA)
    d["candidates"][1]["id"]=d["candidates"][0]["id"]
    with pytest.raises(ValueError,match="duplicate"):
        _run(d)


def test_missing_asking_price_provenance_rejected():
    d=deepcopy(DATA)
    d["candidates"][0]["sourced_items"][0]["url"]=""
    with pytest.raises(ValueError,match="provenance"):
        _run(d)


def test_cheaper_derived_price_does_not_invent_full_build_cost():
    d=deepcopy(DATA)
    d["candidates"][0]["sourced_items"][0]["ask_ntd"]=1800
    result=_run(d)
    cm4=next(x for x in result["results"] if x["candidate_id"]=="cm4_dual_dsi")
    assert cm4["asking_price_subtotal_ntd"]==4396
    assert cm4["module_footprint_gate"]["fits_nominal_xy"] is False
    assert cm4["all_in_prototype_price_ntd"] is None
    assert cm4["purchasing_authorized"] is False
    assert cm4["manufacturing_authorized"] is False


def test_budget_tightening_changes_preference_but_not_safety():
    d=deepcopy(DATA)
    d["product_requirement"]["target_budget_ntd"]=6000
    result=_run(d)
    assert result["preferred_linux_research_candidate_id"] is None
    cm4=next(x for x in result["results"] if x["candidate_id"]=="cm4_dual_dsi")
    assert cm4["budget_status"]=="asking_price_subtotal_already_above_budget"
    assert cm4["machine_release"]["allowed"] is False


def test_fold_price_is_benchmark_not_two_rigid_screen_solution():
    result=_run()
    fold=next(x for x in result["results"] if x["candidate_id"]=="used_fold4")
    assert fold["display_topology"]=="not_this_two_rigid_touchscreen_product"
    assert fold["budget_status"]=="asking_price_subtotal_already_above_budget"


def test_native_XY_gate_catches_cheap_5inch_B_screen():
    r=_run()
    x=next(x for x in r["results"] if x["candidate_id"]=="cm4_dual_dsi")
    assert x["module_footprint_gate"]["fits_nominal_xy"] is False
    assert x["module_footprint_gate"]["module_oriented_width_mm"]==87.45
    assert x["module_footprint_gate"]["native_FDM_usable_width_mm"]==76.8
    assert x["pocketability"]=="manufacturer_panel_xy_exceeds_155x80_case"


def test_narrow_5inch_has_verified_XY_but_over_budget_before_carrier():
    r=_run()
    x=next(x for x in r["results"] if x["candidate_id"]=="cm4_narrow_50_dsi")
    assert x["module_footprint_gate"]["fits_nominal_xy"] is True
    assert x["asking_price_subtotal_ntd"]==8366
    assert x["budget_status"]=="asking_price_subtotal_already_above_budget"
    assert x["all_in_prototype_price_ntd"] is None


def test_cheap_43inch_two_pcb_modules_already_too_thick():
    r=_run()
    x=next(x for x in r["results"] if x["candidate_id"]=="cm4_43_dsi")
    assert x["asking_price_subtotal_ntd"]==5724
    assert x["two_module_minimum_thickness_mm"]==28.1
    assert x["pocketability"]=="two_unmodified_display_modules_exceed_18mm_alone"


def test_cannot_fabricate_false_fit_by_smaller_pocket_requirement():
    d=deepcopy(DATA)
    d["candidates"][0]["module_footprint_mm"]=[127.70,79.0]
    r=_run(d)
    x=next(x for x in r["results"] if x["candidate_id"]=="cm4_dual_dsi")
    assert x["module_footprint_gate"]["fits_nominal_xy"] is False
    assert not x["manufacturing_authorized"]


def test_no_free_panels_from_missing_local_quote():
    r=_run()
    x=next(x for x in r["results"] if x["candidate_id"]=="cm4_narrow_custom")
    assert x["asking_price_subtotal_ntd"]==3728
    assert x["number_of_listed_price_items"]==1
    assert "TWO DISPLAY MODULES" in x["unpriced_subsystems"]
    assert x["all_in_prototype_price_ntd"] is None
    assert r["preferred_linux_research_candidate_id"] is None
