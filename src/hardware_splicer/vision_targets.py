from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Mapping


PLANT_WATERING_PRIMITIVES = [
    "controller_case inner width",
    "pump_mount width",
    "tube strain relief",
    "controller_case cable clearance",
    "pump_mount tube bend clearance",
    "pump_mount printed fit",
    "pump retained under tubing pull",
    "tube routing during pump vibration",
    "pump first run",
    "dry-run timeout stops pump",
    "pump startup current below 1.1A limit",
    "five short watering cycles",
]

ARCHETYPE_PRIMITIVES: Dict[str, List[str]] = {
    "automatic_watering": PLANT_WATERING_PRIMITIVES,
    "automatic_plant_watering": PLANT_WATERING_PRIMITIVES,
}

TARGET_ALIASES: Dict[str, str] = {
    "pump mount": "pump_mount width",
    "pump_mount": "pump_mount width",
    "pump mount width": "pump_mount width",
    "controller case": "controller_case inner width",
    "controller_case": "controller_case inner width",
    "controller case inner width": "controller_case inner width",
    "inner width": "controller_case inner width",
    "tube strain": "tube strain relief",
    "strain relief": "tube strain relief",
    "desk plant water ring bench photo": "pump_mount width",
    "bench photo": "pump_mount width",
}


def vision_primitive_glossary(body: Mapping[str, Any]) -> List[str]:
    archetype = str(body.get("archetype") or _infer_archetype(body) or "").strip().lower()
    for key, values in ARCHETYPE_PRIMITIVES.items():
        if key in archetype or archetype in key:
            return list(values)
    goal = str(body.get("goal") or body.get("intent") or "").lower()
    if "water" in goal or "plant" in goal:
        return list(PLANT_WATERING_PRIMITIVES)
    return []


def normalize_vision_evidence_notes(notes: Iterable[str], body: Mapping[str, Any] | None = None) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in notes:
        note = str(raw or "").strip()
        if not note:
            continue
        note = _normalize_note_targets(note, body or {})
        if note in seen:
            continue
        seen.add(note)
        out.append(note)
    return out


def _normalize_note_targets(note: str, body: Mapping[str, Any]) -> str:
    lowered = note.lower()
    for fragment, canonical in TARGET_ALIASES.items():
        if fragment in lowered:
            return _retarget_note(note, canonical)
    glossary = vision_primitive_glossary(body)
    for target in glossary:
        token = target.split()[0]
        if token and token in lowered:
            return _retarget_note(note, target)
    return note


def _retarget_note(note: str, target: str) -> str:
    if note.startswith("measure:"):
        value = _extract_number(note, "value_mm")
        artifact = _extract_token(note, "artifact")
        suffix = f" value_mm={value}" if value is not None else ""
        artifact_suffix = f" artifact={artifact}" if artifact else ""
        status = _extract_token(note, "status") or "observed"
        return f"measure: {target}{suffix} status={status}{artifact_suffix}".strip()
    if note.startswith("clearance:"):
        value = _extract_number(note, "clearance_mm")
        artifact = _extract_token(note, "artifact")
        suffix = f" clearance_mm={value}" if value is not None else ""
        artifact_suffix = f" artifact={artifact}" if artifact else ""
        status = _extract_token(note, "status") or "observed"
        return f"clearance: {target}{suffix} status={status}{artifact_suffix}".strip()
    for prefix in ("mechanical_bench:", "robotics_bench:", "integrated_bench:"):
        if note.startswith(prefix):
            artifact = _extract_token(note, "artifact")
            status = _extract_token(note, "status") or "observed"
            artifact_suffix = f" artifact={artifact}" if artifact else ""
            return f"{prefix} {target} status={status}{artifact_suffix}".strip()
    return note


def _extract_number(note: str, key: str) -> float | None:
    match = re.search(rf"{re.escape(key)}=([0-9]+(?:\.[0-9]+)?)", note)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _extract_token(note: str, key: str) -> str:
    match = re.search(rf"{re.escape(key)}=([^\s]+)", note)
    return match.group(1).strip() if match else ""


def _infer_archetype(body: Mapping[str, Any]) -> str:
    goal = str(body.get("goal") or body.get("intent") or "").lower()
    if "water" in goal or "plant" in goal:
        return "automatic_watering"
    return ""
