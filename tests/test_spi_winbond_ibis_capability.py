import io
import json
import zipfile

import pytest

from hardware_splicer.spi_winbond_ibis_capability import (
    WinbondIbisCapabilityError,
    audit_winbond_ibis_capabilities,
)
from hardware_splicer.vendor_model_capture import inspect_vendor_model_bytes


MODEL_ID = "w25q128jwsiq-ibis-da03-aag072"
SOURCE_URL = (
    "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
    "__locale=en&xmlPath=/support/resources/.content/item/DA03-AAG072.html&level=3"
)
IBIS = """[IBIS Ver] 5.1
[File Name] W25Q128JWSIQ.ibs
[Component] W25Q128JWSIQ
[Manufacturer] Winbond
[Pin] signal_name model_name R_pin L_pin C_pin
1 CS# W25Q128JW_IN 0 0 0
2 DO W25Q128JW_OUT 0 0 0
[Model] W25Q128JW_IN
Model_type Input
[GND Clamp]
0 0
[Model] W25Q128JW_OUT
Model_type Output
[Pullup]
0 0
[Pulldown]
0 0
[Ramp]
dV/dt_r 1/1n
[End]
"""


def _capture(source: str = IBIS) -> tuple[bytes, dict]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("W25Q128JWSIQ.ibs", source)
    payload = buffer.getvalue()
    manifest = inspect_vendor_model_bytes(
        payload,
        model_id=MODEL_ID,
        source_url=SOURCE_URL,
        expected_hosts=["www.winbond.com"],
        filename="W25Q128JWSIQ-IBIS.zip",
        expected_model_kind="IBIS",
        content_type="application/zip",
    )
    return payload, manifest


def test_winbond_ibis_audit_establishes_signal_integrity_eligibility_only() -> None:
    payload, manifest = _capture()
    result = audit_winbond_ibis_capabilities(payload, manifest)

    assert result["target_family_marker_present"] is True
    assert result["signal_integrity_structure_present"] is True
    assert result["eligible_for_later_signal_integrity_execution"] is True
    assert result["execution_credit_granted"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_winbond_ibis_audit_fails_closed_for_wrong_family() -> None:
    payload, manifest = _capture(IBIS.replace("W25Q128JW", "OTHER_PART"))
    result = audit_winbond_ibis_capabilities(payload, manifest)

    assert result["target_family_marker_present"] is False
    assert result["eligible_for_later_signal_integrity_execution"] is False


def test_winbond_ibis_audit_rejects_outer_hash_mismatch() -> None:
    payload, manifest = _capture()
    manifest = json.loads(json.dumps(manifest))
    manifest["sha256"] = "sha256:" + "f" * 64

    with pytest.raises(WinbondIbisCapabilityError, match="outer hash mismatch"):
        audit_winbond_ibis_capabilities(payload, manifest)
