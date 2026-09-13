import io
import zipfile

import pytest

from hardware_splicer.vendor_model_capture import (
    VendorModelCaptureError,
    inspect_vendor_model_bytes,
    validate_vendor_url,
)


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return stream.getvalue()


def test_capture_manifest_hashes_outer_zip_and_members_without_authority_promotion() -> None:
    payload = _zip_bytes({"model.ibs": b"[IBIS Ver] 4.2\n", "readme.txt": b"fixture"})

    manifest = inspect_vendor_model_bytes(
        payload,
        model_id="txu0304-ibis-scem787",
        source_url="https://www.ti.com/lit/zip/SCEM787",
        expected_hosts=["www.ti.com"],
        filename="SCEM787.ZIP",
        content_type="application/zip",
    )

    assert manifest["capture_status"] == "captured_hashed_unreviewed"
    assert manifest["sha256"].startswith("sha256:")
    assert manifest["archive_type"] == "zip"
    assert {row["path"] for row in manifest["archive_members"]} == {"model.ibs", "readme.txt"}
    assert all(row["sha256"].startswith("sha256:") for row in manifest["archive_members"])
    assert manifest["measured_evidence_present"] is False
    assert manifest["physical_correctness"] == "UNPROVEN"
    assert manifest["physical_authority_granted"] is False
    assert manifest["authority_effect"] == "none"


def test_capture_rejects_html_download_interstitial() -> None:
    with pytest.raises(VendorModelCaptureError, match="HTML"):
        inspect_vendor_model_bytes(
            b"<!doctype html><html><body>sign in</body></html>",
            model_id="w25q128jwsiq-ibis-da03-aag072",
            source_url="https://www.winbond.com/download/model",
            expected_hosts=["www.winbond.com"],
            filename="model.zip",
            content_type="text/html",
        )


def test_capture_rejects_wrong_or_insecure_vendor_host() -> None:
    with pytest.raises(VendorModelCaptureError):
        validate_vendor_url("http://www.ti.com/lit/zip/SCEM787", ["www.ti.com"])
    with pytest.raises(VendorModelCaptureError):
        validate_vendor_url("https://example.com/SCEM787.zip", ["www.ti.com"])


def test_capture_rejects_unsafe_zip_member_path() -> None:
    payload = _zip_bytes({"../escape.ibs": b"bad"})

    with pytest.raises(VendorModelCaptureError, match="unsafe ZIP member path"):
        inspect_vendor_model_bytes(
            payload,
            model_id="txu0304-ibis-scem787",
            source_url="https://www.ti.com/lit/zip/SCEM787",
            expected_hosts=["www.ti.com"],
            filename="SCEM787.ZIP",
        )


def test_expected_sha256_mismatch_fails_closed() -> None:
    with pytest.raises(VendorModelCaptureError, match="SHA-256"):
        inspect_vendor_model_bytes(
            b"[IBIS Ver] 4.2\n",
            model_id="fixture",
            source_url="https://www.ti.com/model.ibs",
            expected_hosts=["www.ti.com"],
            filename="model.ibs",
            expected_sha256="sha256:" + "0" * 64,
        )
