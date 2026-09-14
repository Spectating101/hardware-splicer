import io
import zipfile

import pytest

from hardware_splicer.spi_vendor_model_capability_audit import (
    VendorModelCapabilityAuditError,
    audit_txu0304_ibis_capabilities,
)
from hardware_splicer.vendor_model_capture import inspect_vendor_model_bytes


def _capture(ibis_text: str) -> tuple[bytes, dict]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("txu0304.ibs", ibis_text)
    payload = buffer.getvalue()
    manifest = inspect_vendor_model_bytes(
        payload,
        model_id="txu0304-ibis-scem787",
        source_url="https://www.ti.com/lit/zip/SCEM787",
        expected_hosts=["www.ti.com"],
        filename="SCEM787.ZIP",
        expected_model_kind="IBIS",
    )
    return payload, manifest


def test_ibis_structure_does_not_promote_rail_absent_isolation() -> None:
    payload, manifest = _capture(
        """[IBIS Ver] 5.1
[Component] TXU0304
[Pin]
1 A1 TX_OUT
[Model] TX_OUT
Model_type Output
[Pullup]
0 0 0 0
[Pulldown]
0 0 0 0
[Power Clamp]
0 0 0 0
[Ramp]
dV/dt_r 1/1n 1/1n 1/1n
"""
    )

    result = audit_txu0304_ibis_capabilities(payload, manifest)

    assert result["signal_integrity_structure_present"] is True
    assert result["eligible_for_later_signal_integrity_execution"] is True
    assert result["rail_absent_isolation_claim_supported"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_three_state_or_textual_power_markers_still_do_not_prove_vcc_disconnect() -> None:
    payload, manifest = _capture(
        """[IBIS Ver] 5.1
| output enable and VCC disconnect are mentioned in vendor comments
[Component] TXU0304
[Pin]
1 A1 TX_3STATE
[Model] TX_3STATE
Model_type 3-state
[Pullup]
0 0 0 0
[Pulldown]
0 0 0 0
"""
    )

    result = audit_txu0304_ibis_capabilities(payload, manifest)

    assert result["three_state_model_present"] is True
    assert "vcc disconnect" in result["textual_power_state_markers"]
    assert result["rail_absent_isolation_claim_supported"] is False


def test_outer_hash_mismatch_fails_closed() -> None:
    payload, manifest = _capture(
        """[IBIS Ver] 5.1
[Component] TXU0304
[Pin]
1 A1 TX_OUT
[Model] TX_OUT
Model_type Output
[Pullup]
0 0 0 0
"""
    )
    manifest["sha256"] = "sha256:" + "0" * 64

    with pytest.raises(VendorModelCapabilityAuditError, match="outer hash mismatch"):
        audit_txu0304_ibis_capabilities(payload, manifest)
