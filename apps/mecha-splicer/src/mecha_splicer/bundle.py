from __future__ import annotations

import json
import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

from .engines.bom import build_bom
from .engines.dfm import check_project
from .engines.openscad import (
    generate_belt_reduction_parts_scad,
    generate_bracket_scad,
    generate_enclosure_scad,
    generate_gripper_parts_scad,
    generate_linear_axis_parts_scad,
    generate_leadscrew_axis_parts_scad,
    generate_pan_tilt_parts_scad,
    generate_rotary_joint_parts_scad,
    generate_servo_mount_scad,
)
from .engines.assembly import generate_assembly_scad
from .spec import ProjectSpec


def generate_bundle(spec: Dict[str, Any], *, out_dir: Optional[str | Path] = None) -> Dict[str, Any]:
    project = ProjectSpec.model_validate(spec)

    issues = check_project(project)
    blockers = any(i.severity == "block" for i in issues)
    bom = build_bom(project)

    outputs: Dict[str, str] = {}
    if project.enclosure is not None:
        outputs["enclosure.scad"] = generate_enclosure_scad(project.enclosure)
    if project.bracket is not None:
        outputs["bracket.scad"] = generate_bracket_scad(project.bracket)
    if project.servo_mount is not None:
        outputs["servo_mount.scad"] = generate_servo_mount_scad(project.servo_mount)
    if project.linear_axis is not None:
        outputs.update(generate_linear_axis_parts_scad(project.linear_axis))
    if project.leadscrew_axis is not None:
        outputs.update(generate_leadscrew_axis_parts_scad(project.leadscrew_axis))
    if project.rotary_joint is not None:
        outputs.update(generate_rotary_joint_parts_scad(project.rotary_joint))
    if project.belt_reduction is not None:
        outputs.update(generate_belt_reduction_parts_scad(project.belt_reduction))
    if project.gripper is not None:
        outputs.update(generate_gripper_parts_scad(project.gripper))
    if project.pan_tilt is not None:
        outputs.update(generate_pan_tilt_parts_scad(project.pan_tilt))
    if project.assembly is not None:
        outputs["ASSEMBLY.scad"] = generate_assembly_scad(project)

    bundle: Dict[str, Any] = {
        "project_name": project.project_name,
        "mode": project.mode,
        "process": project.process,
        "blockers": blockers,
        "dfm": [{"severity": i.severity, "message": i.message} for i in issues],
        "bom": [b.to_dict() for b in bom],
        "outputs": list(outputs.keys()),
        "notes": project.notes,
    }

    if out_dir is not None:
        outp = Path(out_dir)
        outp.mkdir(parents=True, exist_ok=True)
        (outp / "mecha_splicer.bundle.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        for name, content in outputs.items():
            (outp / name).write_text(content, encoding="utf-8")
        _write_bom_csv(outp / "bom.csv", bom)
        (outp / "README.md").write_text(_render_readme(bundle), encoding="utf-8")

    return bundle


def _render_readme(bundle: Dict[str, Any]) -> str:
    lines = []
    lines.append(f"# Mecha-Splicer Bundle: {bundle.get('project_name','')}\n")
    lines.append("## Outputs")
    for o in bundle.get("outputs", []):
        lines.append(f"- `{o}`")
    lines.append("")
    lines.append("## BOM")
    for b in bundle.get("bom", []):
        lines.append(f"- {b.get('qty')}× {b.get('item')} ({b.get('spec')})")
    lines.append("")
    lines.append("## DFM Notes")
    for d in bundle.get("dfm", []):
        lines.append(f"- [{d.get('severity')}] {d.get('message')}")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def _write_bom_csv(path: Path, bom) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "item", "spec", "qty", "sku", "notes"])
        for b in bom:
            w.writerow([b.category, b.item, b.spec, b.qty, getattr(b, "sku", ""), b.notes])
