#!/usr/bin/env python3
"""Cross-domain HS proof: one source spec -> validated wiring, firmware ZIP, case SCAD.

This is a deterministic *proposal* pipeline. It does not produce new native
KiCad schematic/PCB, measured fit, compiled binary, fabricated enclosure or
authorize flashing, printing or physical power-on.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

# Direct execution from scripts/ otherwise imports the legacy scripts/hardware_splicer.py
# instead of the installed src/hardware_splicer package.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_plan import build_device_plan, example_specs

MECHA_SRC = ROOT / "apps/mecha-splicer/src"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: dict) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def _enclosure_from_plan(plan: dict) -> tuple[dict, str]:
    """Map HS device coordinates (x along box, z across, y up) to Mecha XYZ.

    Only USB left-wall cutout can be mapped exactly here. Ventilation, mounts,
    lid retention and real board fit are still unresolved.
    """
    if str(MECHA_SRC) not in sys.path:
        sys.path.insert(0, str(MECHA_SRC))
    from mecha_splicer.spec import EnclosureSpec
    from mecha_splicer.engines.openscad import generate_enclosure_scad

    box = plan["case"]
    dimensions = box["inner_mm"]
    w, d, h = (float(dimensions["x"]), float(dimensions["z"]),
               float(dimensions["y"]))
    wall = float(box["wall_mm"])
    cut = box.get("usb_cutout")
    if not isinstance(cut, dict) or cut.get("wall") != "-x":
        raise ValueError("Cannot map USB without a known -x wall placement")
    # The original plan centers x and z in the case; y is height from base.
    port_width, port_height = float(cut["width_mm"]), float(cut["height_mm"])
    lateral = d / 2 + float(cut["z"]) - port_width / 2
    elevation = float(cut["y"]) - wall - port_height / 2
    if not (lateral >= 0 and lateral + port_width <= d and
            elevation >= 0 and elevation + port_height <= h):
        raise ValueError("USB aperture crosses a case boundary; refusing CAD export")
    envelope = {
        "name": "hs_esp32_bme280_enclosure_proposal",
        "inner_w_mm": w, "inner_d_mm": d, "inner_h_mm": h,
        "wall_mm": wall, "floor_mm": wall,
        "lid_mm": wall, "clearance_mm": float(box["clearance_mm"]),
        "include_standoffs": False,
        "include_lid_screw_holes": False,
        "lid_style": "screw",
        "cutouts": [{"kind": "rect", "face": "left", "label": "usb_cable_access",
                     "rect": {"x_mm": round(lateral, 3),
                              "y_mm": round(elevation, 3),
                              "w_mm": port_width, "h_mm": port_height}}],
    }
    cad = EnclosureSpec.model_validate(envelope)
    return envelope, generate_enclosure_scad(cad)



def _add_sensor_ventilation(plan: dict, envelope: dict, original_scad: str) -> tuple[dict, str]:
    """Project plan's placed boards to the Mecha case and cut sensor-facing lid slots.

    Deterministic *catalog-envelope* check only; no measured mounting, air
    exchange or sensor accuracy is inferred. Uses the HS-centered XYZ mapping.
    """
    dims = plan["case"]["inner_mm"]
    inner_w, inner_d, inner_h = dims["x"], dims["z"], dims["y"]
    wall = envelope["wall_mm"]
    components = []
    for module in plan["modules"]:
        box = module["box"]
        x0, x1 = box["x0"] + inner_w / 2, box["x1"] + inner_w / 2
        y0, y1 = box["z0"] + inner_d / 2, box["z1"] + inner_d / 2
        z0 = module["base_y"] - module["below_board_mm"]
        z1 = module["base_y"] + module["pcb_mm"]["z"] + module["above_board_mm"]
        if min(x0, y0, z0) < -0.01 or x1 > inner_w + 0.01 or y1 > inner_d + 0.01 or z1 > wall + inner_h + 0.01:
            raise ValueError(f"Catalog component {module['id']} extends past declared enclosure bounds")
        components.append({
            "id": module["id"], "module": module["module"], "kind": module["kind"],
            "board_xy_mm": [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)],
            "height_mm": [round(z0, 3), round(z1, 3)],
            "dimension_basis": "catalog_and_declared_overrides_not_measured",
        })
    for index, first in enumerate(components):
        a = first["board_xy_mm"]
        for second in components[index + 1:]:
            b = second["board_xy_mm"]
            if min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1]):
                raise ValueError("Declared PCB footprints overlap: " + first["id"] + "/" + second["id"])
    sensors = [x for x in components if x["module"] == "adafruit-bme280-stemma-qt"]
    if len(sensors) != 1:
        raise ValueError("BME280 ventilation fixture requires exactly one sensor module")
    sx0, sy0, sx1, sy1 = sensors[0]["board_xy_mm"]
    cx, cy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    # Four narrow 8 x 1.2 mm vents entirely over the BME280 breakout region.
    # These *do not* prove ambient response, humidity accuracy or FDM clearance.
    slots = []
    for offset in (-4.8, -1.6, 1.6, 4.8):
        lx, ly = round(cx - 4.0, 3), round(cy + offset - 0.6, 3)
        if not (sx0 + 2 <= lx and lx + 8 <= sx1 - 2 and
                sy0 + 2 <= ly and ly + 1.2 <= sy1 - 2):
            raise ValueError("Sensor vent pattern cannot fit within breakout footprint")
        if not (lx >= 2 and ly >= 2 and lx + 8 <= inner_w - 2 and ly + 1.2 <= inner_d - 2):
            raise ValueError("Sensor vent too close to enclosure rim")
        for component in components:
            if component["id"] == sensors[0]["id"]:
                continue
            a, b, c, d = component["board_xy_mm"]
            if min(lx + 8, c) > max(lx, a) and min(ly + 1.2, d) > max(ly, b):
                raise ValueError("Sensor vents overlap another component footprint")
        slots.append({
            "x_mm": round(lx + wall, 3), "y_mm": round(ly + wall, 3),
            "width_mm": 8.0, "depth_mm": 1.2,
        })
    # Mecha Splicer emits an extra trailing blank line; isolate the final call
    # by its exact line rather than assuming a particular newline count.
    lines = original_scad.splitlines(keepends=True)
    entrypoints = [i for i, line in enumerate(lines) if line.strip() == "enclosure();"]
    if len(entrypoints) != 1:
        raise ValueError("Mecha-generated enclosure source has an unrecognized final call")
    lines[entrypoints[0]] = ""
    scad = "".join(lines)
    scad += "\n// Ventilation tied to the measured-or-declared HS sensor footprint.\n"
    scad += "module vented_lid() {\n  difference() {\n    lid();\n"
    for slot in slots:
        scad += (f'    translate([{slot["x_mm"]}, {slot["y_mm"]}, -1]) '
                 f'cube([{slot["width_mm"]}, {slot["depth_mm"]}, lid_t + 2], center=false);\n')
    scad += "  }\n}\n"
    scad += (f"module vented_enclosure() {{\n  base();\n  translate([0, 0, "
             f"{round(inner_h + wall + 1.0, 3)}]) vented_lid();\n}}\n"
             "vented_enclosure();\n")
    manifest = {
        "schema_version": "hardware_splicer.cross_domain_sensor_ventilation.v1",
        "source_revision": "derived_from_DEVICE_PLAN_and_ENCLOSURE_INPUT",
        "catalog_component_envelopes": components,
        "sensor_id": sensors[0]["id"],
        "lid_slots_mm": slots,
        "slot_count": len(slots),
        "nominal_lid_material_removed_mm3": round(
            sum(x["width_mm"] * x["depth_mm"] * envelope["lid_mm"] for x in slots), 3
        ),
        "catalog_footprints_nonoverlapping": True,
        "catalog_component_envelopes_within_case": True,
        "lid_vent_slots_over_sensor_footprint": True,
        "sensor_airflow_validated": False,
        "mechanical_mounting_validated": False,
        "physical_dimensions_measured": False,
    }
    return manifest, scad


def build_cross_domain_package(spec: dict, output: Path) -> dict:
    """Generate all artifacts from one input with an explicit provenance receipt."""
    # Both subsystems re-evaluate the same spec; no caller-supplied plan accepted.
    spec_bytes = _json(spec)
    plan = build_device_plan(spec)
    firmware_meta, firmware_zip = build_device_application(spec)
    enclosure, basic_scad = _enclosure_from_plan(plan)
    ventilation, scad = _add_sensor_ventilation(plan, enclosure, basic_scad)

    with zipfile.ZipFile(io.BytesIO(firmware_zip)) as archive:
        firmware_declared_spec = json.loads(archive.read("DEVICE_SPEC.json"))
        firmware_declared_plan = json.loads(archive.read("DEVICE_PLAN.json"))
        firmware_proposal = json.loads(archive.read("FIRMWARE_PROPOSAL.json"))
    if firmware_declared_spec != spec or firmware_declared_plan != plan:
        raise ValueError("Firmware source package does not match the design plan")
    if firmware_proposal.get("firmware_authorized") or firmware_proposal.get("power_on_authorized"):
        raise ValueError("A proposal unexpectedly claimed physical authority")
    if firmware_meta.get("status") != "HOST_TESTABLE_PROPOSAL":
        raise ValueError("Unexpected firmware package authority status")

    output = Path(output)
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Output folder must be new or empty")
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "DEVICE_SPEC.json": spec_bytes,
        "DEVICE_PLAN.json": _json(plan),
        "FIRMWARE_SOURCE.zip": firmware_zip,
        "ENCLOSURE_INPUT.json": _json(enclosure),
        "VENTILATION_PLAN.json": _json(ventilation),
        "enclosure.scad": scad.encode(),
    }
    for filename, payload in files.items():
        (output / filename).write_bytes(payload)
    receipt = {
        "schema_version": "hardware_splicer.cross_domain_sensor_001.v1",
        "project_id": "esp32_bme280_usb_enclosure_proposal",
        "source_spec_sha256": _sha(spec_bytes),
        "artifacts": {name: {"sha256": _sha(body), "bytes": len(body)}
                      for name, body in sorted(files.items())},
        "revision_consistent": True,
        "firmware_package_status": firmware_meta["status"],
        "electrical_status": "device_wiring_plan_only",
        "mechanical_status": "openscad_proposal_only",
        "firmware_compile_status": "NOT_RUN",
        "geometry_render_status": "NOT_RUN",
        "independent_fit_validation": False,
        "enclosure_mounted_and_ventilated": False,
        "sensor_ventilation_geometry_proposed": True,
        "native_eda_artifacts_verified": False,
        "device_physically_assembled": False,
        "hardware_measurements_present": False,
        "fabrication_authorized": False,
        "flashing_authorized": False,
        "power_on_authorized": False,
        "unresolved": [
            "Board and breakout dimensions must be measured for exact purchased versions",
            "USB plug aperture placement and clearance require physical test-fit",
            "Enclosure now has derived vent cutouts, but airflow and mounting remain unvalidated",
            "Lid geometry lacks approved retention mechanism or tested seals",
            "No native original KiCad design or PCB, no electrical measurement",
            "No verified printer material profile, sliced toolpath or device authorization",
        ],
    }
    (output / "CROSS_DOMAIN_RECEIPT.json").write_bytes(_json(receipt))
    return receipt


def sensor_only_spec() -> dict:
    """Use existing supported wiring example without the optional display."""
    spec = example_specs()["esp32_oled_bme280_usb"]
    spec["name"] = "ESP32 BME280 environmental monitor, USB powered"
    spec["modules"] = [row for row in spec["modules"] if row["id"] != "display"]
    spec["connections"] = [row for row in spec["connections"]
                           if not row["from"].startswith("display.")]
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_cross_domain_package(sensor_only_spec(), args.output)
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
