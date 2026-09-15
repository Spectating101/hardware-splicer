import hashlib
import io
import zipfile

import pytest

from hardware_splicer.captured_model_materialization import (
    CapturedModelMaterializationError,
    extract_bound_model_member,
)


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _zip(member_path: str, member: bytes) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_path, member)
    return stream.getvalue()


def _manifest(outer: bytes, member_path: str, member: bytes) -> dict:
    return {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": "fixture",
        "expected_model_kind": "IBIS",
        "filename": "fixture.zip",
        "size_bytes": len(outer),
        "sha256": _sha(outer),
        "archive_type": "zip",
        "recognized_model_files": [
            {"path": member_path, "model_kind": "IBIS", "sha256": _sha(member)}
        ],
    }


def test_exact_zip_member_is_materialized_with_both_hashes_bound() -> None:
    member = b"[IBIS Ver] 4.2\n[Component] X\n"
    outer = _zip("models/x.ibs", member)
    manifest = _manifest(outer, "models/x.ibs", member)

    extracted, evidence = extract_bound_model_member(
        outer, manifest, member_path="models/x.ibs"
    )

    assert extracted == member
    assert evidence["member_sha256"] == _sha(member)
    assert evidence["outer_sha256"] == _sha(outer)
    assert evidence["physical_authority_granted"] is False


def test_outer_payload_mismatch_is_rejected_before_archive_access() -> None:
    member = b"model"
    outer = _zip("x.ibs", member)
    manifest = _manifest(outer, "x.ibs", member)

    with pytest.raises(CapturedModelMaterializationError, match="outer payload SHA-256"):
        extract_bound_model_member(outer + b"changed", manifest, member_path="x.ibs")


def test_unrecognized_member_cannot_be_materialized() -> None:
    member = b"model"
    outer = _zip("x.ibs", member)
    manifest = _manifest(outer, "x.ibs", member)

    with pytest.raises(CapturedModelMaterializationError, match="not a recognized model"):
        extract_bound_model_member(outer, manifest, member_path="readme.txt")


def test_direct_capture_requires_exact_filename() -> None:
    member = b"module W25Q; endmodule\n"
    manifest = {
        "schema_version": "hardware_splicer.vendor_model_capture.v1",
        "model_id": "verilog",
        "expected_model_kind": "Verilog",
        "filename": "model.v",
        "size_bytes": len(member),
        "sha256": _sha(member),
        "archive_type": "none",
        "recognized_model_files": [
            {"path": "model.v", "model_kind": "Verilog", "sha256": _sha(member)}
        ],
    }

    extracted, evidence = extract_bound_model_member(member, manifest, member_path="model.v")
    assert extracted == member
    assert evidence["model_kind"] == "Verilog"

    with pytest.raises(CapturedModelMaterializationError):
        extract_bound_model_member(member, manifest, member_path="other.v")
