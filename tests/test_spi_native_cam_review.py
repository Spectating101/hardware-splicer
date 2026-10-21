"""Independent ZIP inspection; fake fixture proves validator fail-closed paths.

No fake ZIP is presented as a native KiCad output or source-board validation.
"""
from __future__ import annotations
import hashlib
import io
import json
import zipfile
from pathlib import Path
from hardware_splicer.spi_native_cam_review import (
    REQUIRED_LAYERS, REQUIRED_SOURCE, inspect_spi_native_cam_archive,
)


def _make_archive(path: Path, changes=None, *, missing=()):
    root = "spi_flash_adapter_v1/"
    files = {key: b"synthetic fixture (not physical manufacturing)" for key in REQUIRED_SOURCE}
    smt_refs = ["C1", "C2", "C3", "C4", "C5", "C6",
                "R2", "R3", "R5", "R6", "R7", "U1", "U2", "U3"]
    files["BOM.csv"] = (
        "References,Initial Assembly\\n"
        + " ".join(smt_refs) + ",FIT\\n"
        + "J1 JP1,FIT\\nR1 R4,DNP\\n"
    ).encode()
    receipt = {
        "result": "pass",
        "toolchain": {"kicad_cli": "9.0.9"},
        "authority": {"fabrication_ready": False, "power_on_ready": False},
        "artifact_sha256": {
            role: hashlib.sha256(files[name]).hexdigest()
            for role, name in (
                ("pcb", "spi_flash_adapter_v1.kicad_pcb"),
                ("schematic", "spi_flash_adapter_v1.kicad_sch"),
                ("bom", "BOM.csv"),
                ("design_manifest", "design_manifest.json"),
            )
        },
    }
    files["verification.json"] = json.dumps(receipt).encode()
    for layer in REQUIRED_LAYERS:
        files[f"manufacturing/spi_flash_adapter_v1-{layer}.gbr"] = b"%FSLAX46Y46*%\nM02*\n"
    files["manufacturing/spi_flash_adapter_v1-PTH.drl"] = b"M48\nM30\n"
    files["manufacturing/spi_flash_adapter_v1-NPTH.drl"] = b"M48\nM30\n"
    files["manufacturing/spi_flash_adapter_v1-positions.csv"] = (
        "Ref,Val,X,Y,Side\\n"
        + "".join(f"{ref},component,1,2,top\\n" for ref in smt_refs)
    ).encode()
    files["review/spi_flash_adapter_v1-schematic.pdf"] = b"%PDF-1.5 synthetic"
    files["review/spi_flash_adapter_v1-front-assembly.pdf"] = b"%PDF-1.5 synthetic"
    files["review/spi_flash_adapter_v1-top.svg"] = b"<svg/>"
    for key, value in (changes or {}).items():
        files[key] = value
    for key in missing:
        files.pop(key, None)
    files["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {key}\n"
        for key, content in sorted(files.items())
    ).encode()
    with zipfile.ZipFile(path, "w") as stream:
        for key, value in files.items():
            stream.writestr(root + key, value)
    return path


def test_synthetic_archive_structure_yields_review_only(tmp_path):
    report = inspect_spi_native_cam_archive(_make_archive(tmp_path / "sample.zip"))
    assert report["status"] == "review_package_intact_not_physically_authorized"
    assert not report["issues"]
    assert len(report["gerber_layers"]) == 8
    assert len(report["drill_files"]) == 2
    assert not report["fabrication_authorized"]
    assert not report["physical_assembly_validated"]


def test_missing_edge_layer_is_detected_even_when_checksums_are_valid(tmp_path):
    report = inspect_spi_native_cam_archive(
        _make_archive(tmp_path / "sample.zip", missing=[
            "manufacturing/spi_flash_adapter_v1-Edge_Cuts.gbr"
        ])
    )
    assert report["status"] == "blocked_integrity"
    assert any("Edge_Cuts" in x for x in report["issues"])


