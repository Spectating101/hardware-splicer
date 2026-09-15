import io
import subprocess
import zipfile

from hardware_splicer.spi_vendor_verilog_preflight import preflight_winbond_verilog_model
from hardware_splicer.vendor_model_capture import inspect_vendor_model_bytes


MODEL_ID = "w25q128jw-q-verilog-da02-aag072"
SOURCE_URL = (
    "https://www.winbond.com/hq/support/documentation/downloadV2022.jsp?"
    "__locale=en&xmlPath=/support/resources/.content/item/DA02-AAG072.html&level=2"
)
SOURCE = """`timescale 1ns/1ps
module W25Q128JW_Q(
    input wire CSn,
    input wire CLK,
    input wire DI,
    output reg DO
);
localparam [7:0] CMD_JEDEC = 8'h9F;
localparam [23:0] JEDEC_ID = 24'hEF6018;
reg [7:0] command_shift;
always @(posedge CLK) begin
    if (!CSn) begin
        command_shift <= {command_shift[6:0], DI};
        case (command_shift)
            CMD_JEDEC: DO <= JEDEC_ID[23];
            default: DO <= 1'b0;
        endcase
    end
end
endmodule
"""


def _capture() -> tuple[bytes, dict]:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("models/W25Q128JW_Q.v", SOURCE)
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


def test_preflight_compile_pass_makes_source_execution_eligible(monkeypatch) -> None:
    payload, manifest = _capture()
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(list(argv))
        if "-V" in argv:
            return subprocess.CompletedProcess(argv, 0, b"Icarus Verilog version 12.0\n", b"")
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    monkeypatch.setattr("hardware_splicer.spi_vendor_verilog_preflight.subprocess.run", fake_run)
    result = preflight_winbond_verilog_model(
        payload,
        manifest,
        iverilog_path="/usr/bin/iverilog",
    )

    assert result["status"] == "eligible_for_bound_jedec_testbench"
    assert result["compile_pass"] is True
    assert result["static_source_candidate"] is True
    assert result["jedec_id_read_9f_supported"] is True
    assert result["execution_credit_granted"] is False
    assert result["physical_correctness"] == "UNPROVEN"
    assert len(calls) == 2
    assert calls[1][1:3] == ["-g2012", "-tnull"]


def test_preflight_compile_failure_never_unlocks_execution(monkeypatch) -> None:
    payload, manifest = _capture()

    def fake_run(argv, **kwargs):
        if "-V" in argv:
            return subprocess.CompletedProcess(argv, 0, b"Icarus Verilog version 12.0\n", b"")
        return subprocess.CompletedProcess(argv, 1, b"", b"syntax error\n")

    monkeypatch.setattr("hardware_splicer.spi_vendor_verilog_preflight.subprocess.run", fake_run)
    result = preflight_winbond_verilog_model(
        payload,
        manifest,
        iverilog_path="/usr/bin/iverilog",
    )

    assert result["status"] == "compile_failed"
    assert result["compile_pass"] is False
    assert result["jedec_id_read_9f_supported"] is False
    assert result["execution_credit_granted"] is False


def test_preflight_reports_missing_tool_without_promoting_capability(monkeypatch) -> None:
    payload, manifest = _capture()
    monkeypatch.setattr("hardware_splicer.spi_vendor_verilog_preflight.shutil.which", lambda _: None)

    result = preflight_winbond_verilog_model(payload, manifest)

    assert result["status"] == "tool_unavailable"
    assert result["compile_pass"] is False
    assert result["jedec_id_read_9f_supported"] is False
    assert result["execution_credit_granted"] is False
