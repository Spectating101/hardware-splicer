"""Evidence-scoped practical materials, cleaning, bonding and protection advisor.

Intentional limits:
- Manufacturer guidance is catalogued as *scope-limited claims*, never as a
  compatibility certificate or a universal chemical fact.
- No procedural chemical processing or unsafe handling instructions are issued.
- No automatic material identification, purchasing, fabrication or actuation.
- Economic calculation is based solely on explicit user quotes, not prices
  inferred from product descriptions or manufacturer claims.
"""
from __future__ import annotations

from importlib.resources import files
import json
import math
from typing import Any, Mapping

from .chemical_engineering import NON_AUTHORITY

_CATALOG_FILE = "practical_chemistry_catalog_v1.json"
_TASKS = frozenset({"clean_flux", "clean_contacts", "bond_joint", "coat_pcb", "finish_surface", "assess_corrosion"})
_MATERIALS = frozenset({"FR4", "metal_contact", "gold_contact", "ABS", "ASA", "PC", "PP", "PE", "PETG", "acrylic", "unknown"})
_BATTERY_STATUSES = frozenset({"none", "removed", "installed", "damaged", "unknown"})
_PROVENANCE = ("specific_product", "product_family", "broad_product_claim", "material_family", "repair_guidance", "general_alternative")
_CONTACT_TASKS = frozenset({"clean_flux", "clean_contacts", "coat_pcb", "assess_corrosion"})
_NON_REWORKABLE = frozenset({"structural_acrylic", "general_epoxy", "polymer_solvent_finish"})
_CONSUMABLE_CLASSES = frozenset({"electronics_cleaner", "contact_cleaner", "acrylic_conformal", "hybrid_conformal", "polymer_solvent_finish", "structural_acrylic", "general_epoxy"})


def catalog() -> dict[str, Any]:
    data = json.loads(files("hardware_splicer").joinpath("data", _CATALOG_FILE).read_text(encoding="utf-8"))
    sources = {row["id"]: row for row in data["sources"]}
    if len(sources) != len(data["sources"]):
        raise ValueError("Duplicate evidence source ID in practical catalog")
    methods = data["methods"]
    if len(methods) != len({row["id"] for row in methods}):
        raise ValueError("Duplicate practical approach ID")
    for method in methods:
        if method["task"] not in _TASKS or not method["target_materials"] or not method["validation"]:
            raise ValueError("Practical approach metadata incomplete")
        if method["evidence_level"] not in _PROVENANCE:
            raise ValueError("Unrecognized evidence specificity")
        if any(key not in sources for key in method["source_ids"]):
            raise ValueError("Approach references absent source")
    return data


def _validate_quote(quote: Mapping[str, Any]) -> dict[str, float] | None:
    if not isinstance(quote, Mapping):
        raise ValueError("Each economic quote must be a mapping")
    names = ("consumables_cost", "labor_minutes", "hourly_labor_cost", "testing_cost",
             "equipment_allocation", "replacement_cost", "probability_of_success",
             "failed_attempt_disposal_cost")
    parsed = {}
    for name in names:
        if name not in quote or quote[name] is None:
            continue
        value = quote[name]
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"{name} must be numeric")
        amount = float(value)
        if not math.isfinite(amount) or amount < 0 or amount > 1e9:
            raise ValueError(f"{name} is outside finite nonnegative bounds")
        if name == "probability_of_success" and amount > 1:
            raise ValueError("Probability of success cannot exceed one")
        parsed[name] = amount
    if not parsed:
        return None
    for required in ("consumables_cost", "labor_minutes", "hourly_labor_cost",
                     "testing_cost", "equipment_allocation"):
        if required not in parsed:
            raise ValueError(f"Cost inputs incomplete; missing {required}")
    if "probability_of_success" in parsed and (
        "replacement_cost" not in parsed or "failed_attempt_disposal_cost" not in parsed
    ):
        raise ValueError("Expected-cost calculation requires replacement and failure-path costs")
    return parsed


