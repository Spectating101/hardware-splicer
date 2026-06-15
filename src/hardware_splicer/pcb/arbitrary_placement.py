"""Place components that are not in the module catalog (KiCad netlist / arbitrary IR)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .footprint_sizes import infer_footprint_size


def pins_for_component(netlist: Mapping[str, Any], ref: str) -> List[str]:
    """Collect unique pin names for a component ref from netlist nets."""
    seen: set[str] = set()
    ordered: List[str] = []
    for net in netlist.get("nets") or []:
        for pin in net.get("pins") or []:
            if str(pin.get("component_ref") or "") != ref:
                continue
            pid = str(pin.get("pin") or "")
            if not pid or pid in seen:
                continue
            seen.add(pid)
            ordered.append(pid)
    return ordered


def synthetic_module_spec(
    module_id: str,
    *,
    footprint: str = "",
    value: str = "",
    ref: str = "U",
    pin_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a module-registry-compatible spec for arbitrary footprints."""
    pins = list(pin_ids or [])
    size = infer_footprint_size(footprint, ref)
    pin_count = int(size.get("pinCount") or 0)
    if not pins:
        if pin_count > 0:
            pins = [str(i) for i in range(1, pin_count + 1)]
        else:
            pins = ["1", "2"]

    label = value or module_id or ref
    return {
        "id": module_id or ref,
        "label": label,
        "footprint": footprint or module_id or ref,
        "pins": [{"id": pid, "label": pid, "role": "signal"} for pid in pins],
        "_arbitrary": True,
        "_body_mm": {"w": float(size["w_mm"]), "h": float(size["h_mm"])},
    }
