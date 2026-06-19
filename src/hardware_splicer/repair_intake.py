"""Repair-café style intake fields — symptoms, when-it-fails, device context."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping

SCHEMA_VERSION = "hardware_splicer.repair_intake.v1"


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.replace(";", "\n").splitlines() if part.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def extract_repair_context(intake: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize repair_intake block from a PROJECT_INTAKE payload."""
    repair = intake.get("repair_intake") if isinstance(intake.get("repair_intake"), dict) else {}
    legacy_symptoms = _string_list(intake.get("symptoms"))
    return {
        "schema_version": SCHEMA_VERSION,
        "symptoms": _dedupe(_string_list(repair.get("symptoms")) or legacy_symptoms),
        "when_it_fails": str(repair.get("when_it_fails") or repair.get("when_it_happens") or "").strip(),
        "device_hint": str(repair.get("device_hint") or repair.get("device") or "").strip(),
        "repro_steps": _string_list(repair.get("repro_steps") or repair.get("reproduction_steps")),
        "operator_notes": str(repair.get("operator_notes") or repair.get("notes") or "").strip(),
    }


def _dedupe(items: List[str]) -> List[str]:
    kept: List[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept


def apply_repair_intake_context(intake: Mapping[str, Any]) -> Dict[str, Any]:
    """Merge repair-café fields into intake evidence and vision hints."""
    body: Dict[str, Any] = dict(intake)
    ctx = extract_repair_context(body)
    if not any([ctx["symptoms"], ctx["when_it_fails"], ctx["device_hint"], ctx["repro_steps"], ctx["operator_notes"]]):
        return body

    notes = list(body.get("evidence_notes") or [])
    for symptom in ctx["symptoms"]:
        line = f"symptom: {symptom}"
        if line not in notes:
            notes.append(line)
    if ctx["when_it_fails"]:
        line = f"when_it_fails: {ctx['when_it_fails']}"
        if line not in notes:
            notes.append(line)
    for step in ctx["repro_steps"]:
        line = f"repro: {step}"
        if line not in notes:
            notes.append(line)
    if ctx["operator_notes"]:
        line = f"operator_note: {ctx['operator_notes']}"
        if line not in notes:
            notes.append(line)
    body["evidence_notes"] = notes

    donor_vision = dict(body.get("donor_board_vision") or {})
    if ctx["device_hint"] and not str(donor_vision.get("device_hint") or "").strip():
        donor_vision["device_hint"] = ctx["device_hint"]
    if ctx["symptoms"] and not donor_vision.get("symptoms"):
        donor_vision["symptoms"] = list(ctx["symptoms"])
    body["donor_board_vision"] = donor_vision

    circuit = dict(body.get("circuit") or {})
    boards = [dict(row) for row in (circuit.get("boards") or []) if isinstance(row, dict)]
    for board in boards:
        vision_source = dict(board.get("vision_source") or {})
        if ctx["device_hint"] and not str(vision_source.get("device_hint") or "").strip():
            vision_source["device_hint"] = ctx["device_hint"]
        if ctx["symptoms"] and not vision_source.get("symptoms"):
            vision_source["symptoms"] = list(ctx["symptoms"])
        if vision_source:
            board["vision_source"] = vision_source
    if boards:
        circuit["boards"] = boards
        body["circuit"] = circuit

    body["repair_intake_context"] = ctx
    return body


def repair_intake_report(intake: Mapping[str, Any]) -> Dict[str, Any]:
    """Standalone report for agents inspecting repair context."""
    ctx = extract_repair_context(intake)
    return {**ctx, "applied": bool(ctx["symptoms"] or ctx["when_it_fails"] or ctx["device_hint"])}
