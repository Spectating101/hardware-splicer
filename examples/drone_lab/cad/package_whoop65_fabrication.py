#!/usr/bin/env python3
"""Create one directly usable 65mm microdrone fabrication handoff ZIP.

Source frame files are REUSED from vsergeev/3d-parametric-whoop, not redrawn.
The STEP/FCStd files were made by running HS's FreeCAD script inside Atech
Atelier's bundled (unchanged) FreeCAD 1.1.3 on the user's Optiplex.

This packages manufacturing files and a build guide. It does not test/approve
mechanical fit, print a frame, energize motors or claim physical flight.
"""

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

ORIGINAL_COMMIT = "13cf8c2909de18afe5ddc95b091026e6f11f8e8a"
FRAME_HASHES = {
    "65mm_26x26_whoop.stl":
        "8af1446e7fc76b07ff76bb9571f1e5198d798c6cafa44177af2c087a783f6e8c",
    "betafpv_c03_26x26_canopy.stl":
        "403c6c71542263aa7a3d1250871fe7a1375381cea85e2075547b0a0feb72e5a7",
    "betafpv_c03_camera_harness.stl":
        "7868917fa7f8ea09fc623aaca7054f74f509a21dcf9098ef47e6b03447452266",
}
OPENSCAD_SOURCE = (
    "whoop.scad", "65mm_26x26_whoop.scad",
    "canopy.scad", "betafpv_c03_26x26_canopy.scad",
    "betafpv_c03_camera_harness.scad", "betafpv_c03_camera_harness.scad",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True,
                        help="local clone of vsergeev/3d-parametric-whoop pinned to the declared commit")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    drone_dir = here.parent
    upstream = args.upstream.resolve()
    src_stl = upstream / "stl"

    for file, sha in FRAME_HASHES.items():
        path = src_stl / file
        if digest(path) != sha:
            raise ValueError(f"Original source STL hash mismatch: {file}")

    generated_zip = here / "hs-whoop65-real-freecad-outputs.zip"
    if digest(generated_zip) != "1fa4c7cda556497adaa762a54d136c70335a6d827d9d51e733f8c303ba8fe142":
        raise ValueError("Atech FreeCAD output bytes changed since original measured export")

    with tempfile.TemporaryDirectory(prefix="hs-whoop65-package-") as folder:
        package = Path(folder) / "HS_WHOOP65_FABRICATION"
        printable = package / "PRINTABLE_STL"
        cad = package / "EDITABLE_FCStd_STEP"
        openscad = package / "PARAMETRIC_FRAME_SOURCE"
        docs = package / "INSTRUCTIONS"
        for p in (printable, cad, openscad, docs):
            p.mkdir(parents=True, exist_ok=True)

        for filename in FRAME_HASHES:
            shutil.copy2(src_stl / filename, printable / filename)

        for filename in OPENSCAD_SOURCE:
            path = upstream / filename
            if path.exists():
                shutil.copy2(path, openscad / filename)

        # Exactly two real FreeCAD-generated manufacturing solids.
        with zipfile.ZipFile(generated_zip) as z:
            for item in z.infolist():
                filename = Path(item.filename).name
                if not filename or "/" not in item.filename:
                    continue
                if filename.endswith(".stl"):
                    destination = printable / filename
                elif filename.endswith((".FCStd", ".step")):
                    destination = cad / filename
                elif filename == "whoop65_cad_manifest.json":
                    destination = docs / filename
                else:
                    raise ValueError("Unexpected payload in measured FreeCAD export: " + filename)
                if not item.filename.startswith("hs-whoop65-cad-exports/"):
                    raise ValueError("Unexpected archive path")
                destination.write_bytes(z.read(item))

        for f in ("README.md", "hs_whoop65_build.json"):
            shutil.copy2(drone_dir / f, docs / f)

        (docs / "ATTRIBUTION.txt").write_text(
            "FRAME/CANOPY/CAMERA HARNESS: vsergeev/3d-parametric-whoop at "
            + ORIGINAL_COMMIT + "\n"
            "https://github.com/vsergeev/3d-parametric-whoop\n"
            "Original author's STL and OpenSCAD files are under CC BY 4.0; "
            "the original author retains attribution.\n"
            "JIG/GAUGE: modeled using Atech Atelier's bundled FreeCAD 1.1.3; "
            "source build_whoop65_fixture.py lives in HS.\n"
            "This package combines sourced printable geometry with HS-generated "
            "fit-check tools. It has NOT been printed, assembled or flight-certified.\n"
        )

        (package / "OPEN_FIRST.txt").write_text(
            "HS 65mm DIY WHOOP — FABRICATION HANDOFF\n\n"
            "1. PRINTABLE_STL/65mm_26x26_whoop.stl = original 65mm frame.\n"
            "2. PRINTABLE_STL/betafpv_c03_26x26_canopy.stl = optional C03 camera canopy.\n"
            "3. PRINTABLE_STL/betafpv_c03_camera_harness.stl = camera harness.\n"
            "4. PRINTABLE_STL/whoop65_26x26_board_fit_jig.stl = bench alignment jig.\n"
            "5. PRINTABLE_STL/whoop65_battery_pocket_go_gauge.stl = fit dummy.\n"
            "6. EDITABLE_FCStd_STEP/ = real editable FreeCAD source and STEP for the jig and gauge.\n"
            "7. PARAMETRIC_FRAME_SOURCE/ = the original author's editable OpenSCAD code.\n"
            "8. INSTRUCTIONS/hs_whoop65_build.json + README.md = compatible BOM and steps.\n\n"
            "These are real geometry files. You still need a slicer profile, physical "
            "printer, components and qualified props-off setup before a real flight.\n"
        )

        manifest = {
            "product": "HS-WHOOP65-1S",
            "deliverable": "source-reused actual printer geometry and native FreeCAD tools",
            "original_airframe_commit": ORIGINAL_COMMIT,
            "source_published_fabrication_example": True,
            "original_airframe_hashes": FRAME_HASHES,
            "atech_freecad_generated_zip_sha256":
                "1fa4c7cda556497adaa762a54d136c70335a6d827d9d51e733f8c303ba8fe142",
            "printed": False,
            "assembled": False,
            "flown_physically": False,
            "valid_fabrication_package_not_real_hardware": True,
        }
        (docs / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, "w", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9) as z:
            for file in sorted(package.rglob("*")):
                if file.is_file():
                    z.write(file, file.relative_to(package.parent))
        print(json.dumps({
            "result": "REAL_FABRICATION_PACKAGE_EXPORTED",
            "zip": str(args.out),
            "zip_sha256": digest(args.out),
            "zip_bytes": args.out.stat().st_size,
            "original_airframe_printable_parts": len(FRAME_HASHES),
            "original_editable_scad_files": len(list(openscad.iterdir())),
            "HS_generated_printable_freecad_parts": 2,
            "STEP_files": len(list(cad.glob("*.step"))),
            "FCStd_files": len(list(cad.glob("*.FCStd"))),
            "physical_product_built": False,
        }, indent=2))


if __name__ == "__main__":
    main()
