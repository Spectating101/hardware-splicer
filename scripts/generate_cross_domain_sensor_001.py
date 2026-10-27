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

from hardware_splicer.device_application import build_device_application
from hardware_splicer.device_plan import build_device_plan, example_specs

ROOT = Path(__file__).resolve().parents[1]
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


def build_cross_domain_package(spec: dict, output: Path) -> dict:
    """Generate all artifacts from one input with an explicit provenance receipt."""
    # Both subsystems re-evaluate the same spec; no caller-supplied plan accepted.
    spec_bytes = _json(spec)
    plan = build_device_plan(spec)
    firmware_meta, firmware_zip = build_device_application(spec)
    enclosure, scad = _enclosure_from_plan(plan)

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
        "native_eda_artifacts_verified": False,
        "device_physically_assembled": False,
        "hardware_measurements_present": False,
        "fabrication_authorized": False,
        "flashing_authorized": False,
        "power_on_authorized": False,
        "unresolved": [
            "Board and breakout dimensions must be measured for exact purchased versions",
            "USB plug aperture placement and clearance require physical test-fit",
            "Enclosure has no validated sensor ventilation or mechanical mounting",
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
