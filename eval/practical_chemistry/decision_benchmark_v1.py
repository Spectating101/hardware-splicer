"""Authored practical repair-material decision regression benchmark.

Manufacturer sources are real public guidance; scenarios, material labels,
economic quotes and desired outcomes are *constructed examples*. These are
not an independent compatibility, safety or repair-success benchmark.
"""
from __future__ import annotations

import json
from typing import Any

from hardware_splicer.practical_chemistry import assess_practical_chemistry, practical_catalog_summary


def _case(case_id: str, task: str, material: str, *,
          expected: str, candidate: str | None = None,
          status: str | None = None, blocker: str | None = None,
          **changes: Any) -> dict[str, Any]:
    return {
        "id": case_id, "parameters": {
            "task": task, "primary_material": material,
            "material_identity": "verified", "battery_status": "removed",
            "electrical_state": "off", **changes,
        },
        "expected_decision": expected,
        "approach_id": candidate,
        "approach_status": status,
        "required_blocker": blocker,
    }


def scenarios() -> list[dict[str, Any]]:
    return [
        _case("pp_specialty_adhesive", "bond_joint", "PP", expected="options_for_validation",
              candidate="polyolefin_dp8010", status="candidate_for_validation"),
        _case("pe_specialty_adhesive", "bond_joint", "PE", expected="options_for_validation",
              candidate="polyolefin_dp8010", status="candidate_for_validation"),
        _case("pp_not_generic_epoxy", "bond_joint", "PP", expected="options_for_validation",
              candidate="engineered_plastic_dp100", status="blocked",
              blocker="no_evidence_for_target_substrate"),
        _case("abs_epoxy_insufficient", "bond_joint", "ABS", expected="research_or_replace",
              candidate="engineered_plastic_dp100", status="research_required"),
        _case("pc_coated_grade_unknown", "bond_joint", "PC", expected="research_or_replace",
              candidate="engineered_plastic_dp100", status="research_required"),
        _case("pp_joint_must_be_reworkable", "bond_joint", "PP", expected="research_or_replace",
              candidate="polyolefin_dp8010", status="blocked",
              blocker="rework_requirement_incompatible_with_method", rework_required=True),
        _case("pp_grade_unconfirmed", "bond_joint", "PP", expected="research_or_replace",
              candidate="polyolefin_dp8010", status="research_required", material_identity="claimed"),
        _case("pp_high_service_temperature", "bond_joint", "PP", expected="research_or_replace",
              candidate="polyolefin_dp8010", status="research_required", service_temperature_c=115),
        _case("critical_structural_bond", "bond_joint", "PP", expected="stop_and_escalate",
              candidate="polyolefin_dp8010", status="blocked",
              blocker="safety_critical_application_requires_specialist", duty="safety_critical"),
        _case("pcb_flux_normal", "clean_flux", "FR4", expected="options_for_validation",
              candidate="flux_removal_4140", status="candidate_for_validation",
              keepouts_confirmed=True),
        _case("pcb_flux_adjacent_unknown", "clean_flux", "FR4", expected="research_or_replace",
              candidate="flux_removal_4140", status="research_required", adjacent_materials=["unknown"]),
        _case("pcb_flux_adjacent_polycarbonate", "clean_flux", "FR4", expected="research_or_replace",
              candidate="flux_removal_4140", status="research_required", adjacent_materials=["PC"]),
        _case("live_pcb_cleaning_stop", "clean_flux", "FR4", expected="stop_and_escalate",
              candidate="flux_removal_4140", status="blocked",
              blocker="power_not_confirmed_isolated", electrical_state="energized"),
        _case("battery_installed_cleaning_stop", "clean_flux", "FR4", expected="stop_and_escalate",
              candidate="flux_removal_4140", status="blocked",
              blocker="battery_not_confirmed_removed", battery_status="installed"),
        _case("damaged_battery_stop", "assess_corrosion", "FR4", expected="stop_and_escalate",
              candidate="liquid_damage_assessment", status="blocked",
              blocker="damaged_battery_safety_stop", battery_status="damaged"),
        _case("contact_residue_forbidden", "clean_contacts", "gold_contact",
              expected="options_for_validation", candidate="contact_clean_801b",
              status="blocked", blocker="residual_film_prohibited", residue_tolerance="none"),
        _case("zero_residue_contact_cleaner", "clean_contacts", "gold_contact",
              expected="options_for_validation", candidate="contact_clean_409b",
              status="candidate_for_validation", residue_tolerance="none"),
        _case("contact_lubricating_film_allowed", "clean_contacts", "gold_contact",
              expected="options_for_validation", candidate="contact_clean_801b",
              status="candidate_for_validation", residue_tolerance="allowed"),
        _case("contact_film_unknown", "clean_contacts", "gold_contact",
              expected="options_for_validation", candidate="contact_clean_801b",
              status="research_required", residue_tolerance="unknown"),
        _case("pcb_conformal_mask_not_planned", "coat_pcb", "FR4",
              expected="research_or_replace", candidate="coat_pcb_419d",
              status="research_required"),
        _case("pcb_acrylic_coat_mask_prepared", "coat_pcb", "FR4",
              expected="options_for_validation", candidate="coat_pcb_419d",
              status="candidate_for_validation", keepouts_confirmed=True),
        _case("pcb_flexible_coat_mask_prepared", "coat_pcb", "FR4",
              expected="options_for_validation", candidate="coat_pcb_422b",
              status="candidate_for_validation", keepouts_confirmed=True,
              exposure=["heat_cycle","moisture"]),
        _case("asa_aggressive_solvent_specialist", "finish_surface", "ASA",
              expected="research_or_replace", candidate="asa_solvent_finish",
              status="research_required", keepouts_confirmed=True),
        _case("asa_solvent_near_pc_hardblock", "finish_surface", "ASA",
              expected="research_or_replace", candidate="asa_solvent_finish",
              status="blocked", blocker="aggressive_solvent_near_other_materials",
              adjacent_materials=["PC"], keepouts_confirmed=True),
        _case("abs_not_asa_solvent", "finish_surface", "ABS",
              expected="research_or_replace", candidate="asa_solvent_finish",
              status="blocked", blocker="no_evidence_for_target_substrate"),
        _case("corrosion_assessment_unpowered", "assess_corrosion", "FR4",
              expected="options_for_validation", candidate="liquid_damage_assessment",
              status="candidate_for_validation"),
        _case("unknown_plastic_never_assumed", "bond_joint", "unknown",
              expected="stop_and_escalate", candidate="replace_part",
              status="blocked", blocker="material_identity_unknown",
              material_identity="unknown"),
        _case("wrong_substrate_contact_cleaner", "clean_contacts", "PP",
              expected="research_or_replace", candidate="contact_clean_801b",
              status="blocked", blocker="no_evidence_for_target_substrate"),
        _case("adhesive_joint_rigid_cannot_rework", "bond_joint", "ABS",
              expected="research_or_replace", candidate="engineered_plastic_dp100",
              status="blocked", blocker="rework_requirement_incompatible_with_method",
              rework_required=True),
        _case("high_load_bond_must_test", "bond_joint", "PP",
              expected="options_for_validation", candidate="polyolefin_dp8010",
              status="candidate_for_validation", duty="high_load",
              exposure=["moisture", "vibration"]),
        _case("no_power_status_for_coating", "coat_pcb", "FR4",
              expected="stop_and_escalate", candidate="coat_pcb_419d",
              status="blocked", blocker="power_not_confirmed_isolated",
              electrical_state="unknown", keepouts_confirmed=True),
    ]


