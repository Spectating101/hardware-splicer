"""Export the verified Fielddeck display revision and its retained print parts."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "digital_v1"
REPLACED = {"face_rear_left", "face_rear_right", "tray_rear_left", "tray_rear_right"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bundle(build_dir, baseline, destination):
    geometry = json.loads((build_dir / "geometry.json").read_text())
    if geometry["status"] != "nominal_geometry_checks_passed":
        raise ValueError("A verified native build is required.")
    retained_geometry = baseline / "cad/geometry_report.json"
    evidence = json.loads((ROOT / "sources/evidence.json").read_text())
    if digest(retained_geometry.read_bytes()) != evidence["baseline"]["files"]["cad/geometry_report.json"]:
        raise ValueError("The retained baseline differs from the source record.")

    exports = geometry["exports"]
    names = [row["part"] for row in exports["exported_parts"]]
    if set(names) != REPLACED | {"display_spacer_1"} or len(names) != 5:
        raise ValueError("Unexpected changed-part export inventory.")
    expected = {
        "cad/FIELDDECK_5.step": exports["assembly_step_sha256"],
        "cad/FIELDDECK_5.glb": exports["assembly_glb_sha256"],
        "display5-LICENSE.txt": evidence["vendor_step"]["license_sha256"],
    }
    for row in exports["exported_parts"]:
        for extension in ("step", "stl"):
            expected[f"cad/changed_parts/{row['part']}.{extension}"] = row[f"{extension}_sha256"]
    payload = {"sources/vendor5.zip": (ROOT / "sources/vendor5.zip").read_bytes()}
    if digest(payload["sources/vendor5.zip"]) != evidence["vendor_step"]["archive_sha256"]:
        raise ValueError("The vendor STEP archive differs from the source record.")
    for name, sha256 in expected.items():
        data = (build_dir / name).read_bytes()
        if digest(data) != sha256:
            raise ValueError(f"Export changed after verification: {name}")
        payload[name] = data
    for name in ("geometry.json", "power.json", "BOM.json", "BOM.csv", "substitution.json",
                 "source-evidence.json", "connections.json"):
        payload[name] = (build_dir / name).read_bytes()
    if json.loads(payload["source-evidence.json"]) != evidence:
        raise ValueError("The build's source evidence differs from the study.")

    retained_parts = json.loads(retained_geometry.read_text())["parts"]
    for row in retained_parts:
        if row["printable"] and row["name"] not in REPLACED:
            for extension in ("step", "stl"):
                filename = f"{row['name']}.{extension}"
                data = (baseline / "cad/print" / filename).read_bytes()
                if digest(data) != row[f"{extension}_sha256"]:
                    raise ValueError(f"Retained print part differs: {filename}")
                payload["cad/retained_parts/" + filename] = data

    payload["MANIFEST.json"] = (json.dumps({
        "schema_version": "hardware_splicer.fielddeck_display_bundle.v1",
        "revision": "Fielddeck 5 digital display swap",
        "physical_fit_verified": False,
        "files_sha256": {name: digest(data) for name, data in sorted(payload.items())},
    }, indent=2) + "\n").encode()

    with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payload.items()):
            archive.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(destination) as archive:
        manifest = json.loads(archive.read("MANIFEST.json"))
        if set(manifest["files_sha256"]) | {"MANIFEST.json"} != set(archive.namelist()):
            raise ValueError("Bundle artifact inventory differs.")
        for name, sha256 in manifest["files_sha256"].items():
            if digest(archive.read(name)) != sha256:
                raise ValueError(f"Bundle hash differs: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=BASE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    bundle(args.build, args.baseline, args.output)


if __name__ == "__main__":
    main()
