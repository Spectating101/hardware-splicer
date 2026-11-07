"""HS source-qualified panel/compute compatibility and protected-pack kill gate."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from hardware_splicer.cyberdeck_electrical_feasibility import evaluate

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"examples/cyberdeck/electrical_feasibility"
S=json.loads((SOURCE/"inputs.json").read_text())
P=json.loads((ROOT/"examples/cyberdeck/inset_hinge_test/hinge_qualification.json").read_text())
R=json.loads((SOURCE/"report.json").read_text())


def check(s=None,p=None):
    return evaluate(S if s is None else s,P if p is None else p)


def test_original_replay_and_vendor_source_receipts():
    r=check()
    assert {k:v for k,v in R.items() if k!="evidence_receipt"}==r
    assert R["evidence_receipt"]["input_sha256"]==hashlib.sha256(
        (SOURCE/"inputs.json").read_bytes()).hexdigest()
    assert R["evidence_receipt"]["prior_inset_gate_sha256"]==hashlib.sha256(
        (ROOT/"examples/cyberdeck/inset_hinge_test/hinge_qualification.json").read_bytes()).hexdigest()
    assert r["technical_decision"]=="NO_GO_COMPONENT_ORDER_WITHOUT_PANEL_DRIVER_AND_BENCH_PLAN"


def test_bandwidth_is_only_active_pixels_not_firmware_approval():
    r=check()
    d=r["display"]
    assert d["dsi0_hardware_lanes"]==2
    assert d["dsi1_hardware_lanes"]==4
    assert d["exact_panel_lanes"]==2
    assert d["active_pixel_only_gbps_per_lane"]==0.663552
    assert d["active_data_rate_below_raw_limit"] is True
    assert not d["actual_Phy_clock_or_blanking_timing_verified"]
    assert not d["panel_specific_initialization_and_display_mode_available"]
    assert not d["two_independent_Linux_DSI_outputs_tested"]
    assert not d["two_GT928_touch_devices_tested"]
    assert d["vendor_panel_software_gate"]=="BLOCKED"


def test_official_pi_touch_display_2_is_not_drop_in_Winstar():
    r=check()
    off=r["official_reference"]
    assert off["known_supported_software_reference"]
    assert off["outer_xy_mm"]==[143.5,91.5]
    assert off["depth_mm"]==16
    assert off["fits_80mm_body"] is False
    assert off["drop_in_winstar_driver_equivalent"] is False
    assert r["display"]["same_chip_as_official_panel_does_not_mean_same_init"]


def test_protected_battery_does_not_unlock_18mm():
    r=check()
    b=r["protected_pack_comparison"]
    assert b["previous_assumed_unprotected_cell_depth_mm"]==6
    assert b["candidate_part"]=="LP525178"
    assert b["manufacturer_claimed_protected_pack_depth_mm"]==5.2
    assert b["CM4_mated_plus_carrier_height_mm"]==5.878
    assert b["primary_lower_stack_dominant_component"]=="CM4"
    assert b["old_6mm_cell_nominal_lower_bound_mm"]==19.05
    assert b["new_protected_5p2mm_pack_nominal_lower_bound_mm"]==18.928
    assert b["nominal_thickness_saved_mm"]==0.122
    assert b["remaining_shortfall_to_18mm_mm"]==0.928
    assert not b["NTC_present"]
    assert not b["price_and_shipping_validated"]
    assert not b["pack_thermal_and_protection_system_qualified"]


def test_electrical_power_and_release_are_still_closed():
    r=check()
    assert r["backlight"]["two_panel_range_W"]==[1.568,1.904]
    assert not r["backlight"]["5V_direct_connection_acceptable"]
    assert not r["backlight"]["driver_schematic_or_SPICE_test_completed"]
    assert all(v is False for v in r["release"].values())
    assert r["next_cheapest_experiment"]["first_physical_purchase_authorized"] is False
    assert r["next_cheapest_experiment"]["two_panel_purchase_authorized"] is False


@pytest.mark.parametrize("key,value",[
    ("two_touchscreens",False),("no_physical_keyboard",False),
    ("max_closed_mm",[155,80,20]),("marketing_business_out_of_scope",False),
    ("budget_user_approved",True),
])
def test_user_goals_cannot_be_silently_rewritten(key,value):
    s=deepcopy(S);s["user_constraints"][key]=value
    with pytest.raises(ValueError):check(s)


def test_wrong_near_sku_four_lane_rejected():
    s=deepcopy(S)
    s["panel"]["exact_mpn"]="WF50DTYA3MNG10"
    s["panel"]["dsi_lanes"]=4
    with pytest.raises(ValueError,match="exact 2-lane"):
        check(s)


@pytest.mark.parametrize("field",[
    "vendor_init_table_confirmed","timing_and_DSI_mode_validated",
    "linux_exact_panel_driver_confirmed",
])
def test_can_not_claim_software_works_without_source_vendor_evidence(field):
    s=deepcopy(S);s["panel"][field]=True
    with pytest.raises(ValueError,match="actual Winstar driver"):
        check(s)


def test_kernel_driver_commit_cannot_be_swapped():
    s=deepcopy(S);s["kernel"]["driver_blob_sha"]="unreviewed"
    with pytest.raises(ValueError,match="driver/overlay identity"):
        check(s)


def test_unsafe_battery_pack_spec_cannot_pass_as_protected():
    s=deepcopy(S);s["protected_pack"]["PCM_included"]=False
    with pytest.raises(ValueError,match="protected pack"):
        check(s)


def test_battery_source_missing_taiwan_checkout_not_an_all_in_cost():
    s=deepcopy(S)
    s["protected_pack"]["shipping_and_local_price_unknown"]=False
    with pytest.raises(ValueError,match="not certified"):
        check(s)


def test_false_bench_claims_rejected():
    for key in S["gate_truth"]:
        s=deepcopy(S);s["gate_truth"][key]=True
        with pytest.raises(ValueError,match="bench verification"):
            check(s)


def test_previous_native_hinge_cannot_grant_retroactive_fabrication():
    p=deepcopy(P);p["manufacturing_authorized"]=True
    with pytest.raises(ValueError,match="not hardware authorized"):
        check(p=p)


def test_erase_1mm_research_clearance_not_an_allowed_optimization():
    s=deepcopy(S);s["stack"]["min_component_research_clearance_mm"]=0.4
    with pytest.raises(ValueError,match="silently loosen"):
        check(s)
