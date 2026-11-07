"""CM4 side hinge model verification, vendor panel constraints and regressions."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"apps/mecha-splicer/src"))
sys.path.insert(0,str(ROOT/"examples/cyberdeck"))
from mecha_splicer.bundle import generate_bundle
from mecha_splicer.spec import ProjectSpec
from hardware_splicer.cyberdeck_inset_hinge_gate import evaluate,run
from hardware_splicer.cyberdeck_panel_collision import _run_cgal
from produce_terminal import audit_stl

HERE=ROOT/"examples/cyberdeck/inset_hinge_test"
QUAL=json.loads((HERE/"qualification_input.json").read_text())
SPEC=json.loads((HERE/"spec.json").read_text())
CAD=json.loads((HERE/"evidence/design_evidence.json").read_text())
PRIOR=json.loads((ROOT/"examples/cyberdeck/cm4_thin_stack/evidence/cm4_stack_result.json").read_text())
PANELS=json.loads((HERE/"panel_CGAL_report.json").read_text())


def _evaluate(q=None,spec=None,cad=None,prior=None,panels=None):
    return evaluate(QUAL if q is None else q,SPEC if spec is None else spec,
                    CAD if cad is None else cad,PRIOR if prior is None else prior,
                    PANELS if panels is None else panels)


def test_real_cgal_hinge_six_angles_and_mesh():
    r=_evaluate()
    assert r["tested_geometry"]["closed_body_xyz_mm"]==[155,80,18]
    assert r["tested_geometry"]["barrel_max_external_projection_mm"]==0
    assert r["tested_geometry"]["CGAL_six_shell_angles_pass"]
    assert r["tested_geometry"]["nominal_full_thickness_screen_boxes_cross_half_tested"]
    assert not r["tested_geometry"]["full_screen_and_FPC_sweep_tested"]
    for name in ("base_shell","lid_shell"):
        m=audit_stl(HERE/"evidence"/(name+".stl"))
        assert m["nonmanifold_edges"]==0
        assert m["bbox_mm"][:2]==[155,80]
        assert m["sha256"]==CAD["mesh"][name]["sha256"]
    assert [x["angle_deg"] for x in CAD["cgal_interference_sweep"]]==[0,-30,-60,-90,-135,-165]
    assert all(x["interference_mesh"]=="EMPTY" for x in CAD["cgal_interference_sweep"])


def test_winstar_vendor_worst_case_collides_with_nominal_lid():
    r=_evaluate()
    assert PANELS["vendor_max_panel_collides_with_lid_floor"]
    assert all(x["intersection"]=="EMPTY" for x in PANELS["angles"])
    assert r["retention"]["minimum_upper_lid_for_panel_max_mm"]==5.7
    assert r["retention"]["selected_lid_missing_mm"]==0.6
    assert r["retention"]["vendor_max_panel_collides_inside_nominal_lid_CGAL"]
    assert r["retention"]["unsupported_screen_rear_edge_mm"]==2.65
    assert r["retention"]["screen_retention_gate"]=="BLOCKED"


def test_battery_nominal_floor_is_not_physical_power_authorization():
    r=_evaluate()
    assert r["worst_case_packaging"]["minimum_closed_thickness_mm"]==19.05
    assert r["worst_case_packaging"]["minimum_closed_if_no_bondline_mm"]==18.9
    assert r["worst_case_packaging"]["shortfall_to_18mm_mm"]==1.05
    assert r["mechanical_and_service"]["rear_shell_open_across_width_mm"]==6.0
    assert r["mechanical_and_service"]["base_rear_upper_clearance_cut_mm"]==6.7
    assert r["mechanical_and_service"]["rear_dust_and_water_ingress_risk"]
    assert not r["mechanical_and_service"]["hinge_pin_supported_with_real_physical_load_test"]
    assert not r["manufacturing_authorized"] and not r["safe_to_power"]


def test_source_backlight_rail_not_an_assumed_5v_regulator():
    r=_evaluate()
    e=r["electrical"]
    assert e["LCD_backlight_voltage_domain_v"]==[19.6,23.8]
    assert e["two_backlights_w"]==[1.568,1.904]
    assert e["requires_current_controlled_boost"]
    assert not e["backlight_driver_qualified"]
    assert not e["two_linux_DSI_panels_verified"]
    assert not e["two_GT928_touch_inputs_verified"]


def test_machine_project_fails_closed_despite_passing_cad_shells():
    r=_evaluate()
    a=r["machine_release"]
    assert a["blockers"]
    assert any(x["code"]=="verification_not_passed" for x in a["blockers"])
    assert any(x["code"]=="safety_not_closed" for x in a["blockers"])
    assert r["decision"]=="CGAL_KINEMATIC_PASS_COMPONENT_RETENTION_AND_TOLERANCE_FAIL"
    assert r["component_procuring_authorized"] is False
    assert r["manufacturing_authorized"] is False
    assert r["safe_to_power"] is False


def test_native_inset_generator_outputs_tracked_solid_geometry_and_correct_bom(tmp_path):
    native=generate_bundle(SPEC,out_dir=tmp_path)
    assert not native["blockers"]
    assert set(native["outputs"])=={
        "base_shell.scad","lid_shell.scad","clamshell_open_preview.scad",
        "dual_touch_visual_preview.scad"
    }
    for f in native["outputs"]:
        assert (tmp_path/f).read_bytes()==(HERE/"evidence"/f).read_bytes()
    bom={row["item"]:row for row in native["bom"]}
    assert bom["Raspberry Pi CM4102000 wireless Lite 2GB"]["qty"]==1
    assert bom["Winstar WF50DTYA3MNG10-000"]["qty"]==2
    assert not any("ESP32" in row for row in bom)
    assert SPEC["clamshell_terminal"]["hinge_style"]=="inset_side_pins"


def test_inset_side_pin_must_fit_side_margin_not_hit_LCD():
    p=deepcopy(SPEC)
    p["clamshell_terminal"]["hinge_side_knuckle_axial_length_mm"]=5.0
    p["clamshell_terminal"]["display_board_w_mm"]=132.0
    p["clamshell_terminal"]["lower_touch_board_w_mm"]=132.0
    with pytest.raises(ValueError,match="overlap"):
        ProjectSpec.model_validate(p)


def test_inset_hinge_rejects_external_barrel_projection():
    p=deepcopy(SPEC)
    p["clamshell_terminal"]["hinge_inset_from_rear_mm"]=2.5
    with pytest.raises(ValueError,match="outside"):
        ProjectSpec.model_validate(p)


def test_rear_cut_cannot_erase_entire_lower_rear_attachment():
    p=deepcopy(SPEC)
    p["clamshell_terminal"]["hinge_base_rear_relief_height_mm"]=11.0
    with pytest.raises(ValueError,match="destroys"):
        ProjectSpec.model_validate(p)


@pytest.mark.parametrize("field,value",[
    ("panel_mpn","WF50DTYA3MNG10"),
    ("panel_thickness_tolerance_mm",0),
    ("panel_thickness_tolerance_mm",0.1),
    ("lcd_backlight_voltage_min_v",5.0),
    ("lcd_backlight_nominal_current_a",0.01),
    ("battery_protection_qualified",True),
    ("dual_dsi_linux_verified",True),
    ("hinge_flex_dynamic_bend_verified",True),
    ("user_approved_hinge_rear_opening",True),
    ("commercialization_required",True),
])
def test_safety_and_source_claims_cannot_be_faked(field,value):
    q=deepcopy(QUAL);q[field]=value
    with pytest.raises(ValueError):
        _evaluate(q=q)


def test_missing_actual_screen_collision_negative_control_rejected():
    panels=deepcopy(PANELS);panels["vendor_max_panel_collides_with_lid_floor"]=False
    with pytest.raises(ValueError,match="positive CGAL"):
        _evaluate(panels=panels)


def test_false_CGAL_green_flag_is_not_sufficient():
    panels=deepcopy(PANELS)
    panels["angles"][2]["intersection"]="NONEMPTY"
    with pytest.raises(ValueError,match="display clashes"):
        _evaluate(panels=panels)


def test_missing_shell_angle_is_rejected():
    cad=deepcopy(CAD)
    cad["cgal_interference_sweep"].pop()
    with pytest.raises(ValueError,match="required"):
        _evaluate(cad=cad)


def test_upstream_cm4_fit_state_cannot_be_manufacturing_authorized():
    prior=deepcopy(PRIOR);prior["manufacturing_authorized"]=True
    with pytest.raises(ValueError,match="incorrectly authorized"):
        _evaluate(prior=prior)


def test_bad_or_stale_STL_bytes_fail_provenance(tmp_path):
    # Files in a temp replay directory intentionally break the mesh SHA chain.
    (tmp_path/"evidence").mkdir()
    for filename in ("base_shell.stl","lid_shell.stl","design_evidence.json"):
        data=(HERE/"evidence"/filename).read_bytes()
        if filename=="base_shell.stl":
            data+=b"BAD"
        (tmp_path/"evidence"/filename).write_bytes(data)
    (tmp_path/"spec.json").write_bytes((HERE/"spec.json").read_bytes())
    (tmp_path/"qualification_input.json").write_bytes((HERE/"qualification_input.json").read_bytes())
    (tmp_path/"panel_CGAL_report.json").write_bytes((HERE/"panel_CGAL_report.json").read_bytes())
    # Unchanged upstream path is relative to the real repo, so shadow copy it.
    (tmp_path.parent/"cm4_thin_stack/evidence").mkdir(parents=True,exist_ok=True)
    # Keep this test safe by invoking a copied report path in same temp parent.
    (tmp_path.parent/"cm4_thin_stack/evidence/cm4_stack_result.json").write_bytes(
        (ROOT/"examples/cyberdeck/cm4_thin_stack/evidence/cm4_stack_result.json").read_bytes())
    with pytest.raises(ValueError,match="does not match"):
        run(tmp_path/"qualification_input.json",tmp_path/"result.json")


def test_result_deterministic_from_same_repo_evidence(tmp_path):
    result=run(HERE/"qualification_input.json",tmp_path/"result.json")
    saved=json.loads((HERE/"hinge_qualification.json").read_text())
    assert result==saved
    assert (tmp_path/"result.json").read_bytes()==(HERE/"hinge_qualification.json").read_bytes()
