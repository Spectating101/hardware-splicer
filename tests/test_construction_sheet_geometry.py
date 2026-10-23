"""Physical shop proposal integration across geometry, Mecha and HS."""

from __future__ import annotations

import builtins
import csv
import io
import json

import pytest

from hardware_splicer.construction_sheet_geometry import (
    make_panel_schedule, schedule_csv, schedule_svg, schedule_parts,
)


def _enclosure():
    return {"inner_w_mm":100,"inner_d_mm":80,"inner_h_mm":30,
            "wall_mm":2,"floor_mm":2,"lid_mm":2,
            "cutouts":[{"face":"front","kind":"rect","label":"USB",
                        "rect":{"x_mm":10,"y_mm":5,"w_mm":12,"h_mm":7}}]}


def _construction():
    return {"preference":"auto","panel_thickness_mm":3,
            "connector_family":"moduframe","connector_count":4,
            "panel_material":{"material_id":"placeholder-panel",
                              "evidence_kind":"assumed"}}


def test_inner_space_preserved_with_panel_thickness_not_3d_print_wall():
    r=make_panel_schedule(_enclosure(),_construction())
    assert r["target_internal_dimensions_mm"]==[100,80,30]
    assert r["hybrid_outer_dimensions_mm"]==[106,86,36]
    assert r["unoptimized_total_panel_area_mm2"]==29392
    assert r["blank_panel_volume_mm3"]==88176
    assert [(p["part_id"],p["quantity"],p["width_mm"],p["height_mm"])
            for p in r["panels"]]==[
        ("front_back",2,106,36),
        ("left_right",2,80,36),
        ("floor_lid",2,100,80),
    ]
    assert r["buildable"] is False
    assert r["fabrication_authorized"] is False
    assert r["untransformed_interfaces"][0]["label"]=="USB"
    assert r["untransformed_interfaces"][0]["status"]=="untransformed_mark_for_review_not_cut"
    assert any("not_transferred" in b for b in r["blockers"])


def test_no_sheet_thickness_does_not_emit_cut_geometry():
    c=_construction()
    del c["panel_thickness_mm"]
    r=make_panel_schedule(_enclosure(),c)
    assert r["status"]=="missing_measured_panel_thickness"
    assert r["panels"] == []
    assert "MEASUREMENT REQUIRED" in schedule_svg(r)
    assert schedule_parts(r,c) == []


def test_dimensioned_cut_sheet_csv_svg_and_distinct_hybrid_parts():
    r=make_panel_schedule(_enclosure(),_construction())
    rows=list(csv.DictReader(io.StringIO(schedule_csv(r))))
    assert len(rows)==3
    assert rows[0]["faces"]=="front/back"
    assert rows[0]["quantity"]=="2"
    assert rows[0]["thickness_mm"]=="3.0"
    drawing=schedule_svg(r)
    assert "<svg" in drawing
    assert 'width="106.000mm"' not in drawing  # Includes drawing margin
    assert 'width="106.000"' in drawing
    assert "NOT VERIFIED CAM" in drawing
    assert "<script" not in drawing
    bom=schedule_parts(r,_construction())
    assert len(bom)==5
    assert sum(x["quantity"] for x in bom if x["kind"]=="sheet_blank")==6
    assert bom[-2]["source_key"]=="moduframe"
    assert bom[-1]["quantity"] is None


@pytest.mark.parametrize("value",[0,-1,2501,float("inf"),"bad"])
def test_unsafe_stock_thickness_refused(value):
    construction=_construction()
    construction["panel_thickness_mm"]=value
    with pytest.raises(ValueError):
        make_panel_schedule(_enclosure(),construction)


def test_mecha_exports_shop_packet_and_does_not_cut_ports(tmp_path):
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha package not available")
    from mecha_splicer.runner import run
    result=run({
        "project_name":"operator-electronics-enclosure",
        "enclosure":_enclosure(),
        "construction":_construction(),
    },out_dir=tmp_path)
    assert (tmp_path/"enclosure.scad").is_file()
    assert (tmp_path/"HYBRID_PANEL_BLANKS.svg").is_file()
    assert (tmp_path/"HYBRID_PANEL_CUTS.csv").is_file()
    interface=json.loads((tmp_path/"HYBRID_INTERFACE_REVIEW.json").read_text())
    assert interface["fabrication_authorized"] is False
    assert interface["geometry"][0]["label"]=="USB"
    assert interface["geometry"][0]["status"]=="untransformed_mark_for_review_not_cut"
    assert "HYBRID_PANEL_BLANKS.svg" in (tmp_path/"BUILD_RECIPE.md").read_text()
    assert result["construction_alternatives"]["selected_manufacturing_method"] is None


