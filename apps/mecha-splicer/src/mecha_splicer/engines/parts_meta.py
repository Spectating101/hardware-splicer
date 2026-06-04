from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

from ..spec import ProjectSpec


@dataclass(frozen=True)
class PartMeta:
    file: str
    module: str
    kind: str
    print_orientation: str
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def build_parts_meta(project: ProjectSpec, outputs: List[str]) -> List[PartMeta]:
    out: List[PartMeta] = []
    for f in outputs:
        if not str(f).endswith(".scad"):
            continue
        stem = Path(str(f)).stem
        kind, orient, notes = _classify(project, str(f))
        out.append(PartMeta(file=str(f), module=stem, kind=kind, print_orientation=orient, notes=notes))
    return out


def _classify(project: ProjectSpec, filename: str) -> tuple[str, str, str]:
    # Orientation vocabulary is intentionally simple; slicers differ.
    if filename in {"enclosure.scad", "bracket.scad", "servo_mount.scad"}:
        return "structure", "flat_on_base", "Print flat; verify first-layer squish for hole accuracy."
    if filename in {"motor_mount.scad", "idler_mount.scad", "ls_motor_mount.scad", "ls_screw_end_support.scad"}:
        return "mount", "flat_on_plate", "Increase perimeters for stiffness; consider PETG/ABS for heat."
    if filename in {"carriage.scad", "ls_carriage_nut_mount.scad"}:
        return "carriage", "flat_on_plate", "Ream rod bores if tight; keep clearance >=0.4mm for FDM."
    if filename in {"rod_holder.scad"}:
        return "clamp", "flat_on_plate", "Print with high perimeters; tighten bolts gradually to avoid cracking."
    if filename in {"belt_clamp.scad", "tensioner_block.scad", "endstop_mount.scad"}:
        return "accessory", "flat_on_plate", "Prototype-grade accessory; verify hole sizing."
    if filename.startswith("rj_"):
        return "rotary_joint", "flat_on_plate", "Bearing pockets may need clearance tuning (0.2–0.4mm typical)."
    if filename.startswith("br_"):
        return "reduction", "flat_on_plate", "Use rigid mounting; plate thickness matters more than infill."
    if filename.startswith("gr_"):
        return "gripper", "flat_on_plate", "Use washers/bushings at pivots; printed friction-fit is unreliable."
    if filename.startswith("pt_"):
        return "pan_tilt", "flat_on_plate", "Use spacers to avoid interference at high tilt angles."
    if filename == "ASSEMBLY.scad":
        return "assembly", "n/a", "This file imports modules; render it to visually check placement."
    return "part", "flat_on_plate", ""

