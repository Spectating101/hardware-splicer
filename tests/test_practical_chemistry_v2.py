from __future__ import annotations

import asyncio
import math

import pytest
from fastapi.testclient import TestClient

from eval.practical_chemistry.decision_benchmark_v1 import run as run_v1
from eval.practical_chemistry.decision_benchmark_v2 import run as run_v2
from hardware_splicer.mcp_backend_gateway import dispatch_operation, operation_catalog, task_operation_manifest
from hardware_splicer.practical_chemistry import assess_practical_chemistry, catalog, practical_catalog_summary
from hardware_splicer.practical_chemistry_thermal import thermal_interface_screen
from hardware_splicer.product_api import create_product_app


def base(task: str, material: str, **kwargs):
    d = dict(task=task, primary_material=material,
             material_identity="verified", electrical_state="off",
             battery_status="removed")
    d.update(kwargs)
    return d


def method(report, mid):
    return next(item for item in report["approaches"] if item["approach_id"] == mid)


def test_combined_catalog_is_unique_and_complete():
    data = catalog()
    assert data["schema_version"].endswith(".v2")
    assert len(data["sources"]) == len({r["id"] for r in data["sources"]})
    assert len(data["methods"]) == len({r["id"] for r in data["methods"]})
    assert len(data["sources"]) == 21
    assert len(data["methods"]) == 20
    assert len(practical_catalog_summary()["task_types"]) == 12
    ids = {x["id"] for x in data["sources"]}
    for m in data["methods"]:
        assert len(m["source_ids"]) and set(m["source_ids"]).issubset(ids)
        assert m["failure_modes"] and m["validation"]
        assert m["evidence_level"]
    assert any(s["id"] == "henkel_hc5000" and s["url"].startswith("https://datasheets.tdx.henkel.com/")
               for s in data["sources"])


def test_v1_31_and_v2_35_authored_cases_remain_green():
    old, new = run_v1(), run_v2()
    assert old["cases_passed"] == old["cases_total"] == 31
    assert new["passed"] == new["authored_cases"] == 35


def test_thermal_ideal_resistance_is_dimensions_and_heat_consistent():
    x = thermal_interface_screen(
        thickness_mm=1, contact_area_mm2=100, heat_load_w=5,
        bulk_conductivity_w_mk=5, allowable_rise_c=20,
    )
    assert x["bulk_only_ideal_resistance_k_per_w"] == 2
    assert x["bulk_only_ideal_delta_t_c"] == 10
    assert not x["fails_even_idealized_screen"]
    assert not x["actual_contact_resistance_accounted_for"]
    assert not x["prediction_is_full_device_thermal_model"]
    y = thermal_interface_screen(
        thickness_mm=1, contact_area_mm2=100, heat_load_w=15,
        bulk_conductivity_w_mk=5, allowable_rise_c=20,
    )
    assert y["bulk_only_ideal_delta_t_c"] == 30
    assert y["fails_even_idealized_screen"]


@pytest.mark.parametrize("patch", [
    {"thickness_mm":0},
    {"contact_area_mm2":-1},
    {"heat_load_w":float("nan")},
    {"bulk_conductivity_w_mk":float("inf")},
    {"allowable_rise_c":-1},
    {"contact_area_mm2":float("inf")},
])
def test_thermal_invalid_or_nonfinite_never_produces_a_result(patch):
    data = {
        "thickness_mm":1.0, "contact_area_mm2":100,
        "heat_load_w":5, "bulk_conductivity_w_mk":5,
        "allowable_rise_c":20,
    }
    data.update(patch)
    with pytest.raises(ValueError):
        thermal_interface_screen(**data)


def test_pad_actual_interface_always_requires_measurement():
    req = base("manage_thermal_interface", "FR4",
        electrical_function_required="insulating",
        interface_geometry=dict(thickness_mm=1, contact_area_mm2=100,
                                heat_load_w=5, allowable_rise_c=20),
        contact_pressure_confirmed=True)
    x = assess_practical_chemistry(**req)
    entry = method(x, "tim_gap_pad_hc5000")
    assert entry["thermal_screen"]["bulk_only_ideal_delta_t_c"] == 10
    assert entry["status"] == "research_required"
    assert "measured_interface_impedance_missing" in entry["conditions_to_research_before_trial"]
    assert not x["chemical_handling_authorized"]
    assert not entry["qualified_for_production"]


def test_pad_not_based_on_conductivity_alone_and_paste_cannot_fill_large_gap():
    req = base("manage_thermal_interface", "aluminum",
        electrical_function_required="insulating",
        contact_pressure_confirmed=True,
        interface_geometry=dict(thickness_mm=1.0, contact_area_mm2=100,
                                heat_load_w=3, allowable_rise_c=25))
    x = assess_practical_chemistry(**req)
    paste = method(x, "tim_paste_860")
    assert paste["status"] == "blocked"
    assert "thermal_paste_inappropriate_for_declared_thick_gap_screen" in paste["hard_blockers"]
    pad = method(x, "tim_gap_pad_hc5000")
    assert pad["status"] == "research_required"
    assert pad["thermal_screen"]["bulk_only_ideal_delta_t_c"] == 6


