"""Bounded, content-addressed ingestion for engineering project sources.

This module accepts raw bytes through canonical base64 transport, computes the file
identity on the server, classifies the source conservatively, and stores the bytes in a
project-scoped content-addressed blob store. Classification never raises authority and
unsupported formats remain inventory-only instead of receiving invented parser output.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import mimetypes
import os
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .machine_project import AuthorityState
from .project_store import default_project_root, validate_project_id


ENGINEERING_SOURCE_INGESTION_SCHEMA = "hardware_splicer.engineering_source_ingestion.v1"
MAX_ENGINEERING_SOURCE_BYTES = 16 * 1024 * 1024
MAX_ENGINEERING_SOURCE_BASE64_CHARACTERS = 4 * ((MAX_ENGINEERING_SOURCE_BYTES + 2) // 3)
MAX_SOURCE_FILENAME_CHARACTERS = 255


class EngineeringSourceKind(str, Enum):
    ROBOT_MODEL = "robot_model"
    STEP_CAD = "step_cad"
    KICAD_DESIGN = "kicad_design"
    FIRMWARE_ARCHIVE = "firmware_archive"
    JSON_DESCRIPTOR = "json_descriptor"
    CSV_DATA = "csv_data"
    TEXT_DOCUMENT = "text_document"
    PDF_DOCUMENT = "pdf_document"
    IMAGE = "image"
    VIDEO = "video"
    ARCHIVE = "archive"
    UNKNOWN = "unknown"


class ParserDisposition(str, Enum):
    STRUCTURED = "structured"
    INVENTORY_ONLY = "inventory_only"


class SourceIngestionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class EngineeringSourceIngestionRequest(SourceIngestionModel):
    project_id: str = Field(min_length=1, max_length=96)
    filename: str = Field(min_length=1, max_length=MAX_SOURCE_FILENAME_CHARACTERS)
    content_base64: str = Field(
        min_length=1,
        max_length=MAX_ENGINEERING_SOURCE_BASE64_CHARACTERS,
    )
    declared_media_type: str | None = Field(default=None, max_length=255)
    authority_ceiling: AuthorityState = AuthorityState.DECLARED
    captured_at: str | None = Field(default=None, max_length=128)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("project_id")
    @classmethod
    def validate_project_identifier(cls, value: str) -> str:
        return validate_project_id(value)

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        resolved = value.strip()
        if not resolved:
            raise ValueError("filename must not be blank")
        if "\x00" in resolved:
            raise ValueError("filename must not contain NUL")
        return resolved

    @field_validator("authority_ceiling")
    @classmethod
    def keep_upload_authority_fail_closed(cls, value: AuthorityState) -> AuthorityState:
        allowed = {
            AuthorityState.UNKNOWN,
            AuthorityState.PROPOSED,
            AuthorityState.DECLARED,
        }
        if value not in allowed:
            raise ValueError(
                "uploaded project files cannot enter above declared authority"
            )
        return value


class EngineeringSourceClassification(SourceIngestionModel):
    kind: EngineeringSourceKind
    media_type: str
    source_type: str
    parser_disposition: ParserDisposition
    parser_route: str | None = None
    structured_format: str | None = None
    confidence: str = "bounded"
    limitations: list[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EngineeringSourceIngestionResult(SourceIngestionModel):
    schema_version: str = ENGINEERING_SOURCE_INGESTION_SCHEMA
    project_id: str
    source_id: str
    original_filename: str
    content_hash: str
    size_bytes: int = Field(ge=0)
    blob_ref: str
    duplicate_blob: bool = False
    bytes_retained: bool = True
    classification: EngineeringSourceClassification
    authority_ceiling: AuthorityState
    source_descriptor: Dict[str, Any]
    automatic_authorization: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _decode_content(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("content_base64 is not valid canonical base64") from exc
    if len(decoded) > MAX_ENGINEERING_SOURCE_BYTES:
        raise ValueError(
            f"decoded engineering source exceeds {MAX_ENGINEERING_SOURCE_BYTES} bytes"
        )
    return decoded


def _extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def _looks_textual(content: bytes) -> bool:
    sample = content[:8192]
    if not sample:
        return True
    if b"\x00" in sample:
        return False
    printable = sum(
        byte in b"\t\n\r" or 32 <= byte <= 126 or byte >= 128
        for byte in sample
    )
    return printable / len(sample) >= 0.90


def _media_type(
    filename: str,
    content: bytes,
    declared_media_type: str | None,
) -> tuple[str, Dict[str, Any]]:
    guessed, _ = mimetypes.guess_type(filename)
    detected: str | None = None
    if content.startswith(b"%PDF-"):
        detected = "application/pdf"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = "image/png"
    elif content.startswith(b"\xff\xd8\xff"):
        detected = "image/jpeg"
    elif content.startswith((b"GIF87a", b"GIF89a")):
        detected = "image/gif"
    elif content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        detected = "image/webp"
    elif content.startswith(b"PK\x03\x04"):
        detected = "application/zip"
    elif len(content) >= 12 and content[4:8] == b"ftyp":
        detected = "video/mp4"
    metadata = {
        "declared_media_type": declared_media_type,
        "extension_media_type": guessed,
        "signature_media_type": detected,
    }
    return detected or guessed or declared_media_type or "application/octet-stream", metadata


def classify_engineering_source(
    filename: str,
    content: bytes,
    *,
    declared_media_type: str | None = None,
) -> EngineeringSourceClassification:
    """Classify one bounded source without claiming successful deep parsing."""

    extension = _extension(filename)
    media_type, media_metadata = _media_type(
        filename,
        content,
        declared_media_type,
    )
    header = content[:8192].lstrip()
    lower_header = header.lower()

    if extension == ".urdf" or b"<robot" in lower_header:
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.ROBOT_MODEL,
            media_type=media_type,
            source_type="cad",
            parser_disposition=ParserDisposition.STRUCTURED,
            parser_route="robot_model_import",
            structured_format="urdf",
            limitations=[
                "Classification does not prove model validity or physical agreement."
            ],
            metadata=media_metadata,
        )
    if extension == ".sdf" or b"<sdf" in lower_header:
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.ROBOT_MODEL,
            media_type=media_type,
            source_type="cad",
            parser_disposition=ParserDisposition.STRUCTURED,
            parser_route="robot_model_import",
            structured_format="sdf",
            limitations=[
                "Classification does not prove model validity or physical agreement."
            ],
            metadata=media_metadata,
        )
    if extension == ".mjcf" or b"<mujoco" in lower_header:
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.ROBOT_MODEL,
            media_type=media_type,
            source_type="cad",
            parser_disposition=ParserDisposition.STRUCTURED,
            parser_route="robot_model_import",
            structured_format="mjcf",
            limitations=[
                "Classification does not prove model validity or physical agreement."
            ],
            metadata=media_metadata,
        )
    if extension in {".step", ".stp"} or b"ISO-10303-21" in content[:512].upper():
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.STEP_CAD,
            media_type=media_type,
            source_type="cad",
            parser_disposition=ParserDisposition.STRUCTURED,
            parser_route="step_geometry",
            structured_format="step",
            limitations=[
                "The existing STEP path is bounded identity and coarse-envelope analysis, not full BREP or FEA."
            ],
            metadata=media_metadata,
        )
    if extension in {
        ".kicad_pro",
        ".kicad_sch",
        ".kicad_pcb",
        ".kicad_sym",
        ".kicad_mod",
    }:
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.KICAD_DESIGN,
            media_type=media_type,
            source_type="pcb",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=[
                "The file is retained and registered but is not automatically treated as a validated KiCad project."
            ],
            metadata=media_metadata,
        )
    if extension in {".hex", ".bin", ".elf", ".uf2", ".ino"}:
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.FIRMWARE_ARCHIVE,
            media_type=media_type,
            source_type="other",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=[
                "Firmware bytes are not built, flashed, executed, or granted device authority."
            ],
            metadata=media_metadata,
        )
    if extension in {".zip", ".tar", ".gz", ".tgz", ".7z"} or content.startswith(
        b"PK\x03\x04"
    ):
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.ARCHIVE,
            media_type=media_type,
            source_type="other",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=[
                "Archives are not extracted until traversal, symlink, expansion-ratio, and aggregate-size controls are implemented."
            ],
            metadata=media_metadata,
        )
    if extension == ".json" or header.startswith((b"{", b"[")):
        try:
            json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return EngineeringSourceClassification(
                kind=EngineeringSourceKind.UNKNOWN,
                media_type=media_type,
                source_type="other",
                parser_disposition=ParserDisposition.INVENTORY_ONLY,
                limitations=["JSON-like content was invalid and was not adapted."],
                metadata={**media_metadata, "json_valid": False},
            )
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.JSON_DESCRIPTOR,
            media_type="application/json",
            source_type="other",
            parser_disposition=ParserDisposition.STRUCTURED,
            parser_route="engineering_source_descriptor",
            structured_format="json",
            limitations=[
                "Valid JSON is not automatically trusted as a valid engineering-source schema."
            ],
            metadata={**media_metadata, "json_valid": True},
        )
    if extension == ".csv":
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.CSV_DATA,
            media_type=media_type,
            source_type="other",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=["CSV semantics require an explicit adapter or user mapping."],
            metadata=media_metadata,
        )
    if content.startswith(b"%PDF-") or extension == ".pdf":
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.PDF_DOCUMENT,
            media_type="application/pdf",
            source_type="manual",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=[
                "PDF bytes are retained but no document claims are extracted automatically."
            ],
            metadata=media_metadata,
        )
    if media_type.startswith("image/"):
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.IMAGE,
            media_type=media_type,
            source_type="photo",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=[
                "Image content is not interpreted as measured or verified evidence."
            ],
            metadata=media_metadata,
        )
    if media_type.startswith("video/"):
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.VIDEO,
            media_type=media_type,
            source_type="video",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=[
                "Video content requires explicit selection, timestamp ranges, and bounded observation records."
            ],
            metadata=media_metadata,
        )
    if extension in {".txt", ".md", ".rst", ".log"} or _looks_textual(content):
        return EngineeringSourceClassification(
            kind=EngineeringSourceKind.TEXT_DOCUMENT,
            media_type=media_type if media_type != "application/octet-stream" else "text/plain",
            source_type="other",
            parser_disposition=ParserDisposition.INVENTORY_ONLY,
            limitations=[
                "Text is retained without automatically promoting its statements into engineering claims."
            ],
            metadata=media_metadata,
        )
    return EngineeringSourceClassification(
        kind=EngineeringSourceKind.UNKNOWN,
        media_type=media_type,
        source_type="other",
        parser_disposition=ParserDisposition.INVENTORY_ONLY,
        limitations=["No bounded parser is registered for this format."],
        metadata=media_metadata,
    )


def _assert_no_symlink(path: Path, root: Path) -> None:
    current = root
    if current.is_symlink():
        raise ValueError("engineering source root must not be a symlink")
    relative = path.relative_to(root)
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ValueError(f"engineering source path contains symlink: {current}")


def _write_content_addressed_blob(
    root: Path,
    project_id: str,
    digest_hex: str,
    content: bytes,
) -> tuple[str, bool]:
    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    project_dir = root / validate_project_id(project_id)
    blob_dir = project_dir / "sources" / "sha256" / digest_hex[:2]
    target = blob_dir / digest_hex
    _assert_no_symlink(blob_dir, root)
    blob_dir.mkdir(parents=True, exist_ok=True)
    _assert_no_symlink(target, root)

    if target.exists():
        existing = target.read_bytes()
        if hashlib.sha256(existing).hexdigest() != digest_hex:
            raise ValueError("existing content-addressed blob failed hash verification")
        return target.relative_to(project_dir).as_posix(), True

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{digest_hex}.",
        suffix=".tmp",
        dir=blob_dir,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if hashlib.sha256(temp_path.read_bytes()).hexdigest() != digest_hex:
            raise ValueError("temporary engineering source failed hash verification")
        os.replace(temp_path, target)
    finally:
        temp_path.unlink(missing_ok=True)
    return target.relative_to(project_dir).as_posix(), False


def ingest_engineering_source(
    request: EngineeringSourceIngestionRequest | Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
) -> EngineeringSourceIngestionResult:
    """Hash, classify, and persist one project source without raising authority."""

    resolved = (
        request
        if isinstance(request, EngineeringSourceIngestionRequest)
        else EngineeringSourceIngestionRequest.model_validate(request)
    )
    content = _decode_content(resolved.content_base64)
    digest_hex = hashlib.sha256(content).hexdigest()
    content_hash = f"sha256:{digest_hex}"
    classification = classify_engineering_source(
        resolved.filename,
        content,
        declared_media_type=resolved.declared_media_type,
    )
    root = Path(project_root) if project_root is not None else default_project_root()
    blob_ref, duplicate = _write_content_addressed_blob(
        root,
        resolved.project_id,
        digest_hex,
        content,
    )
    source_id = f"upload-{digest_hex[:20]}"
    source_descriptor: Dict[str, Any] = {
        "source_id": source_id,
        "source_type": classification.source_type,
        "uri": f"hs-project://{resolved.project_id}/{blob_ref}",
        "revision": content_hash,
        "content_hash": content_hash,
        "authority_ceiling": resolved.authority_ceiling.value,
        "metadata": {
            **dict(resolved.metadata),
            "original_filename": resolved.filename,
            "captured_at": resolved.captured_at,
            "size_bytes": len(content),
            "media_type": classification.media_type,
            "ingestion_schema": ENGINEERING_SOURCE_INGESTION_SCHEMA,
            "source_kind": classification.kind.value,
            "parser_disposition": classification.parser_disposition.value,
            "parser_route": classification.parser_route,
            "structured_format": classification.structured_format,
            "blob_ref": blob_ref,
            "server_computed_hash": True,
            "bytes_retained": True,
            "automatic_authorization": False,
            "limitations": classification.limitations,
        },
    }
    return EngineeringSourceIngestionResult(
        project_id=resolved.project_id,
        source_id=source_id,
        original_filename=resolved.filename,
        content_hash=content_hash,
        size_bytes=len(content),
        blob_ref=blob_ref,
        duplicate_blob=duplicate,
        bytes_retained=True,
        classification=classification,
        authority_ceiling=resolved.authority_ceiling,
        source_descriptor=source_descriptor,
        automatic_authorization=False,
        metadata={
            "server_computed_hash": True,
            "content_addressed_storage": True,
            "raw_bytes_in_response": False,
            "fabrication_authorized": False,
            "flash_authorized": False,
            "power_on_authorized": False,
            "motion_authorized": False,
            "release_authorized": False,
        },
    )
