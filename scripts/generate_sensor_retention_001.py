#!/usr/bin/env python3
"""Source-bound mechanical retention proposal for HS Sensor 001.

Adds two external M3 through-bolt ears to both case and lid. It does NOT
assert that any board can be mounted: neither catalog board has verified
mounting-hole coordinates. The resulting parts remain unqualified for use.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: dict) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()


def create_retention(project: Path) -> dict:
    from hardware_splicer.device_plan import build_device_plan

    project = Path(project).resolve()
    receipt = json.loads((project / "CROSS_DOMAIN_RECEIPT.json").read_text())
    for name in ("DEVICE_SPEC.json", "DEVICE_PLAN.json",
                 "ENCLOSURE_INPUT.json", "VENTILATION_PLAN.json", "enclosure.scad"):
        if digest((project / name).read_bytes()) != receipt["artifacts"][name]["sha256"]:
            raise ValueError("Untrusted source artifact hash: " + name)
    spec = json.loads((project / "DEVICE_SPEC.json").read_text())
    plan = json.loads((project / "DEVICE_PLAN.json").read_text())
    if build_device_plan(spec) != plan:
        raise ValueError("Device plan is not reproducible from source spec")
    enclosure = json.loads((project / "ENCLOSURE_INPUT.json").read_text())
    vent = json.loads((project / "VENTILATION_PLAN.json").read_text())
    if not vent.get("lid_vent_slots_over_sensor_footprint") or len(vent["lid_slots_mm"]) != 4:
        raise ValueError("No verified source-plan ventilation geometry")
    w = float(enclosure["inner_w_mm"]) + 2 * float(enclosure["wall_mm"])
    d = float(enclosure["inner_d_mm"]) + 2 * float(enclosure["wall_mm"])
    h = float(enclosure["inner_h_mm"]) + float(enclosure["floor_mm"])
    lid_t = float(enclosure["lid_mm"])
    # Product-specific prototype geometry, not verified commercial fastening.
    projection, overlap, tab_span, tab_t = 8.0, 1.0, 10.0, 2.0
    hole_d, offset = 3.4, 4.0
    if lid_t != tab_t or d < tab_span + 8.0:
        raise ValueError("Lid thickness or enclosure width incompatible with prototype tabs")
    if offset - hole_d / 2 < 1.0 or projection - offset - hole_d / 2 < 1.0:
        raise ValueError("Insufficient tab fastener-edge clearance")
    usb = enclosure["cutouts"][0]["rect"]
    usb_elevation = enclosure["floor_mm"] + usb["y_mm"]
    if usb_elevation + usb["h_mm"] > h - tab_t - 1.0:
        raise ValueError("USB cutout is too close to proposed tab connection")
    y0 = round((d - tab_span) / 2, 3)
    holes = [{"x_mm": -offset, "y_mm": d / 2},
             {"x_mm": w + offset, "y_mm": d / 2}]
    old = (project / "enclosure.scad").read_text()
    lines = old.splitlines(keepends=True)
    matches = [i for i, row in enumerate(lines) if row.strip() == "vented_enclosure();"]
    if len(matches) != 1:
        raise ValueError("Expected precisely one source-bound vented enclosure entrypoint")
    lines[matches[0]] = ""
    scad = "".join(lines)
    scad += ("\n// Standalone case/lid bolt ears; requires physical M3 + nut clearance review.\n")
    for kind in ("base", "lid"):
        inner = "base()" if kind == "base" else "vented_lid()"
        z = round(h - tab_t, 3) if kind == "base" else 0
        scad += f"module retained_{kind}() {{\n  difference() {{\n    union() {{\n"
        scad += f"      {inner};\n"
        for x in (-projection, w - overlap):
            scad += (f"      translate([{round(x,3)}, {y0}, {z}]) "
                     f"cube([{projection + overlap}, {tab_span}, {tab_t}]);\n")
        scad += "    }\n"
        for hole in holes:
            scad += (f"    translate([{round(hole['x_mm'],3)}, {round(hole['y_mm'],3)}, "
                     f"{round(z-1,3)}]) cylinder(h={tab_t+2}, d={hole_d}, $fn=96);\n")
        scad += "  }\n}\n"
    scad += (f"module retained_assembly() {{\n  retained_base();\n"
             f"  translate([0, 0, {h}]) retained_lid();\n}}\nretained_assembly();\n")
    manifest = {
        "schema_version": "hardware_splicer.lid_retention_proposal.v1",
        "source_spec_sha256": receipt["source_spec_sha256"],
        "source_enclosure_sha256": receipt["artifacts"]["enclosure.scad"]["sha256"],
        "method": "two_external_through_bolt_ears",
        "fastener_nominal": "M3 screw and nut, exact length and fit UNVERIFIED",
        "tab_projection_mm": projection, "tab_overlap_mm": overlap,
        "tab_span_mm": tab_span, "tab_thickness_mm": tab_t,
        "hole_diameter_mm": hole_d, "hole_centers_mm": holes,
        "base_z_mm": h - tab_t, "lid_z_mm": 0,
        "expected_base_extent_mm": [round(w+2*projection,3), round(d,3), round(h,3)],
        "expected_lid_extent_mm": [round(w+2*projection,3), round(d,3), round(lid_t,3)],
        "nominal_added_volume_each_part_mm3": round(
            2 * (projection * tab_span - math.pi * (hole_d/2)**2) * tab_t, 3
        ),
        "board_mounting": {
            "status": "BLOCKED_UNVERIFIED_BOARD_MOUNT_HOLES",
            "required": ["measured ESP32 board mounting holes or approved alternative fixture",
                         "measured BME280 breakout mounting-hole coordinates",
                         "header underside/power and wire harness clearances",
                         "PCB support and fastener torque/retention tests"],
            "standoffs_generated": False,
        },
        "geometry_checked": False,
        "fit_tested": False, "bolt_strength_tested": False,
        "physical_fastener_verified": False, "assembly_authorized": False,
        "fabrication_authorized": False,
    }
    dst_scad = project / "enclosure_retained.scad"
    dst_meta = project / "LID_RETENTION_PLAN.json"
    if dst_scad.exists() or dst_meta.exists():
        raise FileExistsError("Refusing to replace a previously generated retention proposal")
    dst_scad.write_text(scad)
    dst_meta.write_bytes(_json(manifest))
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(create_retention(args.project), indent=2))
        return 0
    except (ValueError, FileNotFoundError, FileExistsError) as err:
        print(f"HS retention proposal refused: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