def test_potting_rework_and_heat_cycle_not_certified():
    req = base("pot_electronics", "FR4", keepouts_confirmed=True,
               rework_required=True, exposure=["heat_cycle"])
    x = assess_practical_chemistry(**req)
    assert x["decision"] == "research_or_replace"
    for mid in ("pot_rigid_832hd", "pot_flexible_832fx"):
        assert method(x, mid)["status"] == "blocked"
    assert "rigid_potting_thermal_cycling_stress_unverified" in (
        method(x, "pot_rigid_832hd")["conditions_to_research_before_trial"]
    )


def test_lubricant_dimensional_change_and_sensitive_elastomer():
    x = assess_practical_chemistry(**base("lubricate_seals","NBR",
                                          dimensional_stability_required=True))
    assert "intentional_o_ring_swelling_incompatible_with_dimensional_stability" in (
        method(x,"seal_orings_55")["hard_blockers"]
    )
    y = assess_practical_chemistry(**base("lubricate_seals","silicone_rubber"))
    assert "manufacturer_requires_special_testing_for_this_elastomer_or_plastic" in (
        method(y,"seal_orings_55")["hard_blockers"]
    )


def test_conductive_grease_cannot_be_used_as_insulator_or_without_keepouts():
    x = assess_practical_chemistry(**base("protect_contacts","gold_contact",
        keepouts_confirmed=True, electrical_function_required="insulating"))
    assert method(x,"contact_grease_846")["status"] == "blocked"
    y = assess_practical_chemistry(**base("protect_contacts","gold_contact",
        electrical_function_required="conductive"))
    assert method(y,"contact_grease_846")["status"] == "research_required"
    z = assess_practical_chemistry(**base("protect_contacts","gold_contact",
        keepouts_confirmed=True, electrical_function_required="conductive"))
    assert method(z,"contact_grease_846")["status"] == "candidate_for_validation"
    assert not z["fabrication_authorized"]


def test_corrosion_material_loss_not_treated_as_ordinary_cleaning():
    x = assess_practical_chemistry(**base("assess_corrosion","FR4",
                                          corrosion_damage="trace_loss"))
    assert "material_loss_requires_repair_or_replacement_assessment" in (
        method(x,"liquid_damage_assessment")["hard_blockers"]
    )
    assert method(x,"corrosion_replace")["status"] == "candidate_for_validation"


@pytest.mark.parametrize("patch", [
    {"interface_geometry":{"thickness_mm":1.0}},
    {"interface_geometry":{"thickness_mm":1.0,"contact_area_mm2":0,"heat_load_w":5}},
    {"interface_geometry":{"thickness_mm":1.0,"contact_area_mm2":100,
                            "heat_load_w":float("nan")}},
    {"interface_geometry":{"thickness_mm":1.0,"contact_area_mm2":100,
                            "heat_load_w":5,"extra":"injection"}},
])
def test_incomplete_or_unbounded_thermal_geometry_fails_closed(patch):
    with pytest.raises(ValueError):
        assess_practical_chemistry(**base("manage_thermal_interface","FR4",**patch))


def test_wrong_task_cannot_claim_thermal_geometry():
    with pytest.raises(ValueError):
        assess_practical_chemistry(**base("bond_joint","PP",
            interface_geometry={"thickness_mm":1,"contact_area_mm2":100,"heat_load_w":5}))


def test_practical_v2_same_canonical_api_and_mcp():
    app = create_product_app()
    client = TestClient(app)
    request = base("manage_thermal_interface", "FR4",
        electrical_function_required="insulating",
        interface_geometry={"thickness_mm":1,"contact_area_mm2":100,
                            "heat_load_w":5,"allowable_rise_c":20},
        contact_pressure_confirmed=True)
    response = client.post("/v1/engineering/chemical/practical/assess", json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    assert method(body,"tim_gap_pad_hc5000")["thermal_screen"]["bulk_only_ideal_delta_t_c"] == 10
    assert body["catalog_version"].endswith(".v2")
    catalog_reply = client.get("/v1/engineering/chemical/practical/catalog")
    assert catalog_reply.json()["approach_count"] == 20
    op = next(row for row in operation_catalog(app)
              if row["path"] == "/v1/engineering/chemical/practical/assess")
    actual = asyncio.run(dispatch_operation(op["operation_id"], app=app, json_body=request))
    assert actual["status_code"] == 200
    assert actual["body"]["selected_method"] is None
    manifest = task_operation_manifest("practical_chemistry_repair", app)
    assert op["operation_id"] in manifest["workflow_operation_ids"]


def test_api_rejects_nan_geometry_and_unknown_material_fields():
    app = TestClient(create_product_app())
    req = base("manage_thermal_interface","FR4",
        interface_geometry={"thickness_mm":"not-a-number","contact_area_mm2":100,"heat_load_w":5})
    reply = app.post("/v1/engineering/chemical/practical/assess",json=req)
    assert reply.status_code == 422
    req2 = base("lubricate_seals","something_not_catalogued")
    assert app.post("/v1/engineering/chemical/practical/assess", json=req2).status_code == 422
