#!/usr/bin/env python3
"""Independent mesh and source-binding checks for external lid-fastener ears.

This checker re-derives retention source from exact HS artifacts and verifies
the actual volumes of holes/tabs; it does not qualify a real plastic fastener.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entrypoint(source: str, name: str) -> str:
    if name not in ("base", "lid", "retained_base", "retained_lid", "vented_lid"):
        raise ValueError("Unsupported geometry module")
    actual = "retained_assembly();" if "retained_assembly();" in source else "vented_enclosure();"
    lines = source.splitlines(keepends=True)
    indices = [i for i, line in enumerate(lines) if line.strip() == actual]
    if len(indices) != 1:
        raise ValueError("Expected exactly one model entrypoint")
    lines[indices[0]] = name + "();\n"
    return "".join(lines)


def verify_retention(project: Path) -> dict:
    project = Path(project).resolve()
    retention = _load_script(
        "hs_retention_generator", ROOT / "scripts/generate_sensor_retention_001.py"
    )
    geometry = _load_script(
        "hs_geometry_validator", ROOT / "scripts/verify_cross_domain_geometry_001.py"
    )
    receipt = json.loads((project / "CROSS_DOMAIN_RECEIPT.json").read_text())
    plan = json.loads((project / "LID_RETENTION_PLAN.json").read_text())
    scad = (project / "enclosure_retained.scad").read_text()
    if plan["source_spec_sha256"] != receipt["source_spec_sha256"]:
        raise ValueError("Source spec mismatch")
    if plan["source_enclosure_sha256"] != receipt["artifacts"]["enclosure.scad"]["sha256"]:
        raise ValueError("Enclosure revision mismatch")
    if plan["board_mounting"]["standoffs_generated"] or plan["assembly_authorized"]:
        raise ValueError("Unexpected mechanical authority")
    with tempfile.TemporaryDirectory(prefix="hs-retention-compare-") as folder:
        temp = Path(folder)
        for file in ("DEVICE_SPEC.json", "DEVICE_PLAN.json", "ENCLOSURE_INPUT.json",
                     "VENTILATION_PLAN.json", "enclosure.scad", "CROSS_DOMAIN_RECEIPT.json"):
            shutil.copyfile(project / file, temp / file)
        expected = retention.create_retention(temp)
        if expected != plan or (temp / "enclosure_retained.scad").read_text() != scad:
            raise ValueError("Retention files not reproducible from HS source artifacts")
    binary = shutil.which("openscad")
    if not binary:
        raise ValueError("Native OpenSCAD not available")
    enclosure = json.loads((project / "ENCLOSURE_INPUT.json").read_text())
    outer_w = enclosure["inner_w_mm"] + 2 * enclosure["wall_mm"]
    outer_d = enclosure["inner_d_mm"] + 2 * enclosure["wall_mm"]
    outer_h = enclosure["inner_h_mm"] + enclosure["floor_mm"]
    lid_t = enclosure["lid_mm"]
    ref_scad = (project / "enclosure.scad").read_text()

    with tempfile.TemporaryDirectory(prefix="hs-retention-mesh-") as folder:
        temp = Path(folder)
        observed = {}
        for name, source, expected_dimensions in (
            ("retained_base", scad, [outer_w+16, outer_d, outer_h]),
            ("retained_lid", scad, [outer_w+16, outer_d, lid_t]),
            ("unretained_base", ref_scad, [outer_w, outer_d, outer_h]),
            ("unretained_lid", ref_scad, [outer_w, outer_d, lid_t]),
        ):
            module = name.removeprefix("un")
            if name == "unretained_base":
                module = "base"
            elif name == "unretained_lid":
                module = "vented_lid"
            target = project / (name + ".stl") if not name.startswith("un") else temp / (name + ".stl")
            if target.exists():
                raise FileExistsError("Refusing to overwrite previously rendered retention mesh")
            geometry._render(_entrypoint(source, module), target, temp, binary)
            observed[name] = geometry._read_mesh(target, expected_dimensions)

    # Two external ears per part, with each tab overlapping the existing body
    # by 1 mm. Holes lie wholly outside the original body's x footprint.
    intended = plan["nominal_added_volume_each_part_mm3"]
    base_added = observed["retained_base"]["volume_mm3"] - observed["unretained_base"]["volume_mm3"]
    lid_added = observed["retained_lid"]["volume_mm3"] - observed["unretained_lid"]["volume_mm3"]
    for name, change in (("base", base_added), ("lid", lid_added)):
        if not math.isclose(change, intended, rel_tol=0.015, abs_tol=1.5):
            raise ValueError(f"Unexpected material volume for {name} external tabs: {change:.3f} mm3")
    for name in ("retained_base", "retained_lid"):
        minimum, maximum = observed[name]["bounds_mm"]
        if abs(minimum[0] + 8.0) > 0.1 or abs(maximum[0] - (outer_w + 8.0)) > 0.1:
            raise ValueError("Retaining tabs do not have required outside extents")
    return {
        "schema_version": "hardware_splicer.lid_retention_mesh_evidence.v1",
        "source_spec_sha256": receipt["source_spec_sha256"],
        "source_enclosure_sha256": receipt["artifacts"]["enclosure.scad"]["sha256"],
        "lid_retention_plan_sha256": hashlib.sha256(
            (project / "LID_RETENTION_PLAN.json").read_bytes()).hexdigest(),
        "geometry_source_sha256": hashlib.sha256(scad.encode()).hexdigest(),
        "retained_base": observed["retained_base"],
        "retained_lid": observed["retained_lid"],
        "nominal_added_volume_each_part_mm3": intended,
        "observed_added_volume_mm3": {
            "base": round(base_added, 3), "lid": round(lid_added, 3),
        },
        "retention_ear_and_hole_geometry_verified": True,
        "board_mounting_verified": False,
        "lid_fastener_strength_verified": False,
        "physical_fit_verified": False,
        "assembly_authorized": False,
        "manufacturing_authorized": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project", type=Path, required=True)
    args = p.parse_args()
    out = args.project / "LID_RETENTION_GEOMETRY_EVIDENCE.json"
    if out.exists():
        p.error("Output evidence already exists")
    try:
        evidence = verify_retention(args.project)
        out.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
        print(json.dumps(evidence, indent=2))
        return 0
    except (OSError, ValueError, KeyError, ImportError) as e:
        print(f"HS retention geometry gate failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
