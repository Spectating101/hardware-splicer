"""Infer footprint body size from KiCad library name (minimal engine port)."""

from __future__ import annotations

import re
from typing import Dict


def infer_footprint_size(footprint_lib: str, ref: str) -> Dict[str, float | str | int | None]:
    name = footprint_lib or ""

    m = re.search(r"(SOIC|SOP|TSSOP|SSOP|MSOP|VSSOP)[-_]?(\d+)[-_]?(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", name, re.I)
    if m:
        w, h = float(m.group(3)), float(m.group(4))
        return {"w_mm": max(w, h) + 1, "h_mm": min(w, h) + 1.5, "kind": "ic", "pinCount": int(m.group(2))}

    m = re.search(r"(LQFP|TQFP|QFP|QFN|DFN|VQFN)[-_]?(\d+)[-_]?(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)mm", name, re.I)
    if m:
        return {"w_mm": float(m.group(3)), "h_mm": float(m.group(4)), "kind": "ic", "pinCount": int(m.group(2))}

    if re.search(r"PinHeader_1x(\d+)", name, re.I):
        count = int(re.search(r"PinHeader_1x(\d+)", name, re.I).group(1))
        return {"w_mm": 2.54 * count + 1.2, "h_mm": 3.5, "kind": "connector", "pinCount": count}

    if re.search(r"ESP32|WROOM|Arduino|Pico|Module:", name, re.I):
        return {"w_mm": 18, "h_mm": 25, "kind": "module"}

    if re.search(r"BarrelJack|USB", name, re.I):
        return {"w_mm": 10, "h_mm": 8, "kind": "connector"}

    prefix = re.sub(r"\d+$", "", ref or "U").upper()
    defaults = {
        "U": (5.0, 4.0, "ic"),
        "J": (7.0, 5.0, "connector"),
        "P": (7.0, 5.0, "connector"),
    }
    w, h, kind = defaults.get(prefix, (12.0, 10.0, "unknown"))
    return {"w_mm": w, "h_mm": h, "kind": kind}
