"""Shared PCB component class naming helpers."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


PCB_COMPONENT_CLASS_NAMES = (
    "battery",
    "button",
    "buzzer",
    "capacitor",
    "crystal",
    "connector",
    "diode",
    "display",
    "fuse",
    "heatsink",
    "ic_chip",
    "inductor",
    "led",
    "pads",
    "pins",
    "potentiometer",
    "relay",
    "resistor",
    "switch",
    "transducer",
    "transformer",
    "transistor",
)


COMPONENT_CLASS_ALIASES = {
    "cap1": "capacitor",
    "cap2": "capacitor",
    "cap3": "capacitor",
    "cap4": "capacitor",
    "clock": "crystal",
    "ic": "ic_chip",
    "integrated_circuit": "ic_chip",
    "mosfet": "transistor",
    "mov": "varistor",
    "resestor": "resistor",
}


def normalize_component_class_name(class_name: str | None) -> str:
    """Return the internal component taxonomy name for a model label."""
    if not class_name:
        return "unknown"
    normalized = str(class_name).strip().lower().replace(" ", "_").replace("-", "_")
    return COMPONENT_CLASS_ALIASES.get(normalized, normalized)


def model_class_name(
    model: Any,
    class_id: int,
    fallback_classes: Sequence[str] | None = None,
) -> tuple[str, str]:
    """Resolve a YOLO class id to ``(canonical_name, raw_name)``."""
    names = getattr(model, "names", None)
    raw_name: str
    if isinstance(names, Mapping):
        raw_name = str(names.get(class_id, "unknown"))
    elif isinstance(names, Sequence) and not isinstance(names, (str, bytes)) and class_id < len(names):
        raw_name = str(names[class_id])
    elif fallback_classes and class_id < len(fallback_classes):
        raw_name = str(fallback_classes[class_id])
    else:
        raw_name = "unknown"
    return normalize_component_class_name(raw_name), raw_name
