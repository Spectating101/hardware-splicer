"""Explicit, independent acceptance contracts for restoration and recombination.

Only a supervised/canonical physical evidence workflow can eventually prove a
completed hardware mission. This software compiler provides *candidate design*
evidence, never automatically asserts a repaired original or working new product.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA = "hardware_splicer.engineering_mission_contract.v1"
VERDICT_SCHEMA = "hardware_splicer.engineering_mission_evaluation.v1"
TYPES = {"restorative_repair", "novel_splice"}
_FIELDS = {
    "restorative_repair": {"type", "original_device", "original_function", "source_refs"},
    "novel_splice": {"type", "new_product", "required_functions", "source_refs", "minimum_distinct_donors"},
}


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 500:
        raise ValueError(f"{label} must be a nonempty bounded string")
    return value.strip()


def _strings(value: object, label: str, *, minimum: int) -> list[str]:
    if (
        not isinstance(value, list)
        or not minimum <= len(value) <= 32
        or any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in value)
    ):
        raise ValueError(f"{label} requires {minimum}-32 nonempty bounded entries")
    normalized = [v.strip() for v in value]
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{label} contains duplicate entries")
    return normalized


def normalize_engineering_mission(intake: Mapping[str, Any]) -> dict[str, Any] | None:
    """Require explicitly selected mode. A repair_intake alone is NOT a repair mission.

    Reject unknown/authority-looking fields rather than silently accepting claims.
    Source IDs never constitute ownership or test evidence.
    """
    if "engineering_mission" not in intake:
        return None  # Legacy API/demos keep their historical compile-only behavior.
    raw = intake["engineering_mission"]
    if not isinstance(raw, Mapping):
        raise ValueError("engineering_mission must be an object")
    mode = raw.get("type")
    if not isinstance(mode, str) or mode not in TYPES:
        raise ValueError("engineering_mission.type must be restorative_repair or novel_splice")
    extra = set(raw) - _FIELDS[mode]
    if extra:
        raise ValueError(f"unsupported engineering_mission fields: {', '.join(sorted(map(str,extra)))}")
    refs = _strings(raw.get("source_refs"), "source_refs", minimum=1 if mode == "restorative_repair" else 2)
    if mode == "restorative_repair":
        if len(refs) != 1:
            raise ValueError("restorative_repair targets exactly one identified original donor")
        return {
            "schema_version": SCHEMA,
            "type": mode,
            "original_device": _text(raw.get("original_device"), "original_device"),
            "original_function": _text(raw.get("original_function"), "original_function"),
            "source_refs": refs,
            "success_definition": "restore original device functionality with independent observed functional test",
            "source_refs_are_physical_evidence": False,
            "physical_authority_granted": False,
        }
    minimum = raw.get("minimum_distinct_donors", 2)
    if type(minimum) is not int or not 2 <= minimum <= 32:
        raise ValueError("minimum_distinct_donors must be integer 2-32")
    if len(refs) < minimum:
        raise ValueError("minimum_distinct_donors cannot exceed candidate source count")
    return {
        "schema_version": SCHEMA,
        "type": mode,
        "new_product": _text(raw.get("new_product"), "new_product"),
        "required_functions": _strings(raw.get("required_functions"), "required_functions", minimum=2),
        "source_refs": refs,
        "minimum_distinct_donors": minimum,
        "success_definition": "new product meets required functions with verified cross-donor integration and physical end-to-end test",
        "source_refs_are_physical_evidence": False,
        "physical_authority_granted": False,
    }


def evaluate_engineering_mission(
    mission: Mapping[str, Any],
    *,
    build_id: str | None,
    compiler_passed: bool,
    salvage_package: Mapping[str, Any],
) -> dict[str, Any]:
    """Current design path is untrusted for physical mission closure.

    No accepting success boolean based on user-provided evidence, fixture,
    physical-looking part names, a catalog match or a clean KiCad DRC.
    """
    mode = mission["type"]
    splice = salvage_package.get("splice_plan") or {}
    blocks = splice.get("reusable_blocks") or []
    circuit_blocks = [
        b for b in blocks
        if isinstance(b, Mapping) and b.get("source") == "circuit_functional_salvage"
    ]
    reused = len(circuit_blocks)
    if mode == "restorative_repair":
        alignment = "unresolved_original_function"
        gates = [
            "independent specimen identity and safe physical intake",
            "baseline observation of original function and differential fault diagnosis",
            "documented model-compatible repair plan and safe verification steps",
            "authorized repair performed and original function independently retested",
        ]
        # A carrier board that compiles does not demonstrate that the original
        # instrument's barcode reader, display, etc. has been restored.
        goal = {"original_device": mission["original_device"], "original_function": mission["original_function"]}
    else:
        alignment = "proposed_architecture_unverified"
        gates = [
            "independently inspect and identify at least two distinct physical donors",
            "verify exact subsystem functions, pinouts, power limits and geometry per source",
            "prove new architecture covers every required function and integrates the verified donors",
            "validate carrier plus mechanical fabrication, firmware/control and system safety",
            "observe a working new product completing its end-to-end function",
        ]
        goal = {"new_product": mission["new_product"], "required_functions": list(mission["required_functions"])}
    return {
        "schema_version": VERDICT_SCHEMA,
        "type": mode,
        "goal": goal,
        "source_refs": list(mission["source_refs"]),
        "compile": {
            "generated_build_id": build_id,
            "carrier_compile_passed": bool(compiler_passed),
            "circuit_backed_fixture_or_candidate_blocks": reused,
            "circuit_backed_blocks_prove_physical_function": False,
        },
        "design_alignment_status": alignment,
        "verified_physical_donor_count_from_this_execution": 0,
        "verified_interface_count_from_this_execution": 0,
        "original_device_function_restored": False if mode == "restorative_repair" else None,
        "new_product_functionally_tested": False if mode == "novel_splice" else None,
        "mission_success": False,
        "verdict": "BLOCKED_ON_INDEPENDENT_PHYSICAL_AND_FUNCTIONAL_EVIDENCE",
        "open_acceptance_gates": gates,
        "human_operator_physical_authority_granted": False,
        "reason": "Software compilation and seller/operator descriptions do not close physical mission acceptance.",
    }


def repair_investigation_plan(
    mission: Mapping[str, Any],
    repair_intake: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Document what to investigate; don't invent a repair or power sequence.

    The available source may be only a marketplace listing. No generic
    substitute product is an answer to an original-function repair request.
    """
    if mission.get("type") != "restorative_repair":
        raise ValueError("repair plan only valid for original-function repair mission")
    notes = repair_intake if isinstance(repair_intake, Mapping) else {}
    from .engineering_repair_differential import repair_differential
    differential = repair_differential(mission, notes)
    symptoms = notes.get("symptoms") or []
    if isinstance(symptoms, str):
        symptoms = [symptoms]
    if not isinstance(symptoms, list):
        symptoms = []
    return {
        "schema_version": "hardware_splicer.restorative_repair_investigation.v1",
        "mission_type": "restorative_repair",
        "original_device": mission["original_device"],
        "original_function": mission["original_function"],
        "source_refs": list(mission["source_refs"]),
        "seller_or_operator_reported_symptoms_unverified": [
            str(s) for s in symptoms[:32] if isinstance(s, str)
        ],
        "candidate_fault_root_cause": None,
        "repair_instructions_validated": False,
        "differential_diagnosis": differential,
        "diagnosis_status": "BLOCKED_AWAITING_ORIGINAL_DEVICE_EVIDENCE",
        "next_evidence_requests": [
            "Confirm possession, ownership/permission and exact physical specimen identity.",
            "Document original equipment model/revision and the actual connector/port/cable variant.",
            "Record baseline failure symptoms with dated photos and supervised observation.",
            "Consult exact-model manufacturer service/connector documentation; do not guess pinout.",
            "Have a qualified operator perform suitable safe inspection and unpowered continuity/short checks.",
            "Resolve at least one evidence-backed fault hypothesis against alternatives.",
            "Only after verified safety and electrical contracts, draft a model-compatible repair procedure.",
            "After operator-performed approved repair, record restoration of the ORIGINAL function.",
        ],
        "may_authorize_power_or_fabrication": False,
        "original_function_verified": False,
        "generic_new_product_substitution_allowed": False,
    }
