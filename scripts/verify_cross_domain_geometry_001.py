#!/usr/bin/env python3
"""Independent OpenSCAD mesh checks for Cross-Domain Sensor 001.

Renders BASE and LID separately, compares geometry with the manifest, and
verifies the planned USB opening was actually subtracted from the 3D solid.
This does not imply mechanical fit, material strength or print authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/mecha-splicer/src"))


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _render(source: str, target: Path, workdir: Path, openscad: str) -> None:
    input_file = workdir / (target.stem + ".scad")
    input_file.write_text(source)
    result = subprocess.run(
        [openscad, "-o", str(target), str(input_file)],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if result.returncode or not target.is_file() or not target.stat().st_size:
        raise ValueError(f"OpenSCAD render failed for {target.name}: "
                         + (result.stderr or result.stdout)[-1500:])


def _only_component(source: str, component: str) -> str:
    if component not in ("base", "lid"):
        raise ValueError("Only declared enclosure components are supported")
    matches = re.findall(r"(?m)^enclosure\(\);\s*$", source)
    if len(matches) != 1:
        raise ValueError("Cannot safely isolate exactly one enclosure() call")
    return re.sub(r"(?m)^enclosure\(\);\s*$", f"{component}();", source)


def _read_mesh(path: Path, expected_mm: list[float]) -> dict:
    import trimesh

    mesh = trimesh.load_mesh(path, process=True)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path.name} is not a nonempty triangulated solid")
    if not mesh.is_watertight or not mesh.is_winding_consistent:
        raise ValueError(f"{path.name} has an open or inconsistent triangle mesh")
    if not math.isfinite(mesh.volume) or mesh.volume <= 0:
        raise ValueError(f"{path.name} has nonpositive mesh volume")
    extents = [float(x) for x in mesh.extents]
    if any(not math.isclose(got, exp, rel_tol=0, abs_tol=0.15)
           for got, exp in zip(extents, expected_mm)):
        raise ValueError(f"{path.name} has unexpected dimensions: "
                         f"{extents} vs {expected_mm} mm")
    return {
        "file": path.name,
        "sha256": sha(path.read_bytes()),
        "bytes": path.stat().st_size,
        "watertight": bool(mesh.is_watertight),
        "consistent_winding": bool(mesh.is_winding_consistent),
        "bounds_mm": [[float(x) for x in row] for row in mesh.bounds],
        "extents_mm": extents,
        "volume_mm3": round(float(mesh.volume), 3),
        "triangle_count": int(len(mesh.faces)),
    }


def inspect_enclosure(project: Path, *, openscad: str = "openscad") -> dict:
    project = Path(project).resolve()
    record = json.loads((project / "CROSS_DOMAIN_RECEIPT.json").read_text())
    paths = ("ENCLOSURE_INPUT.json", "enclosure.scad", "DEVICE_SPEC.json")
    for name in paths:
        if sha((project / name).read_bytes()) != record["artifacts"][name]["sha256"]:
            raise ValueError(f"Source artifact hash mismatch: {name}")
    if not record["revision_consistent"] or record["fabrication_authorized"]:
        raise ValueError("Cross-domain package revision or authority invalid")
    binary = shutil.which(openscad)
    if not binary:
        raise ValueError("OpenSCAD binary missing")
    from mecha_splicer.spec import EnclosureSpec
    from mecha_splicer.engines.openscad import generate_enclosure_scad

    envelope = json.loads((project / "ENCLOSURE_INPUT.json").read_text())
    validated = EnclosureSpec.model_validate(envelope)
    generated = (project / "enclosure.scad").read_text()
    if generate_enclosure_scad(validated) != generated:
        raise ValueError("Actual CAD source disagrees with bound enclosure parameters")
    w, d, h = validated.inner_w_mm, validated.inner_d_mm, validated.inner_h_mm
    wall, floor = validated.wall_mm, validated.floor_mm
    base_dims = [w + 2 * wall, d + 2 * wall, h + floor]
    lid_dims = [w + 2 * wall, d + 2 * wall, validated.lid_mm]
    with tempfile.TemporaryDirectory(prefix="hs-geometry-", dir=project) as temp:
        work = Path(temp)
        base = project / "enclosure_base.stl"
        lid = project / "enclosure_lid.stl"
        if base.exists() or lid.exists():
            raise ValueError("Refusing to overwrite previous meshes")
        _render(_only_component(generated, "base"), base, work, binary)
        _render(_only_component(generated, "lid"), lid, work, binary)
        base_result = _read_mesh(base, base_dims)
        lid_result = _read_mesh(lid, lid_dims)
        no_hole_model = validated.model_copy(update={"cutouts": []})
        # Validate again to avoid incorrectly trusted object mutation.
        no_hole_model = EnclosureSpec.model_validate(no_hole_model.model_dump())
        reference = work / "uncut_base.stl"
        _render(_only_component(generate_enclosure_scad(no_hole_model), "base"),
                reference, work, binary)
        reference_result = _read_mesh(reference, base_dims)

    cuts = validated.cutouts
    if len(cuts) != 1 or cuts[0].kind != "rect" or cuts[0].face != "left":
        raise ValueError("Expected exactly one left-wall rectangular USB opening")
    cut = cuts[0].rect
    if cut is None:
        raise ValueError("USB aperture dimensions missing")
    nominal_removed = cut.w_mm * cut.h_mm * wall
    actual_removed = reference_result["volume_mm3"] - base_result["volume_mm3"]
    if nominal_removed <= 0 or not math.isclose(
        actual_removed, nominal_removed, rel_tol=0.035, abs_tol=1.5
    ):
        raise ValueError(
            "USB aperture not represented by expected removed 3D volume: "
            f"{actual_removed:.2f} vs {nominal_removed:.2f} mm3"
        )
    return {
        "schema_version": "hardware_splicer.cross_domain_geometry_evidence.v1",
        "source_spec_sha256": record["source_spec_sha256"],
        "geometry_backend": "OpenSCAD CLI + trimesh independent mesh inspection",
        "base": base_result,
        "lid": lid_result,
        "usb_opening": {
            "nominal_removed_mm3": round(nominal_removed, 3),
            "observed_removed_mm3": round(actual_removed, 3),
            "observed_3d_subtraction": True,
        },
        "checked_source_artifact_hashes": True,
        "physical_fit_verified": False,
        "mechanical_strength_verified": False,
        "printability_verified": False,
        "manufacturing_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    target = args.project / "GEOMETRY_EVIDENCE.json"
    if target.exists():
        parser.error("Refusing to replace an existing geometry report")
    try:
        report = inspect_enclosure(args.project)
        target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except Exception as exc:
        print(f"Geometry verification failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
