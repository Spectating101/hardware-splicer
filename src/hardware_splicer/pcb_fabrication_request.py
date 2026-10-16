"""Vendor-neutral PCB fabrication/assembly request package.

This produces a deterministic request object from already generated manufacturing
artifacts. It does not choose a vendor, quote money, submit an order, or claim
that the manufacturing files are physically correct.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from dataclasses import dataclass
from typing import Any, Mapping

from .fabrication_operator import FabricationValidationError


@dataclass(frozen=True)
class PcbFabricationSpec:
    quantity: int
    layer_count: int
    thickness_mm: float
    copper_oz: float
    surface_finish: str
    soldermask: str
    silkscreen: str
    assembly_requested: bool = False

    def validate(self) -> None:
        if type(self.quantity) is not int or not 1 <= self.quantity <= 100000:
            raise FabricationValidationError("PCB quantity must be 1..100000")
        if type(self.layer_count) is not int or not 1 <= self.layer_count <= 64:
            raise FabricationValidationError("PCB layer_count must be 1..64")
        for value, field, low, high in (
            (self.thickness_mm, "thickness_mm", 0.1, 20.0),
            (self.copper_oz, "copper_oz", 0.25, 20.0),
        ):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)) or not low <= float(value) <= high:
                raise FabricationValidationError(f"PCB {field} is outside bounded range")
        _text(self.surface_finish, "surface_finish", 64)
        _text(self.soldermask, "soldermask", 64)
        _text(self.silkscreen, "silkscreen", 64)


class PcbFabricationRequestBuilder:
    def build(
        self,
        *,
        project_id: str,
        revision_id: str,
        spec: PcbFabricationSpec,
        gerbers: Mapping[str, bytes],
        drill_files: Mapping[str, bytes],
        bom_csv: bytes | None = None,
        positions_csv: bytes | None = None,
        notes: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(spec, PcbFabricationSpec):
            raise FabricationValidationError("PCB fabrication request requires PcbFabricationSpec")
        spec.validate()
        pid = _id(project_id, "project_id")
        rid = _id(revision_id, "revision_id")
        files: dict[str, bytes] = {}
        for name, content in gerbers.items():
            safe = _filename(name, suffixes=(".gbr", ".ger", ".pho"))
            files[f"gerbers/{safe}"] = _bytes(content, "Gerber")
        if not gerbers:
            raise FabricationValidationError("PCB fabrication request requires Gerber files")
        for name, content in drill_files.items():
            safe = _filename(name, suffixes=(".drl", ".xln", ".txt"))
            files[f"drill/{safe}"] = _bytes(content, "drill")
        if not drill_files:
            raise FabricationValidationError("PCB fabrication request requires drill files")
        if spec.assembly_requested:
            if bom_csv is None or positions_csv is None:
                raise FabricationValidationError("assembly request requires BOM and component positions")
        if bom_csv is not None:
            files["assembly/bom.csv"] = _bytes(bom_csv, "BOM")
        if positions_csv is not None:
            files["assembly/positions.csv"] = _bytes(positions_csv, "positions")

        manifest_files = {
            path: {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
            for path, content in sorted(files.items())
        }
        manifest = {
            "schema": "hardware_splicer.pcb_fabrication_request.v1",
            "project_id": pid,
            "revision_id": rid,
            "spec": {
                "quantity": spec.quantity,
                "layer_count": spec.layer_count,
                "thickness_mm": float(spec.thickness_mm),
                "copper_oz": float(spec.copper_oz),
                "surface_finish": spec.surface_finish,
                "soldermask": spec.soldermask,
                "silkscreen": spec.silkscreen,
                "assembly_requested": bool(spec.assembly_requested),
            },
            "files": manifest_files,
            "notes": _canonical(notes or {}),
            "vendor": None,
            "quote": None,
            "order_submitted": False,
            "physical_correctness": "UNPROVEN",
        }
        manifest_bytes = (json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            _write(archive, "PCB_REQUEST.json", manifest_bytes)
            for path, content in sorted(files.items()):
                _write(archive, path, content)
        package = buffer.getvalue()
        return {
            "manifest": manifest,
            "package": package,
            "package_sha256": hashlib.sha256(package).hexdigest(),
            "physical_correctness": "UNPROVEN",
            "order_submitted": False,
        }


def _write(archive: zipfile.ZipFile, path: str, content: bytes) -> None:
    info = zipfile.ZipInfo(path)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


def _filename(value: Any, *, suffixes: tuple[str, ...]) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError("manufacturing filename must be text")
    cleaned = value.strip().replace("\\", "/").split("/")[-1]
    if not cleaned or cleaned in {".", ".."} or len(cleaned) > 180 or any(ord(ch) < 32 for ch in cleaned):
        raise FabricationValidationError("manufacturing filename is invalid")
    if not cleaned.lower().endswith(suffixes):
        raise FabricationValidationError("manufacturing file has unsupported suffix")
    return cleaned


def _bytes(value: Any, field: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)) or not value:
        raise FabricationValidationError(f"{field} content must be non-empty bytes")
    if len(value) > 128 * 1024 * 1024:
        raise FabricationValidationError(f"{field} content exceeds bounded size")
    return bytes(value)


def _canonical(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise FabricationValidationError("PCB request notes must be canonical JSON") from exc


def _id(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise FabricationValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 128 or any(not (ch.isalnum() or ch in "._:-") for ch in cleaned):
        raise FabricationValidationError(f"{field} must be a bounded identifier")
    return cleaned


def _text(value: Any, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum or any(ord(ch) < 32 for ch in value):
        raise FabricationValidationError(f"PCB {field} must be bounded printable text")
    return value.strip()
