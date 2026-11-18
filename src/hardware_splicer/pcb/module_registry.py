"""Module registry: loads engine_pcb_data.json and exposes lookup helpers
that mirror the TypeScript module-library + module-footprints functions."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "engine_pcb_data.json"

# ---------------------------------------------------------------------------
# Types (plain dicts, matching TS ModuleSpec / ModulePadDef shapes)
# ---------------------------------------------------------------------------
# ModuleSpec  -> {"id", "label", "category", "pins": [{"id","label","role","voltage",...}], ...}
# ModulePadDef -> {"pinId", "x", "y"}

_P = 2.54  # standard pitch mm

# ---------------------------------------------------------------------------
# Footprint table: one data file shared with the TypeScript side
# ---------------------------------------------------------------------------
#
# Module footprint geometry lives in data/module_footprints.json. The TypeScript module
# library consumes a file generated from it (scripts/export_module_footprints_ts.py), and
# tests/test_module_footprint_parity.py fails if the two ever resolve different pads.

_FOOTPRINTS_PATH = Path(__file__).parent.parent / "data" / "module_footprints.json"


def _dual_col(
    left: list[str], right: list[str], x_span: float = _P * 4
) -> list[dict]:
    """Synthetic two-column placeholder used when a module has no registered footprint."""
    rows = max(len(left), len(right))
    y0 = -((rows - 1) * _P) / 2
    x_l = -x_span / 2
    x_r = x_span / 2
    pads: list[dict] = []
    for i, pin_id in enumerate(left):
        pads.append({"pinId": pin_id, "x": x_l, "y": y0 + i * _P})
    for i, pin_id in enumerate(right):
        pads.append({"pinId": pin_id, "x": x_r, "y": y0 + i * _P})
    return pads


def _load_footprints() -> dict[str, dict]:
    with open(_FOOTPRINTS_PATH, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return dict(payload.get("modules") or {})


_MODULE_FOOTPRINTS: dict[str, dict] = _load_footprints()

# ---------------------------------------------------------------------------
# Module library cache (loaded from engine_pcb_data.json)
# ---------------------------------------------------------------------------

_MODULE_LIBRARY: Optional[dict[str, dict]] = None

_MODULE_ALIASES: dict[str, str] = {
    "mini-pump-5v": "water_pump_5v",
}


def _build_library(modules: list[dict], footprints: dict[str, dict]) -> dict[str, dict]:
    """Build independent specs without mutating source modules or depending on table order."""
    lib = {m["id"]: deepcopy(m) for m in modules}
    for alias, target in _MODULE_ALIASES.items():
        if alias in lib or target not in lib:
            continue
        spec = deepcopy(lib[target])
        spec["id"] = alias
        if alias == "mini-pump-5v":
            spec["label"] = "5V mini water pump"
        lib[alias] = spec
    variants = {
        module_id: {**deepcopy(lib[meta["pinsFrom"]]), "id": module_id, "label": meta["label"]}
        for module_id, meta in footprints.items()
        if module_id not in lib and meta.get("pinsFrom") in lib
    }

    def with_reserved_pins(module_id: str, spec: dict) -> dict:
        meta = footprints.get(module_id, {})
        reserved = {
            **(footprints.get(meta.get("pinsFrom"), {}).get("reservedPins") or {}),
            **(meta.get("reservedPins") or {}),
        }
        return {
            **spec,
            "pins": [
                {**pin, **({"reserved": reserved[pin["id"]]} if pin["id"] in reserved else {})}
                for pin in spec.get("pins") or []
            ],
        }

    return {mid: with_reserved_pins(mid, spec) for mid, spec in {**lib, **variants}.items()}


def _load_library() -> dict[str, dict]:
    global _MODULE_LIBRARY
    if _MODULE_LIBRARY is None:
        with open(_DATA_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        _MODULE_LIBRARY = _build_library(data.get("module_library", []), _MODULE_FOOTPRINTS)
    return _MODULE_LIBRARY


# ---------------------------------------------------------------------------
# Public API (mirrors TS helpers)
# ---------------------------------------------------------------------------

def find_module(module_id: str) -> Optional[dict]:
    """Return ModuleSpec dict for module_id, or None."""
    return deepcopy(_load_library().get(module_id))


def find_modules_by_capabilities(requires_any: list[list[str]]) -> list[dict]:
    """Return modules whose capabilityTags satisfy every OR-group in requires_any."""
    out: list[dict] = []
    for module in _load_library().values():
        tags = set(module.get("capabilityTags") or [])
        if all(any(cap in tags for cap in alt) for alt in requires_any):
            out.append(deepcopy(module))
    return out


def find_pin(module: dict, pin_id: str) -> Optional[dict]:
    """Return pin dict for pin_id on module, or None."""
    for pin in module.get("pins") or []:
        if pin.get("id") == pin_id:
            return pin
    return None


def resolve_module_footprint(module_id: str) -> str:
    """Return KiCad footprint string."""
    meta = _MODULE_FOOTPRINTS.get(module_id)
    if meta:
        return meta.get("kicadFootprint", f"Circuit.AI:{module_id}")
    return f"Circuit.AI:{module_id}"


def resolve_module_fit(module_id: str) -> dict:
    """Return the fit record for a module: how its footprint was checked against the real part.

    ``{"status": "verified_against", "verified_against": <citation>}`` or
    ``{"status": "unverified_variant", "reason": <why>}``. A module with no registered
    footprint is drawn with a synthetic placeholder, so it is never verified.
    """
    meta = _MODULE_FOOTPRINTS.get(module_id)
    fit = meta.get("fit") if meta else None
    if isinstance(fit, dict) and fit.get("status") in ("verified_against", "unverified_variant"):
        return dict(fit)
    return {
        "status": "unverified_variant",
        "reason": "No registered footprint: a synthetic two-column placeholder is used.",
    }


def resolve_module_body_mm(module_id: str) -> Optional[dict]:
    """Return {w, h} body envelope in mm, or None."""
    meta = _MODULE_FOOTPRINTS.get(module_id)
    if meta:
        return meta.get("bodyMm")
    return None


def resolve_module_pads(module_id: str, spec: Optional[dict] = None) -> Optional[list[dict]]:
    """Return list of {pinId, x, y} pad defs (local mm from center), or None.

    Mirrors resolveModulePads from module-footprints.ts: custom table first,
    then synthetic dual-column fallback when spec.pins is available.
    """
    meta = _MODULE_FOOTPRINTS.get(module_id)
    if meta:
        custom = meta.get("pads")
        if custom:
            return list(custom)
    if not spec or not spec.get("pins"):
        return None
    pins = spec["pins"]
    half = math.ceil(len(pins) / 2)
    return _dual_col(
        [p["id"] for p in pins[:half]],
        [p["id"] for p in pins[half:]],
    )


def bounds_from_pads(pads: list[dict], margin: float = 3) -> dict:
    """Return {w, h} bounding box of pad positions plus margin."""
    if not pads:
        return {"w": 10, "h": 10}
    xs = [p["x"] for p in pads]
    ys = [p["y"] for p in pads]
    w = max(max(xs) - min(xs) + margin * 2, 8)
    h = max(max(ys) - min(ys) + margin * 2, 8)
    return {"w": w, "h": h}


def list_canvas_modules() -> list[dict]:
    """Modules with KiCad footprints — curated set for browser canvas compose."""
    lib = _load_library()
    rows: list[dict] = []
    for module_id in sorted(_MODULE_FOOTPRINTS.keys()):
        spec = lib.get(module_id)
        if spec:
            rows.append(deepcopy(spec))
    return rows