def _economics(quote: Mapping[str, Any] | None, *, currency: str | None) -> dict[str, Any] | None:
    if quote is None:
        return None
    q = _validate_quote(quote)
    if q is None:
        return None
    cost = (q["consumables_cost"] + q["testing_cost"] + q["equipment_allocation"]
            + q["labor_minutes"] * q["hourly_labor_cost"] / 60.0)
    result: dict[str, Any] = {
        "currency": currency,
        "declared_attempt_cost": round(cost, 4),
        "breakdown": {
            "materials": q["consumables_cost"], "labor": round(q["labor_minutes"]*q["hourly_labor_cost"]/60, 4),
            "testing": q["testing_cost"], "equipment_allocation": q["equipment_allocation"],
        },
        "failure_path_and_probability_verified": False,
        "cost_is_not_quote_verification": True,
    }
    if "replacement_cost" in q:
        result["replacement_cost"] = q["replacement_cost"]
        result["attempt_cost_below_replacement_only"] = cost < q["replacement_cost"]
    if "replacement_cost" in q and "failed_attempt_disposal_cost" in q:
        # Cost = attempt + (1-p) * (replacement + failure_disposal)
        # Break-even vs direct replacement:
        # p > (attempt + failure_disposal)/(replacement + failure_disposal)
        denom = q["replacement_cost"] + q["failed_attempt_disposal_cost"]
        threshold = ((cost + q["failed_attempt_disposal_cost"]) / denom
                     if denom > 0 else None)
        result["break_even_success_probability_min_exclusive"] = (
            round(threshold, 6) if threshold is not None else None
        )
        result["repair_can_economically_beat_direct_replacement"] = (
            threshold is not None and threshold < 1.0
        )
        result["break_even_is_conditional_on_quoted_failure_path"] = True
    if "probability_of_success" in q:
        prob = q["probability_of_success"]
        expected = (cost + (1-prob) * (q["replacement_cost"] + q["failed_attempt_disposal_cost"]))
        result.update({
            "assumed_probability_of_success": prob,
            "failed_attempt_disposal_cost": q["failed_attempt_disposal_cost"],
            "conditional_expected_total_cost": round(expected, 4),
            "conditional_expected_cost_below_direct_replacement": expected < q["replacement_cost"],
            "probability_source": "caller_assumption_not_estimated_by_hs",
        })
    else:
        result["conditional_expected_total_cost"] = None
        result["missing_uncertainty_inputs"] = [
            "probability_of_success", "failed_attempt_disposal_cost"
        ] if "replacement_cost" in q else ["replacement_cost", "probability_of_success",
                                          "failed_attempt_disposal_cost"]
    return result


