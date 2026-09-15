import io
import zipfile

import pytest

from hardware_splicer.vendor_model_capture import (
    VendorModelCaptureError,
    capture_vendor_model_file,
)


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return stream.getvalue()


def test_local_import_hashes_valid_ibis_without_leaking_full_path(tmp_path) -> None:
    model_file = tmp_path / "SCEM787.ZIP"
    model_file.write_bytes(
        _zip_bytes({"txu0304.ibs": b"[IBIS Ver] 4.2\n[Component] TXU0304\n"})
    )

    payload, manifest = capture_vendor_model_file(
        path=model_file,
        model_id="txu0304-ibis-scem787",
        source_url="https://www.ti.com/lit/zip/SCEM787",
        expected_hosts=["www.ti.com"],
        expected_model_kind="IBIS",
    )

    assert payload == model_file.read_bytes()
    assert manifest["acquisition_method"] == "local_file_import"
    assert manifest["local_input_filename"] == "SCEM787.ZIP"
    assert str(tmp_path) not in str(manifest)
    assert manifest["recognized_expected_model_file_count"] == 1
    assert manifest["sha256"].startswith("sha256:")
    assert manifest["physical_correctness"] == "UNPROVEN"
    assert manifest["physical_authority_granted"] is False


def test_local_import_supports_login_mediated_winbond_landing_url(tmp_path) -> None:
    model_file = tmp_path / "W25Q128JW_Q.zip"
    model_file.write_bytes(
        _zip_bytes({"w25q128jw.v": b"module W25Q128JW(input CSn); endmodule\n"})
    )

    _, manifest = capture_vendor_model_file(
        path=model_file,
        model_id="w25q128jw-q-verilog-da02-aag072",
        source_url=(
            "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
            "__locale=en&xmlPath=/support/resources/.content/item/DA02-AAG072.html&level=2"
        ),
        expected_hosts=["www.winbond.com"],
        expected_model_kind="Verilog",
    )

    assert manifest["capture_status"] == "captured_hashed_unreviewed"
    assert manifest["expected_model_kind"] == "Verilog"
    assert manifest["recognized_expected_model_file_count"] == 1
    assert manifest["acquisition_method"] == "local_file_import"


def test_local_import_rejects_wrong_model_kind(tmp_path) -> None:
    model_file = tmp_path / "wrong.zip"
    model_file.write_bytes(
        _zip_bytes({"model.v": b"module wrong(input x); endmodule\n"})
    )

    with pytest.raises(VendorModelCaptureError, match="no recognized IBIS"):
        capture_vendor_model_file(
            path=model_file,
            model_id="txu0304-ibis-scem787",
            source_url="https://www.ti.com/lit/zip/SCEM787",
            expected_hosts=["www.ti.com"],
            expected_model_kind="IBIS",
        )


def test_local_import_rejects_oversize_before_reading_for_credit(tmp_path) -> None:
    model_file = tmp_path / "oversize.ibs"
    model_file.write_bytes(b"[IBIS Ver] 4.2\n[Component] X\n" + b"x" * 128)

    with pytest.raises(VendorModelCaptureError, match="byte ceiling"):
        capture_vendor_model_file(
            path=model_file,
            model_id="fixture",
            source_url="https://www.ti.com/model.ibs",
            expected_hosts=["www.ti.com"],
            expected_model_kind="IBIS",
            max_bytes=32,
        )


def test_local_import_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(VendorModelCaptureError, match="does not exist"):
        capture_vendor_model_file(
            path=tmp_path / "missing.zip",
            model_id="fixture",
            source_url="https://www.ti.com/model.zip",
            expected_hosts=["www.ti.com"],
            expected_model_kind="IBIS",
        )
