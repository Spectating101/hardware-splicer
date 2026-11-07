"""HS CM4 thin dual-touch integration — physical honesty and adversarial cases."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"apps/mecha-splicer/src"))

from hardware_splicer.cyberdeck_cm4_stack import run
from mecha_splicer.spec import ClamshellTerminalSpec

SOURCE=ROOT/"examples/cyberdeck/cm4_thin_stack"
INPUT=json.loads((SOURCE/"requirements.json").read_text())


def _run(p=None,out=None):
    return run(INPUT if p is None else p,out=out)


def test_replay_from_traced_real_module_dimensions():
    result=_run()
    committed=json.loads((SOURCE/"evidence/cm4_stack_result.json").read_text())
    assert result==committed
    assert result["required_closed_xyz_mm"]==[155.0,80.0,18.0]
    assert result["nominal_only_fit"] is True
    assert result["nominal_candidate_lid_height_mm"]==5.1
    assert result["nominal_pass_count"]==3
    assert result["decision"]=="NOMINAL_INTERNAL_STACK_BUT_HINGE_EXCEEDS_POCKET_LIMIT"
    assert result["native_clamshell_hinge_included_xyz_mm"]==[155.0,84.6,18.0]
    assert result["whole_device_pocket_envelope_met"] is False
    assert result["selected_candidate_requires_lid_module_slack_review"] is True


def test_exact_minute_geometry_clearances_and_failure_transition():
    r=_run()
    sweep={x["lid_height_mm"]:x for x in r["sweep"]}
    assert [(lid,sweep[lid]["cm4_display_gap_mm"],sweep[lid]["naked_battery_display_gap_mm"])
            for lid in (5.05,5.1,5.15,5.2,5.3,5.8)]==[
        (5.05,1.222,1.1),(5.1,1.172,1.05),(5.15,1.122,1.0),
        (5.2,1.072,0.95),(5.3,0.972,0.85),(5.8,0.472,0.35)]
    assert all(sweep[lid]["minimum_nominal_research_fit"] for lid in (5.05,5.1,5.15))
    assert all(not sweep[lid]["minimum_nominal_research_fit"] for lid in (5.2,5.3,5.8))
    assert sweep[5.1]["panel_in_lid_rigidity_slack_mm"]==0.05
    assert sweep[5.1]["native_fit_status"]=="candidate"
    assert sweep[5.2]["native_fit_status"]=="blocked"
    assert sweep[5.1]["native_checks"]["clearance-cm4-to-lower-screen"]["status"]=="pass"
    assert sweep[5.1]["native_checks"]["clearance-battery-to-lower-screen"]["status"]=="pass"


def test_nominal_pass_is_fragile_to_realistic_component_differences():
    r=_run()
    sensitivity={x["id"]:x for x in r["sensitivity_at_chosen"]}
    assert set(sensitivity)=={
        "cell_plus_0p30mm","cm4_plus_0p25mm",
        "lid_plus_0p20mm","screen_plus_0p15mm"
    }
    assert all(not x["minimum_nominal_research_fit"] for x in sensitivity.values())
    assert r["sensitivity_any_failed"]
    assert sensitivity["cell_plus_0p30mm"]["naked_battery_display_gap_mm"]==0.75
    assert sensitivity["cm4_plus_0p25mm"]["cm4_display_gap_mm"]==0.922


def test_native_mecha_has_correct_product_and_usable_floor():
    r=_run()
    by_name={x["item"]:x for x in r["native_bom"]}
    assert by_name["Raspberry Pi CM4102000 wireless Lite 2GB"]["qty"]==1
    assert by_name["Winstar WF50DTYA3MNG10-000"]["qty"]==2
    assert not any("Waveshare" in name or "RS485" in name or "CardKB" in name for name in by_name)
    spec=json.loads((SOURCE/"evidence/native_project_spec.json").read_text())
    c=ClamshellTerminalSpec.model_validate(spec["clamshell_terminal"])
    assert c.compute_architecture=="cm4_dual_dsi"
    assert c.input_surface_mode=="dual_touch"
    assert c.floor_mm==c.wall_mm==1.6
    assert c.base_h_mm==12.1 and c.lid_h_mm==5.1 and c.closed_gap_mm==0.8
    assert r["native_cad_outputs"]==[
        "base_shell.scad","lid_shell.scad",
        "clamshell_open_preview.scad","dual_touch_visual_preview.scad"
    ]


def test_repeatable_native_files_and_source_sha(tmp_path):
    r=_run(out=tmp_path)
    root=SOURCE/"evidence"
    assert r["source_sha256"].startswith("sha256:")
    for name in ("cm4_stack_result.json","native_project_spec.json","machine_project.json"):
        assert (tmp_path/name).read_bytes()==(root/name).read_bytes()
    for name in ("base_shell.scad","lid_shell.scad","clamshell_open_preview.scad",
                 "dual_touch_visual_preview.scad","bom.csv","mecha_splicer.bundle.json"):
        assert (tmp_path/"native_mecha"/name).read_bytes()==(
            root/"native_mecha"/name).read_bytes()


def test_no_fake_cost_or_release_authority():
    r=_run()
    assert r["quoted_nonstrict_module_price_ntd"]==2238.43
    assert r["panel_price_separate_currency"]=={
        "usd_each":29.88,"qty":2,"no_NTD_landed_quote":True
    }
    assert "two_panels_delivered_NTD_price" in r["unpriced"]
    assert "protected_battery_and_boost" in r["unpriced"]
    assert r["manufacturing_authorized"] is False
    assert r["safe_to_power"] is False
    assert r["two_DSI_panels_tested"] is False
    a=r["release_assessment"]
    assert a["requested_state"]=="build_ready"
    assert a["blockers"]
    assert not a.get("allowed",False)


@pytest.mark.parametrize("section,key,value",[
    ("user_constraints","screens",1),
    ("user_constraints","physical_keyboard",True),
    ("user_constraints","closed_max_xyz_mm",[155,80,20]),
    ("user_constraints","budget_status","owner_approved"),
    ("enclosure","shell_floor_mm",0.85),
    ("enclosure","shell_wall_mm",1.4),
    ("enclosure","closed_screen_gap_mm",0.3),
    ("enclosure","minimum_research_clearance_mm",0.3),
])
def test_product_and_clearance_constraints_fail_closed(section,key,value):
    p=deepcopy(INPUT);p[section][key]=value
    with pytest.raises(ValueError):
        _run(p)


def test_similar_but_four_lane_Winstar_is_not_a_drop_in():
    p=deepcopy(INPUT)
    p["candidate_parts"]["panels"]["mpn"]="WF50DTYA3MNG10"
    p["candidate_parts"]["panels"]["dsi_lanes"]=4
    with pytest.raises(ValueError,match="2-lane"):
        _run(p)


def test_unverified_complete_power_claim_cannot_be_promoted():
    p=deepcopy(INPUT)
    p["candidate_parts"]["battery"]["protected_pack_qualified"]=True
    with pytest.raises(ValueError,match="naked battery"):
        _run(p)


def test_upsizing_battery_invalidates_even_a_nominal_thin_candidate():
    p=deepcopy(INPUT)
    p["candidate_parts"]["battery"]["cell_thickness_mm"]=6.5
    r=_run(p)
    assert not r["nominal_only_fit"]
    assert r["decision"]=="NO_NOMINAL_INTERNAL_STACK_FIT"
    assert r["manufacturing_authorized"] is False


def test_lid_sweep_can_never_approve_fabrication():
    p=deepcopy(INPUT)
    p["enclosure"]["upper_lid_height_sweep_mm"]=[5.06,5.07]
    r=_run(p)
    assert r["nominal_only_fit"]
    assert r["manufacturing_authorized"] is False
    assert r["release_assessment"]["blockers"]


def test_hinge_is_counted_in_true_whole_pocket_footprint():
    r=_run()
    assert r["external_hinge_projection_mm"]==4.6
    assert r["whole_device_pocket_envelope_met"] is False
    assert r["hinge_geometry_still_requires_redesign"] is True
    # Even shrinking the existing hinge to its specified lower bounds does
    # NOT fix an 80mm-deep body; a genuinely inset architecture is required.
    p=deepcopy(INPUT)
    p["enclosure"]["hinge_outer_d_mm"]=5.8
    p["enclosure"]["hinge_y_offset_mm"]=0.5
    compact=_run(p)
    assert compact["external_hinge_projection_mm"]==3.4
    assert not compact["whole_device_pocket_envelope_met"]
