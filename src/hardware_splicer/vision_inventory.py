"""Merge vision-identified parts into intake inventory."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from .module_resolver import resolve_parts_to_modules

SCHEMA_VERSION = "hardware_splicer.vision_inventory.v1"


def _list_dicts(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _normalize_part_name(text: str) -> Dict[str, Any]:
    return {"name": text.strip(), "type": "part", "source": "vision"}


def extract_parts_from_vision_report(report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Collect parts from vision JSON (identified_parts) and observation heuristics."""
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add_part(row: Mapping[str, Any]) -> None:
        name = str(row.get("name") or row.get("label") or "").strip()
        if not name:
            return
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(
            {
                "name": name,
                "type": str(row.get("type") or row.get("category") or "part"),
                "source": str(row.get("source") or "vision"),
                "confidence": row.get("confidence"),
            }
        )

    for candidate in _list_dicts(report.get("candidates")):
        for row in _list_dicts(candidate.get("identified_parts")):
            add_part(row)

    observations: List[str] = []
    for candidate in _list_dicts(report.get("candidates")):
        for obs in candidate.get("observations") or []:
            observations.append(str(obs))

    heuristic_parts = _heuristic_parts_from_text(" ".join(observations))
    for name in heuristic_parts:
        add_part(_normalize_part_name(name))

    # Resolve to modules where possible for downstream hints
    if out:
        resolved = resolve_parts_to_modules(out)
        for index, row in enumerate(out):
            if index < len(resolved) and resolved[index].get("module_id"):
                out[index]["suggested_module_id"] = resolved[index]["module_id"]
                out[index]["resolve_confidence"] = resolved[index].get("confidence")
    return out


def _heuristic_parts_from_text(text: str) -> List[str]:
    if not text.strip():
        return []
    patterns = [
        r"esp32[\w-]*",
        r"arduino\s*nano",
        r"raspberry\s*pi\s*pico",
        r"soil\s*moisture[\w\s]*sensor",
        r"dht\d+",
        r"bme280",
        r"water\s*pump",
        r"mini\s*pump",
        r"mosfet[\w\s]*",
        r"l298n",
        r"relay\s*module",
        r"usb\s*power\s*bank",
        r"buck[\w\s]*converter",
        r"oled|ssd1306",
        r"ultrasonic|hc-?sr04",
    ]
    found: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            label = match.group(0).strip()
            if label and label.lower() not in {f.lower() for f in found}:
                found.append(label)
    return found


def extract_parts_from_attachments(intake: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Offline inventory hints from attachment filenames, labels, and optional OCR."""
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def add_name(name: str, *, source: str, confidence: float = 0.55) -> None:
        text = str(name or "").strip()
        if not text:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        out.append({"name": text, "type": "part", "source": source, "confidence": confidence})

    for attachment in _list_dicts(intake.get("attachments")):
        for field in ("label", "title", "description", "caption", "alt"):
            add_name(str(attachment.get(field) or ""), source="attachment_meta", confidence=0.6)
        path = str(attachment.get("path") or attachment.get("file") or "")
        if path:
            stem = Path(path).stem.replace("_", " ").replace("-", " ")
            add_name(stem, source="attachment_filename", confidence=0.5)
        notes = attachment.get("identified_parts") or attachment.get("parts")
        if isinstance(notes, list):
            for row in notes:
                if isinstance(row, Mapping):
                    add_name(str(row.get("name") or ""), source="attachment_parts", confidence=0.85)
                else:
                    add_name(str(row), source="attachment_parts", confidence=0.85)

    ocr_parts = _ocr_attachment_text(intake)
    for name in ocr_parts:
        add_name(name, source="attachment_ocr", confidence=0.65)

    if out:
        resolved = resolve_parts_to_modules(out)
        for index, row in enumerate(out):
            if index < len(resolved) and resolved[index].get("module_id"):
                out[index]["suggested_module_id"] = resolved[index]["module_id"]
                out[index]["resolve_confidence"] = resolved[index].get("confidence")
    return out


def _ocr_attachment_text(intake: Mapping[str, Any]) -> List[str]:
    if os.getenv("HARDWARE_SPLICER_OFFLINE_OCR", "1").strip().lower() in {"0", "false", "no", "off"}:
        return []
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
    except ImportError:
        return []

    texts: List[str] = []
    for attachment in _list_dicts(intake.get("attachments")):
        path = str(attachment.get("path") or "")
        if not path or not Path(path).is_file():
            continue
        if Path(path).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
            continue
        try:
            texts.append(pytesseract.image_to_string(Image.open(path)))
        except OSError:
            continue
    return _heuristic_parts_from_text(" ".join(texts))


def merge_attachment_inventory_into_intake(intake: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Offline path: filename/meta/OCR → available_parts (no vision API)."""
    body = dict(intake)
    extracted = extract_parts_from_attachments(body)
    report = {
        "schema_version": SCHEMA_VERSION,
        "mode": "offline_attachments",
        "identified_parts": extracted,
        "merged_count": 0,
        "ocr_enabled": os.getenv("HARDWARE_SPLICER_OFFLINE_OCR", "1").strip().lower() not in {"0", "false", "no", "off"},
    }
    if not extracted:
        return body, report

    existing = _list_dicts(body.get("available_parts") or body.get("parts") or [])
    names = {str(row.get("name") or "").strip().lower() for row in existing}
    merged = list(existing)
    for row in extracted:
        name = str(row.get("name") or "").strip()
        if not name or name.lower() in names:
            continue
        names.add(name.lower())
        merged.append(dict(row))
        report["merged_count"] = int(report["merged_count"]) + 1

    if report["merged_count"]:
        body["available_parts"] = merged
        body["parts"] = merged
        body["offline_merged_parts"] = extracted
    return body, report


def merge_vision_inventory_into_intake(
    intake: Mapping[str, Any],
    vision_report: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    body = dict(intake)
    extracted = extract_parts_from_vision_report(vision_report)
    inventory_report = {
        "schema_version": SCHEMA_VERSION,
        "identified_parts": extracted,
        "merged_count": 0,
    }
    if not extracted:
        return body, inventory_report

    existing = _list_dicts(body.get("available_parts") or body.get("parts") or [])
    names = {str(row.get("name") or "").strip().lower() for row in existing}
    merged = list(existing)
    for row in extracted:
        name = str(row.get("name") or "").strip()
        if not name or name.lower() in names:
            continue
        names.add(name.lower())
        merged.append(dict(row))
        inventory_report["merged_count"] = int(inventory_report["merged_count"]) + 1

    if inventory_report["merged_count"]:
        body["available_parts"] = merged
        body["parts"] = merged
        body["vision_merged_parts"] = extracted
    return body, inventory_report
