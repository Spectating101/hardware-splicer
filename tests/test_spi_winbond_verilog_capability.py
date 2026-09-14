import io
import json
import zipfile

import pytest

from hardware_splicer.spi_winbond_verilog_capability import (
    WinbondVerilogCapabilityError,
    audit_winbond_verilog_capabilities,
)
from hardware_splicer.vendor_model_capture import inspect_vendor_model_bytes


MODEL_ID = "w25q128jw-q-verilog-da02-aag072"
SOURCE_URL = (
    "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
    "__locale=en&xmlPath=/support/resources/.content/item/DA02-AAG072.html&level=2"
)


def _source(*, include_9f: bool = True, include_jedec: bool = True) -> str:
    command = "localparam [7:0] CMD_JEDEC = 8'h9F;" if include_9f else "localparam [7:0] CMD = 8'h05;"
    jedec = "localparam [23:0] JEDEC_ID = 24'hEF6018;" if include_jedec else "localparam [23:0] JEDEC_ID = 24'h000000;"
    return f"""`timescale 1ns/1ps
module W25Q128JW_Q(
    input wire CSn,
    input wire CLK,
    input wire DI,
    output reg DO
);
{command}
{jedec}
reg [7:0] command_shift;
always @(posedge CLK) begin
    if (!CSn) begin
        command_shift <= {{command_shift[6:0], DI}};
        case (command_shift)
            CMD_JEDEC: DO <= JEDEC_ID[23];
            default: DO <= 1'b0;
        endcase
    end
end
endmodule
"""


def _capture(source: str) -> tuple[bytes, dict]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("models/W25Q128JW_Q.v", source)
    payload = buffer.getvalue()
    manifest = inspect_vendor_model_bytes(
        payload,
        model_id=MODEL_ID,
        source_url=SOURCE_URL,
        expected_hosts=["www.winbond.com"],
        filename="W25Q128JW-Q-Verilog.zip",
        expected_model_kind="Verilog",
        content_type="application/zip",
    )
    return payload, manifest


def test_static_audit_finds_bounded_jedec_candidate_without_granting_execution_credit() -> None:
    payload, manifest = _capture(_source())
    result = audit_winbond_verilog_capabilities(payload, manifest)

    assert result["module_names"] == ["W25Q128JW_Q"]
    assert result["command_9f_literal_present"] is True
    assert result["jedec_ef6018_literal_present"] is True
    assert result["has_behavioral_logic"] is True
    assert result["has_case_logic"] is True
    assert result["jedec_id_read_9f_source_candidate"] is True
    assert result["jedec_id_read_9f_supported"] is False
    assert result["execution_credit_granted"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert result["physical_authority_granted"] is False


def test_static_audit_fails_closed_when_command_marker_is_missing() -> None:
    payload, manifest = _capture(_source(include_9f=False))
    result = audit_winbond_verilog_capabilities(payload, manifest)

    assert result["command_9f_literal_present"] is False
    assert result["jedec_id_read_9f_source_candidate"] is False
    assert result["jedec_id_read_9f_supported"] is False


def test_static_audit_rejects_outer_hash_mismatch() -> None:
    payload, manifest = _capture(_source())
    manifest = json.loads(json.dumps(manifest))
    manifest["sha256"] = "sha256:" + "0" * 64

    with pytest.raises(WinbondVerilogCapabilityError, match="outer hash mismatch"):
        audit_winbond_verilog_capabilities(payload, manifest)