def test_existing_mecha_enclosure_defaults_to_advisory_comparison(tmp_path):
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha package not available")
    from mecha_splicer.runner import run
    r=run({"project_name":"automatic-reuse-prompt","enclosure":_enclosure()},
          out_dir=tmp_path)
    assert r["construction_alternatives"]["requested_preference"]=="auto"
    assert r["construction_alternatives"]["alternatives"][1]["status"]=="blocked_pending_evidence"
    assert (tmp_path/"CONSTRUCTION_PLAN.md").exists()
    assert not (tmp_path/"HYBRID_PANEL_BLANKS.svg").exists()


def test_standalone_mecha_without_hs_construction_evaluator_is_graceful(tmp_path,monkeypatch):
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha package not available")
    from mecha_splicer.runner import run
    original_import=builtins.__import__

    def hide_hs(name,*args,**kwargs):
        if name.startswith("hardware_splicer."):
            raise ImportError("deliberate standalone test")
        return original_import(name,*args,**kwargs)

    with monkeypatch.context() as m:
        m.setattr(builtins,"__import__",hide_hs)
        r=run({"project_name":"standalone-mecha",
               "enclosure":_enclosure()},out_dir=tmp_path)
    assert r["construction_alternatives"]["status"]=="capability_unavailable"
    assert (tmp_path/"CONSTRUCTION_PLAN.md").exists()
    assert "not installed" in (tmp_path/"CONSTRUCTION_PLAN.md").read_text()
    assert (tmp_path/"enclosure.scad").exists()


def test_main_hs_intake_preserves_construction_intent_in_compiler_spec():
    from pathlib import Path
    from hardware_splicer.project_intake import load_project_intake,plan_project_from_intake
    root=Path(__file__).resolve().parents[1]
    intake=load_project_intake(root/"examples"/"intakes"/"plant_watering_brief.json")
    intake["construction"]=_construction()
    plan=plan_project_from_intake(intake,skip_vision=True)
    assert plan["scenario"]["compile_spec"]["mechanism"]["construction"] == _construction()
    from hardware_splicer.schemas import HardwareCompileSpec
    typed=HardwareCompileSpec.from_dict(plan["scenario"]["compile_spec"])
    assert typed.mechanism["construction"]["connector_family"]=="moduframe"


@pytest.mark.parametrize("fixture,expected_thickness,source", [
    ("hybrid_cardstock_clip_os.json",1.6,"clip_os"),
    ("hybrid_plywood_moduframe.json",3.0,"moduframe"),
])
def test_real_operator_example_variants_run_with_same_internal_dims(
    tmp_path,fixture,expected_thickness,source,
):
    from pathlib import Path
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha unavailable")
    from mecha_splicer.runner import run
    root=Path(__file__).resolve().parents[1]
    project=json.loads((root/"examples"/"mechanical"/fixture).read_text())
    r=run(project,out_dir=tmp_path)
    comparison=r["construction_alternatives"]
    assert comparison["requested_preference"]=="sheet_hybrid"
    assert comparison["selected_manufacturing_method"] is None
    assert comparison["fabrication_authorized"] is False
    assert comparison["hybrid_sheet_geometry"]["target_internal_dimensions_mm"]==[100,80,30]
    assert comparison["hybrid_sheet_geometry"]["panel_thickness_mm"]==expected_thickness
    assert next(a for a in comparison["alternatives"] if a["method"]=="sheet_hybrid")[
        "connector_source"]["id"]==source
    assert (tmp_path/"HYBRID_PANEL_CUTS.csv").exists()
    assert (tmp_path/"HYBRID_PANEL_BLANKS.svg").exists()
    assert comparison["hypothetical_material_cost_difference"] is None
