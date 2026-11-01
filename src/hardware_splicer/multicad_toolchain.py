"""Cross-tool reusable CAD authoring contract, independent of any specific product.

Every part has one exact source-bound native STEP reference and an explicit
analytic type. build123d authors a *new* STEP; CadQuery independently checks
volumes and bounds of BOTH outputs. PartCAD receives a source-contained
partcad.yaml package, never a fabricated supplier-qualified BOM.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

SCHEMA = "hardware_splicer.multicad_parts.v1"
RESULT_SCHEMA = "hardware_splicer.multicad_native_evidence.v1"
PARTCAD_SCHEMA = "hardware_splicer.partcad_package_receipt.v1"


def canonical(x: Any) -> bytes:
    return (json.dumps(x, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def digest(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def require(flag: bool, reason: str) -> None:
    if not flag:
        raise ValueError("HS multi-CAD refused: " + reason)


def safe_name(value: str) -> bool:
    return (isinstance(value, str) and bool(value)
            and len(value) <= 80
            and all(c.isascii() and (c.isalnum() or c in "_-") for c in value)
            and value not in {".", ".."})


def shape_dimensions(row: dict) -> tuple[float, float, float]:
    shape = row.get("shape")
    dims = row.get("dimensions_mm")
    require(shape in {"box", "cylinder"} and isinstance(dims, list)
            and len(dims) == (3 if shape == "box" else 2),
            "only known analytic box or cylinder dimensions accepted")
    require(all(isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v) and 0 < v <= 100000 for v in dims),
            "invalid or unsafe parametric dimensions")
    if shape == "box":
        return tuple(float(v) for v in dims)
    return (float(dims[0]), float(dims[0]), float(dims[1]))


def validate_manifest(root: Path) -> dict:
    root = Path(root)
    manifest = json.loads((root / "PARTS_MANIFEST.json").read_text())
    require(manifest.get("schema_version") == SCHEMA, "unknown manifest schema")
    require(safe_name(manifest.get("product_id")), "missing product identity")
    sha = manifest.get("source_spec_sha256")
    require(isinstance(sha, str) and len(sha) == 64
            and all(x in "0123456789abcdef" for x in sha),
            "missing product specification hash")
    require(manifest.get("physical_release_authorized") is False
            and manifest.get("vendor_geometry_qualified") is False,
            "unknown physical or manufacturer authority")
    parts = manifest.get("parts")
    require(isinstance(parts, list) and bool(parts), "no modelled parts")
    ids: set[str] = set()
    for row in parts:
        ident = row.get("id")
        require(safe_name(ident) and ident not in ids, "duplicate or unsafe part name")
        ids.add(ident)
        shape_dimensions(row)
        require(row.get("source_status") == "conceptual_analytic_reference"
                and row.get("physical_tested") is False,
                "unverified manufacturer or physical status")
        path = row.get("reference_step")
        require(path == f"references/{ident}.step", "unsafe or mismatched reference path")
        original = root / path
        require(original.is_file() and original.stat().st_size > 0,
                "reference source STEP missing")
        require(digest(original.read_bytes()) == row.get("reference_sha256"),
                "reference STEP changed after source authoring")
    return manifest


def prepare_from_cadclaw(product_root: Path, cad_root: Path, output: Path) -> dict:
    """Construct a generic reference/shape contract from a verified HS product.

    ClearBench is only the first test source, not an invariant of the generic
    validator or the build123d/PartCAD native runners.
    """
    from .product_ecosystem_bridge import load_product

    product, receipt, _ = load_product(product_root)
    authored = json.loads((Path(cad_root) / "CADCLAW_INPUT_RECEIPT.json").read_text())
    require(authored.get("source_spec_sha256") == receipt["product_spec_sha256"]
            and authored.get("product_id") == product["product_id"]
            and authored.get("physical_release_authorized") is False,
            "CadQuery reference belongs to another product or claims fabrication")
    layout = product["layout"]
    spec = [
        ("tray", "box", [layout["tray"][k] for k in ("width_mm", "depth_mm", "height_mm")]),
        ("panel", "box", [layout["back_panel"][k] for k in ("width_mm", "thickness_mm", "height_mm")]),
        ("housing_envelope", "cylinder", [layout["filter_housing"][k] for k in ("diameter_mm", "height_mm")]),
        ("sample_concept", "cylinder", [layout["sample_cup"][k] for k in ("diameter_mm", "height_mm")]),
    ]
    require(set(authored.get("authored_step_parts", {})) == {item[0] for item in spec},
            "CADCLAW reference inventory incomplete")
    out = Path(output)
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())),
            "refusing to overwrite prior multi-CAD data")
    refs = out / "references"
    refs.mkdir(parents=True, exist_ok=True)
    rows = []
    for ident, shape, dimensions in spec:
        existing = authored["authored_step_parts"][ident]
        require(existing.get("file") == f"parts/{ident}.step",
                "mismatched native reference inventory")
        path = Path(cad_root) / existing["file"]
        require(path.is_file() and digest(path.read_bytes()) == existing.get("sha256"),
                "native CADCLAW part changed after authoring")
        expected = shape_dimensions({"shape": shape, "dimensions_mm": dimensions})
        require(all(math.isclose(float(g), v, abs_tol=.02) for g,v in
                    zip(existing["dims_mm"], expected)),
                "native CADCLAW dimension disagrees with product source")
        dest = refs / f"{ident}.step"
        shutil.copyfile(path, dest)
        rows.append({
            "id": ident, "shape": shape, "dimensions_mm": dimensions,
            "reference_step": f"references/{ident}.step",
            "reference_sha256": digest(dest.read_bytes()),
            "source_status": "conceptual_analytic_reference",
            "physical_tested": False,
        })
    result = {
        "schema_version": SCHEMA, "product_id": product["product_id"],
        "source_spec_sha256": receipt["product_spec_sha256"], "parts": rows,
        "physical_release_authorized": False, "vendor_geometry_qualified": False,
    }
    (out / "PARTS_MANIFEST.json").write_bytes(canonical(result))
    validate_manifest(out)
    return result


def author_with_build123d(root: Path) -> dict:
    """Actually author independent build123d STEP, then CadQuery-verify both."""
    from build123d import Align, Box, Cylinder, export_step, import_step
    import cadquery as cq

    root = Path(root)
    manifest = validate_manifest(root)
    out = root / "partcad"
    require(not out.exists(), "existing native outputs must never be overwritten")
    parts_dir = out / "parts"
    parts_dir.mkdir(parents=True)
    records = []
    package = {"parts": {}}
    for row in manifest["parts"]:
        ident = row["id"]
        a,b,c = shape_dimensions(row)
        obj = (Box(a,b,c, align=(Align.MIN,Align.MIN,Align.MIN))
               if row["shape"] == "box"
               else Cylinder(a/2,c, align=(Align.CENTER,Align.CENTER,Align.MIN)))
        dst = parts_dir / f"{ident}.step"
        require(export_step(obj, str(dst)) is True and dst.is_file()
                and dst.stat().st_size > 0, "build123d native STEP export failed")
        # The independent CadQuery importer verifies topology and volume,
        # not just a metadata echo from the new BRep author.
        original = cq.importers.importStep(str(root / row["reference_step"]))
        reproduced = cq.importers.importStep(str(dst))
        require(len(original.solids().vals()) == 1
                and len(reproduced.solids().vals()) == 1,
                "expected exactly one solid on each native STEP import")
        reference_box = original.val().BoundingBox()
        authored_box = reproduced.val().BoundingBox()
        got_dims = [authored_box.xlen, authored_box.ylen, authored_box.zlen]
        ref_dims = [reference_box.xlen, reference_box.ylen, reference_box.zlen]
        require(all(math.isclose(v, target, abs_tol=.08) and
                    math.isclose(ref, target, abs_tol=.08)
                    for v,ref,target in zip(got_dims,ref_dims,(a,b,c))),
                "independent native STEP bounds disagree")
        v1 = original.val().Volume()
        v2 = reproduced.val().Volume()
        require(v1 > 0 and math.isclose(v1,v2,rel_tol=.0005,abs_tol=.01),
                "independent geometry volume disagreement")
        loaded = import_step(str(dst))
        require(math.isclose(float(loaded.volume), v2, rel_tol=.0005,abs_tol=.01),
                "build123d STEP round trip lost volume")
        package["parts"][ident] = {
            "type": "step", "path": f"parts/{ident}.step",
            "desc": "HS source-bound conceptual solid; NOT physically qualified",
        }
        records.append({
            "id": ident, "reference_sha256": row["reference_sha256"],
            "authored_step_sha256": digest(dst.read_bytes()),
            "dimensions_mm": [round(x,3) for x in got_dims],
            "volume_mm3": round(v2,3),
            "cadquery_reference_volume_mm3": round(v1,3),
            "independent_step_round_trip_pass": True,
            "manufacturer_qualified": False, "fabrication_authorized": False,
        })
    import yaml
    (out/"partcad.yaml").write_text(yaml.safe_dump(package,sort_keys=False))
    # The PartCAD package is a real native format; its execution is a separate gate.
    report = {
        "schema_version": RESULT_SCHEMA, "product_id": manifest["product_id"],
        "source_spec_sha256": manifest["source_spec_sha256"],
        "toolchains_executed": ["build123d STEP export and import",
                                "CadQuery independent reference and output STEP import"],
        "parts": records, "partcad_package_created": True,
        "partcad_cli_executed": False, "physical_release_authorized": False,
    }
    (root/"MULTICAD_NATIVE_EVIDENCE.json").write_bytes(canonical(report))
    return report


def check_native_outputs(root: Path) -> dict:
    root=Path(root)
    manifest=validate_manifest(root)
    report=json.loads((root/"MULTICAD_NATIVE_EVIDENCE.json").read_text())
    require(report.get("schema_version") == RESULT_SCHEMA and
            report.get("source_spec_sha256") == manifest["source_spec_sha256"] and
            report.get("product_id") == manifest["product_id"],
            "evidence from different source/specimen")
    require(report.get("physical_release_authorized") is False and
            report.get("partcad_cli_executed") is False,
            "physical or PartCAD execution status forged")
    require(len(report.get("parts", [])) == len(manifest["parts"]),
            "incomplete cross-tool inventory")
    observed={r.get("id"):r for r in report["parts"]}
    require(set(observed)=={r["id"] for r in manifest["parts"]},
            "missing or duplicated part evidence")
    for part in manifest["parts"]:
        record=observed[part["id"]]
        file=root/"partcad"/"parts"/f'{part["id"]}.step'
        require(file.is_file() and digest(file.read_bytes()) == record.get("authored_step_sha256")
                and record.get("reference_sha256") == part["reference_sha256"]
                and record.get("independent_step_round_trip_pass") is True
                and record.get("manufacturer_qualified") is False
                and record.get("fabrication_authorized") is False,
                "changed source/new STEP or falsely promoted native geometry")
    return report


def partcad_execution_receipt(root: Path, cli_output: Path) -> dict:
    root=Path(root)
    report=check_native_outputs(root)
    raw=Path(cli_output).read_bytes()
    require(raw.strip() and b"Traceback" not in raw and b"Error:" not in raw,
            "no successful PartCAD CLI transcript")
    # The CI step must exit zero before this procedure can record execution.
    receipt={"schema_version": PARTCAD_SCHEMA,
             "source_spec_sha256": report["source_spec_sha256"],
             "native_partcad_cli_ran": True,
             "partcad_log_sha256": digest(raw),
             "native_cad_part_count": len(report["parts"]),
             "all_native_parts_manufacturer_qualified": False,
             "fabrication_authorized": False}
    (root/"PARTCAD_EXECUTION_RECEIPT.json").write_bytes(canonical(receipt))
    return receipt
