"""Copper track width for a current, before routing, and the routed board's narrowest track checked against it after.

The formula is IPC-2221's chart fit, I = k dT^0.44 A^0.725, with I in amperes, dT the track's temperature rise in C, A its
cross-section in square mils, and k = 0.048 for outer layers or 0.024 for inner layers (IPC-2221B, section 6.2; HS-BUS-A's
checks used it first). IPC-2152 replaced the chart with measured data that usually allows narrower tracks, so widths from
this fit err on the wide side. Copper is 35 um (1 oz) unless the board says otherwise.

A design gives its currents as ``net_currents_a``, keyed by net name or KiCad net-class pattern (``"*VIN_12V": 5``):

* ``netclasses_for_currents`` turns them into net classes the router obeys (track width for a set temperature rise);
* ``check_routed`` reads every track segment of a routed ``.kicad_pcb`` and reports, per net, the narrowest track's rise
  at that current. A net carried only by a pour has no tracks to judge and says so.

A pass means the tracks are wide enough by this fit, at the current the design states. It is not a thermal simulation:
neighbouring tracks, pours, vias and airflow are not modelled, and nothing here was measured.
"""
from __future__ import annotations

import fnmatch
import math
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "hardware_splicer.trace_capacity.v1"
BASIS = "IPC-2221B 6.2 chart fit I = k dT^0.44 A^0.725 (A in mil^2; k 0.048 outer, 0.024 inner)"
MIL = 0.0254


def _k(external: bool) -> float:
    return 0.048 if external else 0.024


def temperature_rise(current_a: float, width_mm: float, copper_um: float = 35.0, external: bool = True) -> float:
    """Temperature rise (C) of a track carrying ``current_a``."""
    if current_a <= 0:
        return 0.0
    area = (width_mm / MIL) * (copper_um / 1000 / MIL)
    return (current_a / (_k(external) * area ** 0.725)) ** (1 / 0.44)


def width_for_current(current_a: float, rise_c: float = 10.0, copper_um: float = 35.0, external: bool = True) -> float:
    """Narrowest track (mm, rounded up to 0.05 mm) that carries ``current_a`` with at most ``rise_c`` of temperature rise."""
    area = (current_a / (_k(external) * rise_c ** 0.44)) ** (1 / 0.725)
    width = area / (copper_um / 1000 / MIL) * MIL
    return round(math.ceil(width / 0.05 - 1e-9) * 0.05, 2)


def netclasses_for_currents(net_currents: Mapping[str, float], *, rise_c: float = 10.0, copper_um: float = 35.0,
                            min_track_mm: float = 0.2, clearance_mm: float = 0.2) -> list[dict[str, Any]]:
    """One net class per stated current, wide enough on an outer layer. Small currents keep the board's default track."""
    classes = []
    for i, (pattern, amps) in enumerate(sorted(net_currents.items())):
        width = max(min_track_mm, round(width_for_current(float(amps), rise_c, copper_um), 2))
        if width <= min_track_mm:
            continue
        big = width >= 0.8
        classes.append({"name": f"I{i}_{re.sub(r'[^A-Za-z0-9]', '', pattern)[:16] or 'NET'}", "track": width, "clearance": clearance_mm,
                        "via_d": 1.0 if big else 0.8, "via_drill": 0.5 if big else 0.4,
                        "patterns": [pattern if any(c in pattern for c in "*?") else f"*{pattern}"],
                        "basis": f"{amps:g} A at {rise_c:g} C rise, {copper_um:g} um copper; {BASIS}"})
    return classes


def routed_widths(pcb_path: Path) -> dict[str, dict[str, Any]]:
    """Per net name: the narrowest track width on outer and inner layers and the number of segments."""
    text = Path(pcb_path).read_text(encoding="utf-8", errors="replace")
    numbers = {m.group(1): m.group(2) for m in re.finditer(r'^\s*\(net (\d+) "((?:[^"\\]|\\.)*)"\)', text, re.M)}
    out: dict[str, dict[str, Any]] = {}
    # A track segment's fields run up to its uuid (tstamp in older files); single-line segments end at their last parenthesis.
    for m in re.finditer(r"\((segment|arc)\b(.*?)\((?:uuid|tstamp)\b", text, re.S):
        body = m.group(2)
        width = re.search(r"\(width ([\d.]+)\)", body)
        layer = re.search(r'\(layer "?([^")\s]+)"?\)', body)
        net = re.search(r'\(net (?:(\d+)|"((?:[^"\\]|\\.)*)")', body)
        if not (width and layer and net):
            continue
        name = net.group(2) if net.group(2) is not None else numbers.get(net.group(1), net.group(1))
        row = out.setdefault(name, {"segments": 0, "outer_min_mm": None, "inner_min_mm": None})
        row["segments"] += 1
        key = "outer_min_mm" if layer.group(1) in ("F.Cu", "B.Cu") else "inner_min_mm"
        w = float(width.group(1))
        row[key] = w if row[key] is None else min(row[key], w)
    return out


def check_routed(pcb_path: Path, net_currents: Mapping[str, float], *, max_rise_c: float = 20.0, copper_um: float = 35.0) -> dict[str, Any]:
    widths = routed_widths(pcb_path)
    rows, findings = [], []
    for pattern, amps in sorted(net_currents.items()):
        glob = pattern if any(c in pattern for c in "*?") else f"*{pattern}"
        nets = sorted(n for n in widths if fnmatch.fnmatchcase(n, glob)) or sorted(n for n in widths if n.lstrip("/") == pattern)
        if not nets:
            findings.append({"severity": "info", "rule": "current_net_without_tracks",
                             "message": f"No track carries {pattern} ({amps:g} A): it is routed by a pour or not at all, which this check does not judge."})
            continue
        for net in nets:
            w = widths[net]
            rises = [temperature_rise(float(amps), w[k], copper_um, k == "outer_min_mm") for k in ("outer_min_mm", "inner_min_mm") if w[k]]
            rise = max(rises)
            rows.append({"net": net, "current_a": float(amps), "outer_min_mm": w["outer_min_mm"], "inner_min_mm": w["inner_min_mm"],
                         "segments": w["segments"], "worst_rise_c": round(rise, 1)})
            if rise > max_rise_c:
                need = width_for_current(float(amps), max_rise_c, copper_um)
                findings.append({"severity": "warning", "rule": "track_too_narrow_for_current", "net": net,
                                 "message": f"{net}: the narrowest track ({min(x for x in (w['outer_min_mm'], w['inner_min_mm']) if x)} mm) would rise "
                                            f"{rise:.0f} C at {amps:g} A; at least {need:.2f} mm on an outer layer keeps it under {max_rise_c:g} C."})
    return {"schema_version": SCHEMA, "basis": BASIS, "copper_um": copper_um, "max_rise_c": max_rise_c, "nets": rows, "findings": findings,
            "claim_boundary": "Track-width arithmetic from a chart fit at stated currents; not a thermal simulation and not measured."}