def assess_practical_chemistry(
    *, task: str,
    primary_material: str,
    material_identity: str,
    adjacent_materials: list[str] | None = None,
    electrical_state: str = "unknown",
    battery_status: str = "unknown",
    duty: str = "cosmetic",
    exposure: list[str] | None = None,
    rework_required: bool = False,
    residue_tolerance: str = "unknown",
    keepouts_confirmed: bool = False,
    service_temperature_c: float | None = None,
    cost_quotes: Mapping[str, Mapping[str, Any]] | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    if task not in _TASKS:
        raise ValueError("Unknown practical chemistry goal")
    if primary_material not in _MATERIALS:
        raise ValueError("Unknown canonical material family")
    if material_identity not in {"verified", "claimed", "unknown"}:
        raise ValueError("Material identity state must be verified, claimed or unknown")
    if electrical_state not in {"off", "energized", "unknown"}:
        raise ValueError("Electrical isolation state invalid")
    if battery_status not in _BATTERY_STATUSES:
        raise ValueError("Battery state invalid")
    if duty not in {"cosmetic", "normal", "high_load", "safety_critical"}:
        raise ValueError("Unsupported duty classification")
    if residue_tolerance not in {"none", "allowed", "unknown"}:
        raise ValueError("Unsupported residue tolerance")
    neighbors = sorted(set(adjacent_materials or []))
    if len(neighbors) > 20 or any(mat not in _MATERIALS for mat in neighbors):
        raise ValueError("Invalid list of adjacent materials")
    environments = sorted(set(exposure or []))
    allowed_env = {"moisture", "uv", "heat_cycle", "chemical_exposure", "vibration", "none"}
    if len(environments) > 10 or any(item not in allowed_env for item in environments):
        raise ValueError("Unsupported exposure descriptor")
    if service_temperature_c is not None and (
        isinstance(service_temperature_c, bool) or not isinstance(service_temperature_c, (int, float))
        or not math.isfinite(service_temperature_c) or not -50 <= service_temperature_c <= 300
    ):
        raise ValueError("Service temperature outside supported request bounds")
    if currency is not None and (
        not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha()
    ):
        raise ValueError("Currency must be a three-letter ISO code")
    if cost_quotes is not None:
        if not isinstance(cost_quotes, Mapping) or len(cost_quotes) > 100:
            raise ValueError("Cost quotes must be a bounded mapping")
        for val in cost_quotes.values():
            _validate_quote(val)

    evidence = catalog()
    sources = {item["id"]: item for item in evidence["sources"]}
    electrical_sensitive = task in _CONTACT_TASKS
    global_blockers = []
    if electrical_state != "off":
        global_blockers.append("power_not_confirmed_isolated")
    if battery_status == "damaged":
        global_blockers.append("damaged_battery_safety_stop")
    elif electrical_sensitive and battery_status != "none" and battery_status != "removed":
        global_blockers.append("battery_not_confirmed_removed")
    if duty == "safety_critical":
        global_blockers.append("safety_critical_application_requires_specialist")
    if primary_material == "unknown" or material_identity == "unknown":
        global_blockers.append("material_identity_unknown")

    methods_by_id = {row["id"]: row for row in evidence["methods"]}
    if cost_quotes and any(key not in methods_by_id or methods_by_id[key]["task"] != task
                           for key in cost_quotes):
        raise ValueError("Cost quote references an absent or inapplicable approach")
    results = []
    for method in evidence["methods"]:
        if method["task"] != task:
            continue
        reasons = list(global_blockers)
        research = []
        hold_for_evidence = []
        if primary_material not in method["target_materials"]:
            reasons.append("no_evidence_for_target_substrate")
        if material_identity == "claimed" and primary_material != "unknown":
            research.append("confirm_actual_material_grade_and_treatments")
            hold_for_evidence.append("unverified_material_identity")
        if method["evidence_level"] in {"broad_product_claim", "material_family", "general_alternative"}:
            research.append("exact_product_and_substrate_grade_data_missing")
        if method["needs_masking"] and not keepouts_confirmed:
            research.append("keepout_and_masking_plan_missing")
            hold_for_evidence.append("unplanned_masking")
        if rework_required and method["family"] in _NON_REWORKABLE:
            reasons.append("rework_requirement_incompatible_with_method")
        if method["film_leaves_residue"] and task == "clean_contacts":
            if residue_tolerance == "none":
                reasons.append("residual_film_prohibited")
            if residue_tolerance == "unknown":
                hold_for_evidence.append("contact_residue_policy_unknown")
        if method["film_leaves_residue"] and "chemical_exposure" in environments:
            research.append("coating_or_film_environmental_resistance_not_confirmed")
        if method["uses_aggressive_solvent"]:
            hold_for_evidence.append("aggressive_solvent_specialist_review_required")
        if method["uses_aggressive_solvent"] and neighbors:
            reasons.append("aggressive_solvent_near_other_materials")
        if method["sensitive_materials"] and any(mat in method["sensitive_materials"] for mat in neighbors):
            research.append("nearby_component_compatibility_not_verified")
            hold_for_evidence.append("adjacent_material_grade_compatibility_unknown")
        if "unknown" in neighbors:
            research.append("adjacent_material_identity_missing")
            hold_for_evidence.append("unknown_adjacent_material")
        if duty == "high_load" and method["family"] in {"structural_acrylic", "general_epoxy"}:
            research.append("representative_mechanical_joint_testing_required")
        if duty == "high_load" and method["family"] not in {"structural_acrylic", "general_epoxy", "nonchemical_alternative"}:
            reasons.append("insufficient_high_load_application_evidence")
        if service_temperature_c is not None:
            research.append("service_temperature_within_product_limits_not_verified")
            hold_for_evidence.append("unverified_service_temperature")
        if "uv" in environments:
            research.append("uv_ageing_not_verified_for_exact_product")
        if "moisture" in environments and task in {"bond_joint", "coat_pcb"}:
            research.append("moisture_durability_not_verified_for_specific_assembly")
        if "vibration" in environments and task == "bond_joint":
            research.append("dynamic_fatigue_validation_required")
        if method["family"] in _CONSUMABLE_CLASSES:
            research.append("current_tds_sds_and_local_regulatory_requirements")
        if method["family"] == "repair_triage":
            research.append("inspect_corrosion_extent_and_repairability_before_chemicals")
        if method["family"] == "nonchemical_alternative":
            research.append("check_replacement_fit_and_source_availability")
        is_nonchemical = method["family"] == "nonchemical_alternative"
        if is_nonchemical and global_blockers:
            # Even a mechanical method cannot be implicitly authorized through
            # the chemical advisor during a safety-critical or battery emergency.
            reasons.extend(global_blockers)
        status = ("blocked" if reasons else
                  "research_required" if method["evidence_level"] in {"broad_product_claim", "general_alternative"}
                  or hold_for_evidence or primary_material == "unknown" else
                  "candidate_for_validation")
        quote = cost_quotes.get(method["id"]) if cost_quotes else None
        results.append({
            "approach_id": method["id"],
            "name": method["label"],
            "kind": method["family"],
            "evidence_specificity": method["evidence_level"],
            "source_claims": [{
                "source_id": sid, "publisher": sources[sid]["publisher"],
                "url": sources[sid]["url"], "scope": sources[sid]["scope"],
                "source_claim": sources[sid]["claim"]
            } for sid in method["source_ids"]],
            "status": status,
            "hard_blockers": sorted(set(reasons)),
            "verification_gaps": sorted(set(research)),
            "conditions_to_research_before_trial": sorted(set(hold_for_evidence)),
            "required_validation": method["validation"],
            "failure_modes": method["failure_modes"],
            "economics": _economics(quote, currency=currency),
            "qualified_for_production": False,
            "chemical_handling_approved": False,
        })
    rank = {"candidate_for_validation":0, "research_required":1, "blocked":2}
    evidence_rank = {key:i for i,key in enumerate(_PROVENANCE)}
    results.sort(key=lambda row: (rank[row["status"]],
                                  evidence_rank[row["evidence_specificity"]], row["approach_id"]))
    candidates = [row["approach_id"] for row in results if row["status"] == "candidate_for_validation"]
    decision = ("stop_and_escalate" if global_blockers else
                "options_for_validation" if candidates else
                "research_or_replace")
    # Hard global hazards override even theoretical local match; options
    # remain visible with BLOCKED status to explain what was excluded.
    return {
        "schema_version": "hardware_splicer.practical_chemistry_assessment.v1",
        "task": task,
        "inputs": {
            "primary_material": primary_material, "material_identity": material_identity,
            "adjacent_materials": neighbors, "electrical_state": electrical_state,
            "battery_status": battery_status, "duty": duty,
            "exposure": environments, "rework_required": rework_required,
            "residue_tolerance": residue_tolerance,
            "keepouts_confirmed": keepouts_confirmed,
            "service_temperature_c": service_temperature_c,
        },
        "catalog_version": evidence["schema_version"],
        "decision": decision,
        "global_blockers": sorted(set(global_blockers)),
        "approaches": results,
        "candidate_approach_ids_for_validation": candidates,
        "selected_method": None,
        "automatic_material_identification": False,
        "manufacturer_claims_independently_verified": False,
        "ready_to_execute_steps": False,
        "chemical_handling_authorized": False,
        "source_revision_check_required": True,
        "acceptance_workflow": _acceptance_workflow(task),
        "independent_repair_validation_required": True,
        "limits": [
            "Evidence is manually indexed manufacturer/repair guidance, not verified compatibility on this specimen.",
            "Specific chemical and physical procedures must be taken from current product TDS/SDS under competent supervision.",
            "No unquoted costs, cure metrics, performance probabilities or material compositions are invented.",
            "Approaches are scoped hypotheses for validation, not instructions to use products or approve repair.",
        ],
        **NON_AUTHORITY,
    }


def _acceptance_workflow(task: str) -> list[dict[str, str]]:
    common = [
        {"phase": "triage", "gate": "Identify materials, power/battery hazards, actual failure mechanism and duty"},
        {"phase": "screen", "gate": "Match specific manufacturer product claim to actual material/grade and adjacent parts"},
        {"phase": "source_verification", "gate": "Read current product TDS/SDS, limitations and current local authorization"},
        {"phase": "coupon_test", "gate": "Independent small-scale representative compatibility test and evidence record"},
    ]
    practical = {
        "clean_flux": "Document post-clean contamination, dryness, seal/coating integrity and electrical retest",
        "clean_contacts": "Measure contact resistance and cycling; check whether a residual film is allowed",
        "bond_joint": "Test representative joint shear/peel, thermal/vibration cycling and likely failure mode",
        "coat_pcb": "Verify keep-out masking, witness coupon, coating coverage, adhesion, cure and electrical checks",
        "finish_surface": "Compare safe alternative finishing; verify dimensions, loss of detail and surface integrity on coupon",
        "assess_corrosion": "Inspect under components, evaluate metal loss and ongoing moisture source before deciding repairability",
    }
    common.extend([
        {"phase": "inspection", "gate": practical[task]},
        {"phase": "decision", "gate": "Compare tested evidence and full failure-path cost with replacement option"},
        {"phase": "release", "gate": "Require independent qualified verification; never auto-approve from HS assessment"},
    ])
    return common


def practical_catalog_summary() -> dict[str, Any]:
    data = catalog()
    return {
        "schema_version": data["schema_version"],
        "source_count": len(data["sources"]),
        "approach_count": len(data["methods"]),
        "task_types": sorted(_TASKS),
        "methods": [{
            "id": entry["id"], "task": entry["task"],
            "name": entry["label"], "family": entry["family"],
            "materials": entry["target_materials"],
            "evidence_level": entry["evidence_level"],
        } for entry in data["methods"]],
        "source_claims_unverified_against_current_revisions": True,
        **NON_AUTHORITY,
    }