def run() -> dict[str, Any]:
    rows = []
    for scenario in scenarios():
        try:
            report = assess_practical_chemistry(**scenario["parameters"])
            row = next((item for item in report["approaches"]
                        if item["approach_id"] == scenario["approach_id"]), None)
            reasons = row["hard_blockers"] if row else []
            passed = (report["decision"] == scenario["expected_decision"]
                      and row is not None and row["status"] == scenario["approach_status"]
                      and (scenario["required_blocker"] is None
                           or scenario["required_blocker"] in reasons)
                      and report["selected_method"] is None
                      and not report["physical_action_authorized"]
                      and not report["release_authorized"])
            rows.append({
                "case": scenario["id"], "pass": passed, "decision": report["decision"],
                "selected_approach": scenario["approach_id"],
                "approach_status": row["status"] if row else None,
                "blockers": reasons,
                "expected_decision": scenario["expected_decision"],
            })
        except Exception as exc:
            rows.append({"case": scenario["id"], "pass": False,
                         "error": type(exc).__name__ + ": " + str(exc)[:230]})
    return {
        "schema_version": "hardware_splicer.practical_chemistry_case_benchmark.v1",
        "cases_total": len(rows),
        "cases_passed": sum(row["pass"] for row in rows),
        "catalog_approaches": practical_catalog_summary()["approach_count"],
        "catalog_sources": practical_catalog_summary()["source_count"],
        "cases": rows,
        "benchmark_limits": [
            "These expected outcomes are hand-authored; not independent manufacturer approval.",
            "No physical trials, supplier-stock check, price retrieval, toxicity analysis, certification or measured failure probabilities.",
            "Broad product-family claims do not prove exact specimen compatibility.",
        ],
    }


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2))
    if result["cases_passed"] != result["cases_total"]:
        raise SystemExit(1)
