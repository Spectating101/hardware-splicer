"""Reopen the delivered Fielddeck 5 geometry and recompute its saved claims."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from build import (power_comparison, prepare_assembly, read, reimport_geometry, require,
                   sha, write, write_bom)
from study_contract import BASELINE, CASE_ID, PACKAGE, REVISION, engineering_result, evaluator, requirements


def main():
    selected = requirements()
    parts, revised, mount, checks, evidence, assessment, vendor_license = prepare_assembly(
        BASELINE, evaluator=evaluator())
    exports = reimport_geometry(parts, revised, REVISION)
    native = read(REVISION / "geometry.json")
    expected_geometry = {"status": "nominal_geometry_checks_passed", "display_mount": mount,
                         "checks": checks, "exports": exports, "physical_fit_verified": False}
    require(native.keys() == expected_geometry.keys(), "Unexpected geometry report fields.")
    for key, value in expected_geometry.items():
        require(native[key] == value, f"Reimported geometry differs from the saved {key} claim.")
    require(read(REVISION / "substitution.json") == assessment, "Retained interface assessment differs.")
    require(read(REVISION / "source-evidence.json") == evidence, "Retained source declarations differ.")
    require((REVISION / "display5-LICENSE.txt").read_bytes() == vendor_license, "Vendor license differs.")
    require(read(REVISION / "connections.json") == {"display": assessment["connections"],
                                                    "rigid_cad_check": checks["ffc_reserved_access"]},
            "Retained connection plan differs.")
    power = power_comparison(read(BASELINE / "design.json"), evidence["product_brief"]["documented_power_w"],
                             requirements=selected)
    require(read(REVISION / "power.json") == power, "Power scenarios differ from the selected requirements.")
    expected = engineering_result(power, selected)
    require(read(REVISION / "engineering.json") == expected, "Engineering checks differ from recomputation.")
    with TemporaryDirectory(prefix="hs-fielddeck5-bom-") as temp:
        assembled = Path(temp)
        write_bom(BASELINE, assembled)
        for name in ("BOM.json", "BOM.csv"):
            require((REVISION / name).read_bytes() == (assembled / name).read_bytes(), "Retained BOM differs.")
    # Original enclosure parts included alongside the new ones retain the
    # exact baseline print geometry hashes.
    for row in read(BASELINE / "cad/geometry_report.json")["parts"]:
        for ext in ("step", "stl") if row["printable"] and row["name"] not in revised else ():
            require(sha(BASELINE / "cad/print" / (row["name"] + "." + ext)) == row[ext + "_sha256"],
                    f"Retained {row['name']} {ext} differs from the baseline.")
    contract = read(PACKAGE / "study-contract.json")
    names = contract["adapter"]["outputs"]
    require(all(name.startswith("revision/") and ".." not in Path(name).parts for name in names),
            "Unexpected archived output path.")
    verified = {name: sha(PACKAGE / name) for name in names if name != "revision/verification.json"}
    write(REVISION / "verification.json", {
        "case_id": CASE_ID, "artifact_integrity": True, "physical_validation_performed": False,
        "engineering_acceptance": expected["requirements_met"], "artifact_sha256": verified,
        "reimported_assembly_solids": exports["reimported_assembly_solids"],
        "clear_ribbon_reserve_boxes": len(checks["ffc_reserved_access"]["reserved_boxes_mm"]),
        "mount_paths_checked": checks["display_mount_paths_checked"],
    })
    print(json.dumps({"verified_payload_files": len(verified), "engineering_acceptance": expected["requirements_met"]}))


if __name__ == "__main__":
    main()
