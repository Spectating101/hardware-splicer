"""Resolve OCR markings into likely electronic parts and pinout evidence."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from src.intelligence.component_datasheet_retriever import datasheet_retriever
from src.intelligence.pinout_database import ICPinout, pinout_database


PART_TOKEN_RE = re.compile(r"\b[A-Z]{1,4}[A-Z0-9]{2,}[A-Z0-9\-_.]*\b", re.IGNORECASE)
SILK_LABEL_RE = re.compile(
    r"\b(?:VIN|VCC|VDD|3V3|5V|12V|24V|GND|TX|RX|SDA|SCL|MISO|MOSI|SCK|RST|RESET|EN|IO\d+|GPIO\d+|MOTOR|OUT\d*|IN\d*)\b",
    re.IGNORECASE,
)


class MarkingResolver:
    """Turn noisy OCR text into likely components, pinouts, and connector labels."""

    def __init__(self, extracted_pinout_dir: str = "data/extracted_pinouts"):
        self.extracted_pinout_dir = Path(extracted_pinout_dir)
        self._extracted_index = self._load_extracted_index()

    def resolve_detections(self, detections: Iterable[Any]) -> Dict[str, Any]:
        resolved = []
        all_labels = []
        for index, detection in enumerate(detections or []):
            record = self._detection_record(detection, index)
            text = record.get("text", "")
            tokens = self.extract_part_tokens(text)
            labels = self.extract_silk_labels(text)
            all_labels.extend(labels)
            candidates = [self.resolve_token(token) for token in tokens]
            candidates = [candidate for candidate in candidates if candidate]
            if candidates or labels:
                resolved.append(
                    {
                        "component_id": record["id"],
                        "class_name": record["class_name"],
                        "bbox": record.get("bbox", []),
                        "text": text,
                        "part_tokens": tokens,
                        "silk_labels": labels,
                        "candidates": candidates[:5],
                    }
                )

        return {
            "mode": "ocr_marking_resolution",
            "components": resolved,
            "connector_labels": sorted(set(all_labels)),
            "confidence": self._confidence(resolved),
            "limitations": [
                "OCR markings are noisy and should be verified against the photo",
                "short top-mark codes may map to multiple parts",
                "datasheet/pinout matches are evidence, not proof, until package and circuit context agree",
            ],
        }

    def extract_part_tokens(self, text: str) -> List[str]:
        tokens = []
        for raw in PART_TOKEN_RE.findall(text or ""):
            token = raw.strip("._-").upper()
            if len(token) < 3:
                continue
            if token in {"VIN", "VCC", "VDD", "GND", "SDA", "SCL", "RST", "RESET"}:
                continue
            if token not in tokens:
                tokens.append(token)
        return tokens[:12]

    def extract_silk_labels(self, text: str) -> List[str]:
        labels = []
        for raw in SILK_LABEL_RE.findall(text or ""):
            label = raw.upper()
            if label not in labels:
                labels.append(label)
        return labels[:20]

    def resolve_token(self, token: str) -> Dict[str, Any] | None:
        normalized = token.upper().replace("-", "").replace("_", "")
        pinout = pinout_database.get_pinout(normalized) or pinout_database.search_by_component_name(normalized)
        datasheet = self._datasheet_info(normalized)
        extracted = self._match_extracted_pinout(normalized)
        if not pinout and not datasheet and not extracted:
            return {
                "part_number": token.upper(),
                "confidence": 0.18,
                "match_type": "unresolved_marking",
                "next_steps": ["search datasheet", "verify package", "capture sharper crop"],
            }

        payload: Dict[str, Any] = {
            "part_number": self._canonical_part(token, pinout, datasheet, extracted),
            "confidence": 0.72 if pinout or datasheet else 0.48,
            "match_type": "known_pinout_or_datasheet" if pinout or datasheet else "extracted_pinout",
        }
        if datasheet:
            payload["datasheet"] = {
                "manufacturer": datasheet.manufacturer,
                "url": datasheet.datasheet_url,
                "key_specs": datasheet.key_specs or {},
                "common_issues": datasheet.common_issues or [],
                "replacement_parts": datasheet.replacement_parts or [],
            }
        if pinout:
            payload["pinout"] = self._serialize_pinout(pinout)
        elif extracted:
            payload["pinout"] = extracted
        return payload

    def _load_extracted_index(self) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}
        if not self.extracted_pinout_dir.exists():
            return index
        for path in self.extracted_pinout_dir.glob("*_pinout.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            name = str(data.get("ic_name") or path.stem.replace("_pinout", "")).upper()
            index[name.replace("-", "").replace("_", "")] = {
                "part_number": name,
                "pin_count": data.get("total_pins", len(data.get("pins") or [])),
                "pins": (data.get("pins") or [])[:40],
                "source": str(path),
            }
        return index

    def _match_extracted_pinout(self, normalized: str) -> Dict[str, Any] | None:
        for key, data in self._extracted_index.items():
            if key in normalized or normalized in key:
                return data
        return None

    def _datasheet_info(self, normalized: str) -> Any:
        if normalized in datasheet_retriever.metadata:
            return datasheet_retriever.metadata[normalized]
        if normalized in datasheet_retriever.known_datasheets:
            return datasheet_retriever.known_datasheets[normalized]
        for known_part, info in datasheet_retriever.known_datasheets.items():
            key = known_part.upper().replace("-", "").replace("_", "")
            if key in normalized or normalized in key:
                return info
        return None

    def _canonical_part(self, token: str, pinout: ICPinout | None, datasheet: Any, extracted: Dict[str, Any] | None) -> str:
        if pinout:
            return pinout.part_number
        if datasheet:
            return datasheet.part_number
        if extracted:
            return str(extracted.get("part_number") or token.upper())
        return token.upper()

    def _serialize_pinout(self, pinout: ICPinout) -> Dict[str, Any]:
        power_pins = [pin for pin in pinout.pins if pin.pin_type.value in {"power", "ground"}]
        programming_pins = [pin for pin in pinout.pins if pin.pin_type.value in {"programming", "reset", "clock"}]
        io_pins = [pin for pin in pinout.pins if pin.pin_type.value in {"input", "output", "bidirectional", "analog"}]
        return {
            "part_number": pinout.part_number,
            "manufacturer": pinout.manufacturer,
            "description": pinout.description,
            "package": pinout.package.value,
            "pin_count": pinout.pin_count,
            "datasheet_url": pinout.datasheet_url,
            "notes": pinout.notes,
            "power_pins": [_pin_type_safe(asdict(pin)) for pin in power_pins[:12]],
            "programming_or_clock_pins": [_pin_type_safe(asdict(pin)) for pin in programming_pins[:12]],
            "io_pins_sample": [_pin_type_safe(asdict(pin)) for pin in io_pins[:16]],
        }

    def _detection_record(self, detection: Any, index: int) -> Dict[str, Any]:
        if isinstance(detection, dict):
            class_name = str(detection.get("class_name") or detection.get("label") or "component")
            text = detection.get("ocr_text") or detection.get("text_content") or detection.get("text") or detection.get("part_number") or ""
            bbox = detection.get("bbox") or []
        else:
            class_name = str(getattr(detection, "class_name", "component"))
            text = getattr(detection, "ocr_text", "") or getattr(detection, "text_content", "") or getattr(detection, "part_number", "")
            bbox = getattr(detection, "bbox", []) or []
        return {
            "id": f"cmp_{index}_{class_name.lower().replace(' ', '_')}",
            "class_name": class_name,
            "text": str(text or ""),
            "bbox": bbox,
        }

    def _confidence(self, resolved: List[Dict[str, Any]]) -> float:
        if not resolved:
            return 0.0
        scores = []
        for item in resolved:
            candidates = item.get("candidates") or []
            if candidates:
                scores.append(max(float(candidate.get("confidence", 0.0) or 0.0) for candidate in candidates))
            elif item.get("silk_labels"):
                scores.append(0.35)
        return round(sum(scores) / len(scores), 3) if scores else 0.0


def _pin_type_safe(payload: Dict[str, Any]) -> Dict[str, Any]:
    value = dict(payload)
    pin_type = value.get("pin_type")
    if hasattr(pin_type, "value"):
        value["pin_type"] = pin_type.value
    return value
