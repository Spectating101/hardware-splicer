"""Hybrid sheet/print construction proposals through the actual HS Mecha path."""

from __future__ import annotations

import json
import math

import pytest

from hardware_splicer.construction_alternatives import (
    CONNECTOR_SOURCES, evaluate_construction_alternatives, render_construction_plan,
)


def _project():
    return {
        "project_name": "low-waste-sensor-box",
        "enclosure": {
            "inner_w_mm": 100, "inner_d_mm": 80, "inner_h_mm": 30,
            "wall_mm": 2, "floor_mm": 2, "lid_mm": 2,
        },
        "construction": {
            "preference": "auto",
            "operating_temp_c": 35,
            "chemical_exposures": ["humidity"],
            "panel_thickness_mm": 3,
            "connector_family": "moduframe",
            "connector_count": 4,
            "connector_print_volume_cm3": .6,
            "filament_material": {
                "material_id": "supplied-petg",
                "evidence_kind": "datasheet",
                "source_uri": "https://example.com/real-measurement-replaced-by-user",
                "density_kg_m3": 1250,
                "max_service_temp_c": 65,
                "cost_per_kg": 25,
                "chemical_compatibility": {"humidity": "compatible"},
            },
            "panel_material": {
                "material_id": "supplier-plywood",
                "evidence_kind": "datasheet",
                "source_uri": "https://example.com/real-measurement-replaced-by-user",
                "density_kg_m3": 550,
                "max_service_temp_c": 50,
                "cost_per_m2": 12,
                "chemical_compatibility": {"humidity": "unknown"},
            },
        },
    }


def _hybrid(result):
    return next(row for row in result["alternatives"]
                if row["method"] == "sheet_hybrid")


def test_no_implicit_construction_substitution():
    r=evaluate_construction_alternatives({"enclosure": _project()["enclosure"]})
    assert r["status"] == "not_requested"
    assert r["fabrication_authorized"] is False


def test_sourced_material_mass_cost_geometry_and_thermochemistry():
    result=evaluate_construction_alternatives(_project())
    assert result["status"] == "comparison_produced_research_only"
    assert result["enclosure_outer_dimensions_mm"] == [104,84,34]
    assert result["selected_manufacturing_method"] is None
    assert len(result["alternatives"]) == 3
    full=result["alternatives"][0]
    hybrid=_hybrid(result)
    assert full["estimated_solid_envelope_mm3"] == pytest.approx(57024)
    assert full["estimated_printed_mass_g"] == pytest.approx(71.28)
    assert hybrid["panel_area_mm2_unoptimized"] == pytest.approx(30256)
    assert hybrid["panel_mass_g"] == pytest.approx(49.9224,abs=.001)
    assert hybrid["connector_printed_mass_g"] == pytest.approx(3)
    assert hybrid["combined_estimated_mass_g"] == pytest.approx(52.922,abs=.002)
    assert result["hypothetical_full_print_minus_hybrid_mass_g"] == pytest.approx(18.358,abs=.002)
    assert result["hypothetical_material_cost_difference"] is not None
    assert result["thermal_screen"]["panel"] == "below_reported_limit_not_validated"
    assert result["chemical_screen"]["panel"] == {"humidity":"unknown"}
    assert "chemical_compatibility_unverified" in hybrid["blockers"]
    assert "external_connector_revision_unpinned" in hybrid["blockers"]
    assert hybrid["connector_source"]["local_asset_validated"] is False
    assert result["full_enclosure_thermal_simulation_performed"] is False
    assert result["structural_safety_verified"] is False
    assert result["release_authorized"] is False


def test_heat_limit_and_solvent_incompatibility_block_hybrid():
    project=_project()
    project["construction"]["operating_temp_c"] = 80
    project["construction"]["chemical_exposures"] = ["acetone"]
    project["construction"]["panel_material"]["chemical_compatibility"] = {
        "acetone": "incompatible"
    }
    report=evaluate_construction_alternatives(project)
    assert report["thermal_screen"]["panel"]=="above_reported_service_limit"
    assert report["thermal_screen"]["filament"]=="above_reported_service_limit"
    b=_hybrid(report)["blockers"]
    assert "panel_temperature_limit_exceeded" in b
    assert "filament_temperature_limit_exceeded" in b
    assert "panel_chemical_incompatibility" in b
    assert report["selected_manufacturing_method"] is None


def test_connector_nominal_size_mismatch_rejected():
    project=_project()
    project["construction"]["connector_family"]="clip_os"
    r=evaluate_construction_alternatives(project)
    assert "connector_nominal_thickness_mismatch" in _hybrid(r)["blockers"]
    assert r["selected_manufacturing_method"] is None


