"""HS local-first 2x portrait touch design — source, CAD and UX acceptance."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.cyberdeck_workstation_tradeoff import evaluate,run

ROOT=Path(__file__).resolve().parents[1]
ROOT_DATA=ROOT/"examples/cyberdeck/workstation_tradeoff"
S=json.loads((ROOT_DATA/"parts_sources.json").read_text())
C=json.loads((ROOT_DATA/"evidence/waveshare_d_step.json").read_text())
B=json.loads((ROOT_DATA/"evidence/portrait_vs_DS_browser.json").read_text())
R=json.loads((ROOT_DATA/"evidence/hs_workstation_decision.json").read_text())


def _eval(s=None,c=None,b=None):
    return evaluate(S if s is None else s,C if c is None else c,
                    B if b is None else b)


def test_actual_sourced_replay_is_deterministic(tmp_path):
    new=run(ROOT_DATA/"parts_sources.json",ROOT_DATA/"evidence/waveshare_d_step.json",
            ROOT_DATA/"evidence/portrait_vs_DS_browser.json",tmp_path/"result.json")
    assert new==R
    assert (tmp_path/"result.json").read_bytes()==(
        ROOT_DATA/"evidence/hs_workstation_decision.json").read_bytes()
    assert R["provenance"]["sourced_options_sha256"]==hashlib.sha256(
        (ROOT_DATA/"parts_sources.json").read_bytes()).hexdigest()


def test_not_a_gaming_console_or_remote_only_ssh_product():
    r=_eval()
    assert "dual portrait 720x1280 touchscreens" in r["product_direction"]
    assert S["requirements"]["dual_screen_count"]==2
    assert S["requirements"]["local_development_required"]
    assert not S["requirements"]["physical_keyboard"]
    assert S["requirements"]["commercial_launch_required"] is False
    assert S["requirements"]["assistant_cost_goal_user_approved"] is False
    assert len(S["reference_only"])==2


def test_monetary_subtotals_include_both_screen_prices_but_no_fake_total():
    r=_eval()
    options={x["candidate_id"]:x for x in r["sourced_compute_and_screen_subtotals"]}
    assert r["price_screen_pair_ask_NTD"]==4638
    assert options["pi_cm4_lite_2gb"]["compute_and_two_panels_subtotal_NTD"]==6876.43
    assert options["pi_cm5_wifi4_lite"]["compute_and_two_panels_subtotal_NTD"]==8439
    assert options["pi_cm5_wifi8_lite"]["compute_and_two_panels_subtotal_NTD"]==10793
    assert options["pi_cm5_wifi4_emmc32"]["compute_and_two_panels_subtotal_NTD"]==10938
    assert options["pi_cm5_wifi4_lite"]["emmc_gb"]==0
    assert options["pi_cm5_wifi8_lite"]["RAM_research_preference_met"]
    assert not options["pi_cm5_wifi4_lite"]["RAM_research_preference_met"]
    assert options["pi_cm5_wifi4_emmc32"]["availability_at_research"]=="listed_sold_out"
    assert options["radxa_cm5_8_emmc64"]["compute_ask_currency"]=="USD"
    assert options["radxa_cm5_8_emmc64"]["compute_and_two_panels_subtotal_NTD"] is None
    assert options["radxa_cm5_8_emmc64"]["availability_at_research"]=="listed_sold_out"
    for op in options.values():
        assert op["known_full_delivered_BOM_NTD"] is None
        assert op["simultaneous_dual_DSI_bench_test_passed"] is False
        assert not op["manufacturing_authorized"]


def test_vendor_step_geometry_disproves_ready_made_18mm_stack():
    r=_eval()
    g=r["vendor_CAD_geometry"]
    assert C["number_solid_components"]==365
    assert len(C["step_sha256"])==64
    assert C["analysis_engine"].startswith("OpenCascade")
    assert g["full_single_display_assembled_xyz_mm"]==[70.708,126.908,13.608]
    assert g["full_module_pair_only_depth_mm"]==27.216
    assert g["pair_without_deep_mount_hardware_mm"]==21.6
    assert g["front_solid_pair_only_depth_mm"]==11.6
    assert g["front_solids_plus_two_1p6mm_shells_and_0p8mm_gap_mm"]==15.6
    assert g["remaining_in_assistant_18mm_stretch_goal_without_any_compute_or_battery_mm"]==2.4
    assert g["assembled_two_displays_alone_exceed_18mm"]
    assert g["removing_only_deep_mount_hardware_not_sufficient"]
    assert not g["front_solid_electronics_compatible_after_separation_proven"]


def test_real_browser_input_improvement_with_caveats():
    r=_eval()
    x=r["browser_portrait"]
    assert x["real_xterm_cells_24px"]==[47,35]
    assert x["compared_rgds_cells_24px"]==[42,12]
    assert x["wide_key_nominal_mm"]==7.28
    assert x["wide_vs_previous_key_width_gain"]>=2
    assert x["real_touch_to_sandboxed_ssh_tested"]
    assert x["real_symbol_page_to_sandboxed_ssh_tested"]
    assert not x["human_ergonomics_tested"]
    assert not x["actual_touch_controller_or_DSI_tested"]
    assert x["CSS_pixel_to_physical_mm_is_projection_only"]


def test_webapp_wide_key_profile_preserves_full_e2e_controls():
    js=(ROOT/"examples/cyberdeck/workflow_lab/web/app.js").read_text()
    html=(ROOT/"examples/cyberdeck/workflow_lab/web/index.html").read_text()
    assert "WIDE_ALPHA_ROWS" in js and "WIDE_SYMBOL_ROWS" in js
    assert "symbolLayer=key==='SYM'" in js
    assert "wideKeys=!wideKeys" in js
    for k in ("TMUX","CTRL-C","CTRL-D","SHIFT","CTRL","TAB","ESC","BACKSPACE","LEFT","RIGHT"):
        assert k in js
    assert 'id="keyboard-mode"' in html
    assert "const term = new Terminal(" in js


@pytest.mark.parametrize("path,val",[
    (("requirements","dual_screen_count"),1),
    (("requirements","physical_keyboard"),True),
    (("requirements","screen_orientation"),"landscape"),
    (("requirements","local_development_required"),False),
    (("requirements","commercial_launch_required"),True),
    (("requirements","assistant_cost_goal_user_approved"),True),
    (("displays","both_simultaneous_validated"),True),
    (("displays","after_electronics_relocation_drivers_validated"),True),
    (("truth","real_two_panels_on_compute_tested"),True),
    (("truth","hardware_purchased"),True),
])
def test_any_unearned_hardware_or_wrong_user_direction_is_rejected(path,val):
    s=deepcopy(S)
    s[path[0]][path[1]]=val
    with pytest.raises(ValueError):_eval(s=s)


def test_old_four_lane_or_landscape_screen_pricing_cannot_substitute():
    s=deepcopy(S)
    s["displays"]["sku"]="Waveshare 5inch DSI LCD (B) 800x480"
    s["displays"]["twd_ask_each"]=1298
    with pytest.raises(ValueError,match="portrait panel"):
        _eval(s=s)


def test_usd_ask_must_not_be_converted_to_TWD_without_fx():
    s=deepcopy(S)
    o=next(x for x in s["computes"] if x["id"]=="radxa_cm5_4_emmc32")
    o["price_ntd"]=2800
    with pytest.raises(ValueError,match="exactly one"):
        _eval(s=s)


def test_missing_vendor_step_receipt_cannot_fabricate_an_18mm_pass():
    c=deepcopy(C)
    c["outer_bbox_xyz_mm"]=[70.7,126.9,3.45]
    c["fabrication_qualified"]=True
    with pytest.raises(ValueError):_eval(c=c)


def test_fake_bench_hardware_qualification_rejected():
    b=deepcopy(B)
    b["physical_touchscreen_or_CM5_tested"]=True
    with pytest.raises(ValueError,match="not a physical"):
        _eval(b=b)


def test_incorrect_terminal_keys_or_unverified_symbol_layer_fail():
    b=deepcopy(B)
    for row in b["results"]:
        if row["device"]=="hs_dual_5in_portrait" and row["fontsize_css_px"]==24:
            row["smallest_letter_nominal_mm"]=3.5
    with pytest.raises(ValueError,match="keyboard"):
        _eval(b=b)
    b=deepcopy(B)
    for row in b["results"]:
        row.pop("symbol_layer_to_real_SSH_verified",None)
    with pytest.raises(ValueError,match="symbol"):
        _eval(b=b)


def test_physical_release_invariably_false():
    r=_eval()
    assert set(r["physical_release"].values())=={False}
    assert r["not_a_shippable_or_verified_BOM"]
    assert "not old CM4-only" in r["revised_evaluation"]
