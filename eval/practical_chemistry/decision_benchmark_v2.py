"""Additional authored practical-material v2 cases beyond previous 31 tests.

Uses source-scoped manufacturer claims and deterministic engineering heuristics.
Not an independently validated specimen/supplier test, certification or
production recommendation.
"""
from __future__ import annotations

import json
from typing import Any

from hardware_splicer.practical_chemistry import assess_practical_chemistry, practical_catalog_summary


def case(case_id: str, task: str, material: str, approach_id: str, status: str,
         *, must_include: str | None = None, **extra: Any) -> dict[str, Any]:
    params = dict(task=task, primary_material=material, material_identity="verified",
                  electrical_state="off", battery_status="removed")
    params.update(extra)
    return {
        "id": case_id,
        "inputs": params,
        "method": approach_id,
        "status": status,
        "blocker_or_hold": must_include,
    }


def scenarios() -> list[dict[str, Any]]:
    thermal = dict(electrical_function_required="insulating",
                   contact_pressure_confirmed=True)
    return [
        case("pcb_rigid_potting_cure_unverified", "pot_electronics", "FR4",
             "pot_rigid_832hd", "research_required", must_include="potting_heat_and_cure_validation_missing",
             keepouts_confirmed=True),
        case("pcb_flexible_potting_stress_cure", "pot_electronics", "FR4",
             "pot_flexible_832fx", "research_required", must_include="potting_heat_and_cure_validation_missing",
             keepouts_confirmed=True, exposure=["heat_cycle"]),
        case("rigid_potting_cycling_stress_warning", "pot_electronics", "FR4",
             "pot_rigid_832hd", "research_required",
             must_include="rigid_potting_thermal_cycling_stress_unverified",
             keepouts_confirmed=True, exposure=["heat_cycle"]),
        case("potting_reentry_rigid_block", "pot_electronics", "FR4",
             "pot_rigid_832hd", "blocked",
             must_include="rework_requirement_incompatible_with_method",
             rework_required=True, keepouts_confirmed=True),
        case("potting_reentry_flexible_block", "pot_electronics", "FR4",
             "pot_flexible_832fx", "blocked",
             must_include="rework_requirement_incompatible_with_method",
             rework_required=True, keepouts_confirmed=True),
        case("potting_no_mask_hold", "pot_electronics", "FR4",
             "pot_rigid_832hd", "research_required", must_include="unplanned_masking"),
        case("potting_power_unknown", "pot_electronics", "FR4",
             "pot_rigid_832hd", "blocked", must_include="power_not_confirmed_isolated",
             electrical_state="unknown", keepouts_confirmed=True),
        case("potting_battery_unknown", "pot_electronics", "FR4",
             "pot_rigid_832hd", "blocked", must_include="battery_not_confirmed_removed",
             battery_status="unknown", keepouts_confirmed=True),
        case("thermal_gap_pad_nominal_not_proven", "manage_thermal_interface", "FR4",
             "tim_gap_pad_hc5000", "research_required",
             must_include="measured_interface_impedance_missing",
             interface_geometry={"thickness_mm":1.0,"contact_area_mm2":100,
                                 "heat_load_w":5,"allowable_rise_c":20}, **thermal),
        case("thermal_gap_pad_unknown_compression", "manage_thermal_interface", "FR4",
             "tim_gap_pad_hc5000", "research_required",
             must_include="pad_compression_pressure_unknown",
             interface_geometry={"thickness_mm":1.0,"contact_area_mm2":100,
                                 "heat_load_w":5,"allowable_rise_c":20},
             electrical_function_required="insulating"),
        case("thermal_gap_pad_ideal_bound_fails", "manage_thermal_interface", "FR4",
             "tim_gap_pad_hc5000", "blocked",
             must_include="thermal_bulk_lower_bound_exceeds_user_threshold",
             interface_geometry={"thickness_mm":1.0,"contact_area_mm2":100,
                                 "heat_load_w":15,"allowable_rise_c":20}, **thermal),
        case("thermal_pad_thicker_than_offered", "manage_thermal_interface", "FR4",
             "tim_gap_pad_hc5000", "blocked",
             must_include="gap_outside_nominal_pad_thickness_envelope",
             interface_geometry={"thickness_mm":4.0,"contact_area_mm2":100,
                                 "heat_load_w":1,"allowable_rise_c":80}, **thermal),
        case("thermal_gap_unknown_system", "manage_thermal_interface", "FR4",
             "tim_gap_pad_hc5000", "research_required",
             must_include="thermal_geometry_and_heat_load_missing",
             electrical_function_required="insulating"),
        case("thermal_electrical_role_unknown", "manage_thermal_interface", "FR4",
             "tim_gap_pad_hc5000", "research_required",
             must_include="electrical_insulation_need_unconfirmed",
             interface_geometry={"thickness_mm":1.0,"contact_area_mm2":100,
                                 "heat_load_w":2,"allowable_rise_c":20}),
        case("thermal_paste_thick_gap_block", "manage_thermal_interface", "aluminum",
             "tim_paste_860", "blocked",
             must_include="thermal_paste_inappropriate_for_declared_thick_gap_screen",
             interface_geometry={"thickness_mm":1.0,"contact_area_mm2":100,
                                 "heat_load_w":2,"allowable_rise_c":40}, **thermal),
        case("thermal_paste_thin_interface", "manage_thermal_interface", "aluminum",
             "tim_paste_860", "research_required",
             must_include="measured_interface_impedance_missing",
             interface_geometry={"thickness_mm":0.08,"contact_area_mm2":150,
                                 "heat_load_w":3,"allowable_rise_c":40}, **thermal),
        case("thermal_not_an_electrical_contact", "manage_thermal_interface", "FR4",
             "tim_gap_pad_hc5000", "blocked",
             must_include="catalog_thermal_products_do_not_establish_conductive_contact_function",
             electrical_function_required="conductive",
             interface_geometry={"thickness_mm":1.0,"contact_area_mm2":100,
                                 "heat_load_w":2,"allowable_rise_c":20}),
        case("seal_rtv_masking_unknown", "seal_enclosure", "ABS",
             "seal_neutral_1035", "research_required",
             must_include="unplanned_masking"),
        case("seal_rtv_neutral_cure_possible", "seal_enclosure", "ABS",
             "seal_neutral_1035", "candidate_for_validation",
             keepouts_confirmed=True),
        case("seal_rtv_battery_present_stop", "seal_enclosure", "ABS",
             "seal_neutral_1035", "blocked",
             must_include="battery_not_confirmed_removed",
             keepouts_confirmed=True,battery_status="installed"),
        case("silicone_o_ring_55_requires_testing", "lubricate_seals", "silicone_rubber",
             "seal_orings_55", "blocked",
             must_include="manufacturer_requires_special_testing_for_this_elastomer_or_plastic"),
        case("swelling_grease_dimensions_block", "lubricate_seals", "NBR",
             "seal_orings_55", "blocked",
             must_include="intentional_o_ring_swelling_incompatible_with_dimensional_stability",
             dimensional_stability_required=True),
        case("seal_compound_grade_unverified", "lubricate_seals", "EPDM",
             "seal_orings_111", "research_required",
             must_include="exact_elastomer_or_plastic_grade_compatibility_unverified"),
        case("seal_grease_adjacent_polycarbonate_warning", "lubricate_seals", "EPDM",
             "seal_orings_55", "blocked",
             must_include="manufacturer_requires_special_testing_for_this_elastomer_or_plastic",
             adjacent_materials=["PC"]),
        case("nylon_gear_lubrication_requires_trials", "lubricate_moving_parts", "nylon",
             "plastic_slide_ym102", "research_required",
             must_include="exact_elastomer_or_plastic_grade_compatibility_unverified"),
        case("pao_grease_not_unknown_grade_safe", "lubricate_moving_parts", "POM",
             "plastic_slide_ym102", "research_required",
             must_include="exact_elastomer_or_plastic_grade_compatibility_unverified"),
        case("conductive_contact_grease_requires_defined_role", "protect_contacts", "gold_contact",
             "contact_grease_846", "research_required",
             must_include="contact_electrical_function_unknown",
             keepouts_confirmed=True),
        case("conductive_grease_insulation_block", "protect_contacts", "gold_contact",
             "contact_grease_846", "blocked",
             must_include="conductive_grease_in_insulating_contact_zone",
             electrical_function_required="insulating", keepouts_confirmed=True),
        case("conductive_contact_grease_unmasked", "protect_contacts", "metal_contact",
             "contact_grease_846", "research_required",
             must_include="conductive_material_migration_keepouts_unverified",
             electrical_function_required="conductive"),
        case("conductive_contact_grease_plausible_test", "protect_contacts", "gold_contact",
             "contact_grease_846", "candidate_for_validation",
             electrical_function_required="conductive", keepouts_confirmed=True),
        case("corrosion_unknown_replace_research", "assess_corrosion", "FR4",
             "corrosion_replace", "research_required",
             must_include="corrosion_damage_classification_missing"),
        case("corrosion_trace_loss_blocks_cleaning_only", "assess_corrosion", "FR4",
             "liquid_damage_assessment", "blocked",
             must_include="material_loss_requires_repair_or_replacement_assessment",
             corrosion_damage="trace_loss"),
        case("corrosion_metal_loss_replacement", "assess_corrosion", "FR4",
             "corrosion_replace", "candidate_for_validation",
             corrosion_damage="trace_loss"),
        case("corrosion_surface_deposits_inspection", "assess_corrosion", "FR4",
             "liquid_damage_assessment", "candidate_for_validation",
             corrosion_damage="surface_residue"),
        case("corrosion_pitting_measured_integrity", "assess_corrosion", "metal_contact",
             "liquid_damage_assessment", "research_required",
             must_include="pitted_conductor_integrity_unverified",
             corrosion_damage="pitting"),
    ]