def test_missing_properties_do_not_create_imaginary_savings():
    project=_project()
    project["construction"]["filament_material"] = None
    project["construction"]["panel_material"] = None
    project["construction"]["connector_print_volume_cm3"] = None
    r=evaluate_construction_alternatives(project)
    assert r["hypothetical_full_print_minus_hybrid_mass_g"] is None
    assert r["hypothetical_material_cost_difference"] is None
    assert r["economic_preference"] == "cost_comparison_unavailable"
    assert "sheet_material_or_measured_thickness_missing" in _hybrid(r)["blockers"]


def test_external_sources_are_catalog_only_not_downloaded():
    assert {"clip_os","moduframe","bosl2","boxes_py"} <= set(CONNECTOR_SOURCES)
    r=evaluate_construction_alternatives(_project())
    assert r["selected_manufacturing_method"] is None
    h=_hybrid(r)
    assert h["connector_source"]["requires_external_asset"] is True
    assert h["connector_source"]["revision_pinned"] is False
    text=render_construction_plan(r)
    assert "No manufacturing method has been auto-selected" in text
    assert "ModuFrame" in text
    assert "Preliminary panel cut rectangles" in text
    assert "thermal" in text.lower() or "temperature" in text.lower()


@pytest.mark.parametrize("key,value", [
    ("panel_thickness_mm",-1),
    ("connector_count",-1),
    ("connector_print_volume_cm3",-1),
    ("printed_material_fraction",1.2),
    ("operating_temp_c",math.inf),
    ("connector_family","invented"),
])
def test_invalid_input_is_rejected(key,value):
    p=_project()
    p["construction"][key]=value
    with pytest.raises(ValueError):
        evaluate_construction_alternatives(p)


def test_unscoped_geometry_does_not_get_fake_cut_plan():
    p=_project()
    p.pop("enclosure")
    r=evaluate_construction_alternatives(p)
    assert r["status"]=="unsupported_non_enclosure"
    assert r["alternatives"] == []


def test_mecha_runner_integrates_risk_recipe_and_keeps_original_cad(tmp_path):
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha-Splicer is not installed in this CI environment")
    from mecha_splicer.runner import run
    bundle=run(_project(),out_dir=tmp_path)
    assert bundle["construction_alternatives"]["status"] == "comparison_produced_research_only"
    assert bundle["structural_screening"]["status"]=="unsupported_mechanical_topology"
    assert (tmp_path/"enclosure.scad").exists()
    assert not (tmp_path/"panel_connector.scad").exists()
    assert (tmp_path/"CONSTRUCTION_ALTERNATIVES.json").exists()
    assert (tmp_path/"CONSTRUCTION_PLAN.md").exists()
    assert "ModuFrame" in (tmp_path/"CONSTRUCTION_PLAN.md").read_text()
    assert "chemical_compatibility_unverified" in (tmp_path/"RISK_REGISTER.md").read_text()
    assert "CONSTRUCTION_PLAN.md" in (tmp_path/"BUILD_RECIPE.md").read_text()
    assert "Construction alternatives" in (tmp_path/"MECH_CHECK.md").read_text() or (
        "Construction and Material Alternatives" in (tmp_path/"MECH_CHECK.md").read_text()
    )
    saved=json.loads((tmp_path/"mecha_splicer.bundle.json").read_text())
    assert saved["construction_alternatives"]["selected_manufacturing_method"] is None
    sim=json.loads((tmp_path/"SIM_RESULTS.json").read_text())
    assert sim["construction_alternatives"]["fabrication_authorized"] is False
    assert bundle["construction_alternatives"]["release_authorized"] is False


def test_typed_construction_spec_rejects_negative_geometry():
    from hardware_splicer.mechanism_bridge import _ensure_mecha_on_path
    if not _ensure_mecha_on_path():
        pytest.skip("Mecha-Splicer unavailable")
    from mecha_splicer.spec import ProjectSpec
    with pytest.raises(ValueError):
        ProjectSpec.model_validate({
            **_project(),
            "construction": {
                **_project()["construction"],
                "panel_thickness_mm": -2,
            },
        })


def test_hs_mechanism_pack_propagates_requested_construction(tmp_path):
    from hardware_splicer.mechanism_bridge import run_mechanism_pack
    record = run_mechanism_pack(
        project_name="salvaged-sensor",
        build_id="sensor_logger",
        out_dir=tmp_path,
        construction=_project()["construction"],
    )
    assert record["status"] == "ok"
    assert record["project_spec"]["construction"]["connector_family"] == "moduframe"
    construction = record["construction_alternatives"]
    assert construction["status"] == "comparison_produced_research_only"
    assert construction["selected_manufacturing_method"] is None
    assert construction["release_authorized"] is False
    assert (tmp_path/"mecha_bundle"/"CONSTRUCTION_PLAN.md").exists()