def test_dnp_part_in_placement_is_detected(tmp_path):
    report = inspect_spi_native_cam_archive(_make_archive(
        tmp_path / "sample.zip",
        changes={"manufacturing/spi_flash_adapter_v1-positions.csv":
                 b"Ref,Val,X,Y,Side\nR1,0R,1,2,top\n"}
    ))
    assert any("DNP" in issue for issue in report["issues"])


def test_modified_pcb_cannot_hide_behind_native_receipt(tmp_path):
    report = inspect_spi_native_cam_archive(_make_archive(
        tmp_path / "sample.zip",
        changes={"spi_flash_adapter_v1.kicad_pcb": b"tampered"}
    ))
    assert any("receipt source hash mismatch: pcb" in issue for issue in report["issues"])


def test_archive_integrity_tampering_detected(tmp_path):
    archive = _make_archive(tmp_path / "sample.zip")
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(archive) as src, zipfile.ZipFile(tampered, "w") as dst:
        for entry in src.namelist():
            contents = src.read(entry)
            if entry.endswith("B_Cu.gbr"):
                contents += b"tampered"
            dst.writestr(entry, contents)
    report = inspect_spi_native_cam_archive(tampered)
    assert any("archive hash mismatch" in issue for issue in report["issues"])


def test_missing_native_kicad9_authority_is_blocked(tmp_path):
    path = _make_archive(tmp_path / "sample.zip")
    with zipfile.ZipFile(path) as src:
        contents = {k.removeprefix("spi_flash_adapter_v1/"): src.read(k)
                    for k in src.namelist()}
    native = json.loads(contents["verification.json"])
    native["toolchain"]["kicad_cli"] = "7.0.11"
    contents["verification.json"] = json.dumps(native).encode()
    contents.pop("SHA256SUMS.txt")
    contents["SHA256SUMS.txt"] = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {key}\n"
        for key, payload in sorted(contents.items())
    ).encode()
    alternate = tmp_path / "old.zip"
    with zipfile.ZipFile(alternate, "w") as dst:
        for key, data in contents.items():
            dst.writestr("spi_flash_adapter_v1/" + key, data)
    report = inspect_spi_native_cam_archive(alternate)
    assert report["status"] == "blocked_integrity"
    assert any("KiCad 9" in x for x in report["issues"])

def test_native_protel_gerber_extension_naming_is_accepted(tmp_path):
    extensions = {
        "F_Cu": "gtl", "B_Cu": "gbl", "F_Mask": "gts",
        "B_Mask": "gbs", "F_Paste": "gtp", "B_Paste": "gbp",
        "F_Silkscreen": "gto", "Edge_Cuts": "gm1",
    }
    extra = {f"manufacturing/spi_flash_adapter_v1-{name}.{ext}":
             b"%FSLAX46Y46*%\\nM02*\\n"
             for name, ext in extensions.items()}
    missing = [f"manufacturing/spi_flash_adapter_v1-{name}.gbr" for name in extensions]
    result = inspect_spi_native_cam_archive(_make_archive(
        tmp_path / "protel.zip", changes=extra, missing=missing))
    assert result["status"] == "review_package_intact_not_physically_authorized", result["issues"]
    assert len(result["gerber_layers"]) == 8


def test_incomplete_surface_mount_placement_is_rejected(tmp_path):
    raw = "Ref,Val,X,Y,Side\\n" + "".join(
        f"{ref},component,1,2,top\\n" for ref in
        ["C1", "C2", "C3", "C4", "C5", "C6",
         "R2", "R3", "R5", "R6", "R7", "U1", "U2"]
    )
    result = inspect_spi_native_cam_archive(_make_archive(
        tmp_path / "wrong-placements.zip",
        changes={"manufacturing/spi_flash_adapter_v1-positions.csv": raw.encode()}
    ))
    assert result["status"] == "blocked_integrity"
    assert any("pick-and-place" in issue for issue in result["issues"])