def run() -> dict[str, Any]:
    rows = []
    for c in scenarios():
        try:
            data = assess_practical_chemistry(**c["inputs"])
            method = next(m for m in data["approaches"] if m["approach_id"] == c["method"])
            observed = set(method["hard_blockers"]) | set(method["conditions_to_research_before_trial"])
            actual = method["status"]
            passed = (
                actual == c["status"]
                and (c["blocker_or_hold"] is None or c["blocker_or_hold"] in observed)
                and data["selected_method"] is None
                and not data["ready_to_execute_steps"]
                and not data["release_authorized"]
            )
            rows.append({"case":c["id"],"passed":passed,"method":c["method"],
                         "actual":actual,"expected":c["status"],
                         "conditions":sorted(observed),
                         "thermal":method.get("thermal_screen")})
        except Exception as e:
            rows.append({"case":c["id"],"passed":False,"error":type(e).__name__+":"+str(e)[:180]})
    summary = practical_catalog_summary()
    return {
        "schema_version": "hardware_splicer.practical_chemistry_v2_cases.v1",
        "authored_cases": len(rows), "passed": sum(x["passed"] for x in rows),
        "catalog_source_count": summary["source_count"],
        "catalog_method_count": summary["approach_count"],
        "catalog_task_count": len(summary["task_types"]),
        "rows":rows,
        "limitations":"Authored regression expectations, not physical performance or a blinded evaluation",
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    if result["passed"] != result["authored_cases"]:
        raise SystemExit(1)
