"""Independent integrity and deliverable audit of the SPI reference's KiCad-9 ZIP.

This validates source-file hash bindings and *presence/content* of CAM/assembly
deliverables, not their manufacturer compatibility or physical correctness.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = "hardware_splicer.spi_native_cam_review.v1"
PREFIX = "spi_flash_adapter_v1/"
REQUIRED_SOURCE = (
    "spi_flash_adapter_v1.kicad_pcb", "spi_flash_adapter_v1.kicad_sch",
    "BOM.csv", "design_manifest.json", "verification.json",
    "spi_flash_adapter_v1.kicad_pro", "design_checks.py",
)
REQUIRED_LAYERS = (
    "F_Cu", "B_Cu", "F_Mask", "B_Mask", "F_Paste", "B_Paste",
    "F_Silkscreen", "Edge_Cuts",
)
# KiCad defaults to industry Protel extensions (GT(L/B), soldermask,
# silkscreen, G(M)1). Both Protel and .gbr naming are valid Gerber.
GERBER_EXTENSIONS = (
    ".gbr", ".ger", ".gtl", ".gbl", ".gtp", ".gbp",
    ".gto", ".gts", ".gbs", ".gm1",
)


def _digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def inspect_spi_native_cam_archive(archive_path: str | Path) -> dict:
    source = Path(archive_path)
    errors: list[str] = []
    output: dict = {
        "schema": SCHEMA,
        "archive_sha256": _digest(source.read_bytes()),
        "source_archive": source.name,
        "native_kicad_execution_claim": "native_exports_present_in_archive_not_independently_recomputed",
        "physical_assembly_validated": False,
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "release_authorized": False,
    }
    with zipfile.ZipFile(source, "r") as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)):
            errors.append("archive contains duplicate member names")
        if len(names) > 500:
            errors.append("archive has too many entries")
        for name in names:
            path = PurePosixPath(name)
            if (path.is_absolute() or "\\" in name
                    or any(part in ("", ".", "..") for part in path.parts)
                    or not name.startswith(PREFIX)):
                errors.append(f"unsafe archive member {name!r}")
        if errors:
            return {**output, "status": "blocked_integrity", "issues": errors}
        content = {name[len(PREFIX):]: archive.read(name) for name in names}
    sums = content.get("SHA256SUMS.txt", b"").decode("utf-8", errors="replace")
    records: dict[str, str] = {}
    for line in sums.splitlines():
        bits = line.split("  ", 1)
        if len(bits) != 2 or len(bits[0]) != 64 or bits[1] in records:
            errors.append(f"invalid or duplicated SHA256SUMS record: {line[:180]}")
            continue
        records[bits[1]] = bits[0]
    expected = set(content) - {"SHA256SUMS.txt"}
    if set(records) != expected:
        errors.append("SHA256SUMS does not cover all archive members exactly")
    for path in expected & records.keys():
        if records[path] != _digest(content[path]):
            errors.append(f"archive hash mismatch: {path}")
    for path in REQUIRED_SOURCE:
        if path not in content:
            errors.append(f"canonical source absent: {path}")
    native_receipt = {}
    if "verification.json" in content:
        try:
            native_receipt = json.loads(content["verification.json"])
            if native_receipt.get("result") != "pass":
                errors.append("native KiCad verifier receipt did not pass")
            if native_receipt.get("authority", {}).get("fabrication_ready") is not False:
                errors.append("native receipt has invalid fabrication authority")
            if native_receipt.get("authority", {}).get("power_on_ready") is not False:
                errors.append("native receipt has invalid power-on authority")
            version = native_receipt.get("toolchain", {}).get("kicad_cli", "")
            if not isinstance(version, str) or not version.startswith("9."):
                errors.append(f"required KiCad 9 CLI not evidenced: {version!r}")
            for role, rel in (
                ("pcb", "spi_flash_adapter_v1.kicad_pcb"),
                ("schematic", "spi_flash_adapter_v1.kicad_sch"),
                ("bom", "BOM.csv"),
                ("design_manifest", "design_manifest.json"),
            ):
                if rel in content and native_receipt.get("artifact_sha256", {}).get(role) != _digest(content[rel]):
                    errors.append(f"receipt source hash mismatch: {role}")
        except (ValueError, TypeError, AttributeError):
            errors.append("unparseable native verification receipt")
    gerbers = sorted(name for name in content if name.startswith("manufacturing/")
                     and name.lower().endswith(GERBER_EXTENSIONS))
    drills = sorted(name for name in content if name.startswith("manufacturing/")
                    and name.lower().endswith(".drl"))
    missing_layers = [
        layer for layer in REQUIRED_LAYERS
        if not any(f"-{layer}." in path or f"_{layer}." in path for path in gerbers)
    ]
    if missing_layers:
        errors.append("missing exported CAM layers: " + ", ".join(missing_layers))
    if len(drills) < 2:
        errors.append("plated and nonplated drill files are not both present")
    if any(b"%FS" not in content[path][:2000] for path in gerbers):
        errors.append("Gerber geometry header absent on one or more layers")
    if any(b"M48" not in content[path][:500] for path in drills):
        errors.append("Excellon drill header absent")
    position_files = [p for p in content if p.startswith("manufacturing/")
                      and p.endswith("-positions.csv")]
    if len(position_files) != 1:
        errors.append("expected exactly one initial FIT pick-and-place CSV")
    position_rows = []
    actual_placement_refs: list[str] = []
    expected_placement_refs: list[str] = []
    if "BOM.csv" in content:
        bom_rows = list(csv.DictReader(io.StringIO(content["BOM.csv"].decode("utf-8-sig"))))
        for row in bom_rows:
            if row.get("Initial Assembly") == "FIT":
                refs = (row.get("References") or "").split()
                expected_placement_refs.extend(ref for ref in refs if ref not in {"J1", "JP1"})
        if len(expected_placement_refs) != 14 or len(set(expected_placement_refs)) != 14:
            errors.append("reference BOM does not define fourteen unique SMT assembly positions")
    if len(position_files) == 1:
        raw = content[position_files[0]].decode("utf-8-sig", errors="replace")
        position_rows = list(csv.reader(io.StringIO(raw)))
        if not position_rows or len(position_rows) < 2:
            errors.append("placement export has no placed components")
        elif "Ref" not in position_rows[0]:
            errors.append("placement export has no KiCad Ref column")
        else:
            idx = position_rows[0].index("Ref")
            for row in position_rows[1:]:
                if idx >= len(row) or not row[idx].strip():
                    errors.append("placement export contains missing reference")
                else:
                    actual_placement_refs.append(row[idx].strip())
            if len(set(actual_placement_refs)) != len(actual_placement_refs):
                errors.append("placement file contains duplicate references")
            if {"R1", "R4"} & set(actual_placement_refs):
                errors.append("initially DNP rail link appears in placement")
            if set(actual_placement_refs) != set(expected_placement_refs):
                errors.append("pick-and-place reference set disagrees with the initial FIT surface-mount BOM")
    review_outputs = [p for p in content if p.startswith("review/")]
    if not any(p.endswith("-schematic.pdf") for p in review_outputs):
        errors.append("schematic PDF missing")
    if not any(p.endswith("-front-assembly.pdf") for p in review_outputs):
        errors.append("front assembly PDF missing")
    if not any(p.endswith(".svg") for p in review_outputs):
        errors.append("review SVG missing")
    output.update({
        "status": "review_package_intact_not_physically_authorized" if not errors else "blocked_integrity",
        "issues": sorted(set(errors)),
        "member_count": len(content),
        "verified_member_hashes": len(expected & records.keys()),
        "gerber_layers": gerbers,
        "drill_files": drills,
        "position_file": position_files[0] if len(position_files) == 1 else None,
        "placement_csv_rows_including_header": len(position_rows),
        "placement_references": sorted(actual_placement_refs),
        "expected_surface_mount_references": sorted(expected_placement_refs),
        "review_outputs": review_outputs,
        "native_receipt_kicad_cli_version": native_receipt.get("toolchain", {}).get("kicad_cli"),
        "native_receipt_pass": native_receipt.get("result") == "pass",
        "source_hashes_from_same_archive_checked": True,
        "vendor_footprints_physically_authenticated": False,
        "external_ee_signoff_recorded": False,
    })
    return output
