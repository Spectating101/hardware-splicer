"""Fail-closed downstream projections for model-first salvage.

This module deliberately does less than the historical salvage helpers.  Its job is to
stop an unresolved physical identity or capability from being laundered into guessed
shopping SKUs, GPIO templates, firmware, or mechanical geometry.  It does not select
components and it does not infer architecture from prose.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence


GAP_SCHEMA = "hardware_splicer.salvage_gap_analysis.v1"
FIRMWARE_SCHEMA = "hardware_splicer.firmware_scaffold.v1"
MECHANISM_SCHEMA = "hardware_splicer.mechanism_pack.v1"
BRINGUP_SCHEMA = "hardware_splicer.bringup_card.v1"

_TRUSTED_STATUSES = {"declared", "model_proposed", "proposed_design_component"}
_TRUSTED_SOURCES = {
    "declared_catalog_identity",
    "model_identity_proposed",
    "donor_functional_salvage_declared",
    "workshop_design_proposal",
}


def _rows(value: Any) -> list[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def trusted_module_ids(resolved_modules: Sequence[Mapping[str, Any]]) -> list[str]:
    trusted: list[str] = []
    seen: set[str] = set()
    for row in resolved_modules:
        module_id = str(row.get("module_id") or "").strip()
        if not module_id:
            continue
        if str(row.get("identity_status") or "") not in _TRUSTED_STATUSES:
            continue
        if str(row.get("source") or "") not in _TRUSTED_SOURCES:
            continue
        if module_id not in seen:
            seen.add(module_id)
            trusted.append(module_id)
    return trusted


def unresolved_identity_rows(resolved_modules: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    blockers: list[Dict[str, Any]] = []
    for index, row in enumerate(resolved_modules):
        source = str(row.get("source") or "").strip()
        status = str(row.get("identity_status") or "").strip()
        module_id = str(row.get("module_id") or "").strip()
        external = row.get("external_capability_only") is True
        unresolved = (
            source in {"unresolved_identity", "unresolved_capability_gap"}
            or status in {"unresolved", "external_unresolved"}
            or external
            or not module_id
        )
        if not unresolved:
            continue
        blockers.append(
            {
                "row_index": index,
                "instance_id": row.get("instance_id") or row.get("donor_block_id"),
                "role": row.get("role"),
                "source": source or None,
                "identity_status": status or None,
                "external_capability_only": external,
                "capabilities": list(row.get("capabilities") or []),
                "question": _identity_question(row),
            }
        )
    return blockers


def _identity_question(row: Mapping[str, Any]) -> str:
    role = str(row.get("role") or "component").strip() or "component"
    instance = str(row.get("instance_id") or row.get("donor_block_id") or role).strip()
    if row.get("external_capability_only") is True:
        return f"Verify the physical identity/pinout for donor capability {instance} ({role}) before projecting firmware or geometry."
    if str(row.get("source") or "") == "unresolved_capability_gap":
        return f"Resolve the missing {role} capability with evidence or an explicit design proposal before downstream projection."
    return f"Resolve physical identity for {instance} ({role}) before downstream projection."


def build_model_first_gap_analysis(
    *,
    resolved_modules: Sequence[Mapping[str, Any]],
    power_topology: str | None,
) -> Dict[str, Any]:
    """Describe only evidence-backed coverage and unresolved capability/identity gaps."""
    trusted = trusted_module_ids(resolved_modules)
    blockers = unresolved_identity_rows(resolved_modules)
    covered = []
    for row in resolved_modules:
        module_id = str(row.get("module_id") or "").strip()
        if module_id not in trusted:
            continue
        covered.append(
            {
                "module_id": module_id,
                "role": row.get("role"),
                "source": row.get("source"),
                "identity_status": row.get("identity_status"),
            }
        )
    return {
        "schema_version": GAP_SCHEMA,
        "mode": "model_first_structured",
        "power_topology": power_topology,
        "inventory_module_ids": trusted,
        "goal_module_ids": [],
        "covered": covered,
        "auto_filled": [],
        "shopping_list": [],
        "still_missing": blockers,
        "unresolved_questions": [row["question"] for row in blockers],
        "ready_to_compile": bool(trusted) and not blockers,
        "summary": (
            "Structured identity/capability blockers remain; no concrete replacement SKU was guessed."
            if blockers
            else "All downstream module identities are evidence-backed; no prose-derived shopping projection was run."
        ),
        "semantic_goal_routing_used": False,
        "concrete_gap_substitution_used": False,
        "authority_effect": "none",
    }


def build_model_first_bringup_card(
    *,
    goal: str,
    resolved_modules: Sequence[Mapping[str, Any]],
    power_topology: str | None,
) -> Dict[str, Any]:
    """Emit a question-oriented bring-up card without auto-wiring or guessed pins."""
    trusted = trusted_module_ids(resolved_modules)
    blockers = unresolved_identity_rows(resolved_modules)
    donor_refs: list[Dict[str, Any]] = []
    for row in resolved_modules:
        refs = [str(ref) for ref in (row.get("connector_refs") or []) if str(ref).strip()]
        if not refs:
            continue
        donor_refs.append(
            {
                "instance_id": row.get("instance_id") or row.get("donor_block_id"),
                "connector_refs": refs,
                "instruction": "Preserve connector and verify pinout/voltage before cutting or energizing.",
            }
        )
    questions = [row["question"] for row in blockers]
    if not questions:
        questions.append("Compile an evidence-backed graph before generating hookup GPIO assignments.")
    return {
        "schema_version": BRINGUP_SCHEMA,
        "mode": "model_first_evidence_only",
        "goal": goal,
        "power_topology": power_topology,
        "module_ids": trusted,
        "connections": [],
        "gpio_assignments": [],
        "bench_checks": [
            "Keep power/motion authority closed until pinout, voltage, polarity and common-ground evidence are verified."
        ],
        "warnings": ["Automatic wiring is disabled on the unresolved model-first salvage boundary."],
        "unresolved_questions": questions,
        "donor_harness": donor_refs,
        "sourced_from_graph": False,
        "auto_wire_used": False,
        "authority_effect": "none",
    }


def build_model_first_firmware_scaffold(
    *,
    build_id: str | None,
    resolved_modules: Sequence[Mapping[str, Any]],
    bringup_card: Mapping[str, Any],
) -> Dict[str, Any]:
    """Block firmware templates until identity and pin evidence are explicit."""
    trusted = trusted_module_ids(resolved_modules)
    blockers = unresolved_identity_rows(resolved_modules)
    questions = [row["question"] for row in blockers]
    if not str(build_id or "").strip():
        questions.append("Resolve or explicitly declare the bounded build architecture before selecting a firmware template.")
    if not list(bringup_card.get("gpio_assignments") or []):
        questions.append("Provide graph/pin evidence before generating executable GPIO assignments.")
    return {
        "schema_version": FIRMWARE_SCHEMA,
        "status": "blocked_evidence_required",
        "build_id": str(build_id or "").strip() or None,
        "mcu_family": None,
        "filename": None,
        "modules": trusted,
        "pins": {},
        "source": "",
        "generator": "none_model_first_evidence_gate",
        "unresolved_questions": list(dict.fromkeys(questions)),
        "claim_boundary": "No firmware template generated until physical identity and pin evidence are explicit.",
        "firmware_flash_authorized": False,
        "authority_effect": "none",
    }


def build_model_first_mechanism_pack(
    *,
    resolved_modules: Sequence[Mapping[str, Any]],
    constraints: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Block geometry inference unless the caller supplied explicit physical constraints."""
    constraints_map = dict(constraints or {})
    blockers = unresolved_identity_rows(resolved_modules)
    required = {
        "mechanism_kind": constraints_map.get("mechanism_kind"),
        "pcb_w_mm": constraints_map.get("pcb_w_mm"),
        "pcb_h_mm": constraints_map.get("pcb_h_mm"),
    }
    missing = [key for key, value in required.items() if value in (None, "")]
    questions = [row["question"] for row in blockers]
    if missing:
        questions.append(
            "Declare physical mechanism constraints before geometry projection: " + ", ".join(missing) + "."
        )
    return {
        "schema_version": MECHANISM_SCHEMA,
        "status": "blocked_evidence_required",
        "kind": constraints_map.get("mechanism_kind") if not missing and not blockers else None,
        "project_spec": {},
        "outputs": [],
        "parts": [],
        "bundle_dir": None,
        "unresolved_questions": questions,
        "claim_boundary": "No mechanical geometry generated from goal labels or representative part defaults.",
        "degraded_reason": "physical_identity_or_geometry_evidence_unresolved" if blockers or missing else None,
        "motion_authorized": False,
        "authority_effect": "none",
    }
