from __future__ import annotations

import json
import subprocess
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from hardware_splicer.spi_remote_fct import (
    PyFtdiTransport,
    SpiDevTransport,
    build_dry_run_plan,
    run_read_only_jedec_id,
)


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "run_spi_read_only_jedec_id.py"


@dataclass
class FakeTransport:
    replies: list[bytes]
    identity: str = "fixture:fake-spi"
    commands: list[bytes] = field(default_factory=list)
    closed: bool = False

    def exchange(self, payload: bytes) -> bytes:
        self.commands.append(payload)
        return self.replies.pop(0)

    def close(self) -> None:
        self.closed = True


def test_runner_can_only_issue_read_only_jedec_id() -> None:
    transport = FakeTransport([bytes.fromhex("00ef6018")] * 3)
    result = run_read_only_jedec_id(
        transport,
        frequency_hz=5_000_000,
        trials=3,
        clock=lambda: "2026-09-16T00:00:00+00:00",
        delay=lambda _: None,
        capture_origin="ci_mock",
    )

    assert result["passed"] is True
    assert result["simulated"] is True
    assert result["command_hex"] == "9f"
    assert result["physical_authority_granted"] is False
    assert result["eligible_for_physical_evidence_import"] is False
    assert transport.commands == [bytes.fromhex("9f000000")] * 3
    assert transport.closed is True


def test_mismatched_identity_is_visible_and_fails() -> None:
    transport = FakeTransport(
        [bytes.fromhex("00ef6018"), bytes.fromhex("00ffffff")]
    )
    result = run_read_only_jedec_id(
        transport,
        frequency_hz=1_000_000,
        trials=2,
        clock=lambda: "2026-09-16T00:00:00+00:00",
        delay=lambda _: None,
        capture_origin="ci_mock",
    )

    assert result["passed"] is False
    assert result["response_hex_by_trial"] == ["ef6018", "ffffff"]
    assert result["failure_reason"] == "jedec_id_mismatch"


@pytest.mark.parametrize("frequency", [0, 5_000_001])
def test_frequency_outside_campaign_boundary_is_rejected(frequency: int) -> None:
    transport = FakeTransport([bytes.fromhex("00ef6018")])
    with pytest.raises(ValueError, match="frequency_hz"):
        run_read_only_jedec_id(transport, frequency_hz=frequency)
    assert transport.commands == []


def test_transport_short_read_fails_and_still_closes() -> None:
    transport = FakeTransport([bytes.fromhex("00ef60")])
    result = run_read_only_jedec_id(
        transport, frequency_hz=1_000_000, capture_origin="ci_mock"
    )
    assert result["passed"] is False
    assert result["failure_reason"] == "short_exchange:received_3_bytes_expected_4"
    assert result["attempted_trial_count"] == 1
    assert result["transactions"][0]["rx_hex"] == "00ef60"
    assert transport.closed is True


def test_dry_run_plan_is_explicitly_non_physical() -> None:
    plan = build_dry_run_plan(
        frequency_hz=1_000_000,
        trials=10,
        expected_id=bytes.fromhex("ef6018"),
    )
    assert plan["execution_state"] == "dry_run_no_device_opened"
    assert plan["tx_hex"] == "9f000000"
    assert plan["simulated"] is True
    assert plan["physical_authority_granted"] is False


def test_physical_origin_requires_campaign_article_and_operator_identity() -> None:
    transport = FakeTransport([bytes.fromhex("00ef6018")])
    with pytest.raises(ValueError, match="campaign identity"):
        run_read_only_jedec_id(
            transport,
            frequency_hz=1_000_000,
            capture_origin="physical_test_article",
        )
    assert transport.commands == []


def test_physical_campaign_fixes_expected_identity_and_full_speed_trial_count() -> None:
    transport = FakeTransport([bytes.fromhex("00ef6018")] * 10)
    context = {
        "campaign_sha256": "sha256:" + "a" * 64,
        "test_article_id": "article-001",
        "operator_id": "operator-001",
    }
    with pytest.raises(ValueError, match="expected_id is fixed"):
        run_read_only_jedec_id(
            transport,
            frequency_hz=1_000_000,
            expected_id=bytes.fromhex("ffffff"),
            **context,
        )
    with pytest.raises(ValueError, match="at least 10 trials"):
        run_read_only_jedec_id(
            transport,
            frequency_hz=5_000_000,
            trials=9,
            **context,
        )
    assert transport.commands == []


def test_cli_defaults_to_no_device_dry_run(tmp_path: Path) -> None:
    output = tmp_path / "dry-run.json"
    result = subprocess.run(
        [sys.executable, str(CLI), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(output.read_text())["execution_state"] == "dry_run_no_device_opened"


def test_cli_dry_run_refuses_to_overwrite_existing_evidence(tmp_path: Path) -> None:
    output = tmp_path / "dry-run.json"
    output.write_text("original\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CLI), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "refusing to overwrite evidence" in result.stderr
    assert output.read_text(encoding="utf-8") == "original\n"


def test_cli_rejects_live_execution_without_acknowledgements_before_io(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--execute",
            "--transport",
            "spidev",
            "--spidev-bus",
            "0",
            "--spidev-device",
            "0",
            "--output",
            str(tmp_path / "should-not-exist.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "operator-confirm-bench-authorized" in result.stderr
    assert "spidev is required" not in result.stderr


def test_cli_rejects_too_few_full_speed_trials_before_transport_open(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--execute",
            "--operator-confirm-bench-authorized",
            "--transport",
            "spidev",
            "--spidev-bus",
            "0",
            "--spidev-device",
            "0",
            "--frequency-hz",
            "5000000",
            "--trials",
            "1",
            "--campaign-sha256",
            "sha256:" + "a" * 64,
            "--test-article-id",
            "article-001",
            "--operator-id",
            "operator-001",
            "--output",
            str(tmp_path / "should-not-exist.jsonl"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "at least 10 trials" in result.stderr
    assert "spidev is required" not in result.stderr
    assert not (tmp_path / "should-not-exist.jsonl").exists()


def test_cli_has_no_arbitrary_opcode_surface(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "--opcode",
            "06",
            "--output",
            str(tmp_path / "should-not-exist.json"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "unrecognized arguments: --opcode 06" in result.stderr


def test_spidev_transport_explicitly_disables_unsafe_modes(monkeypatch) -> None:
    class Device:
        def open(self, bus, device):
            self.opened = (bus, device)

        def xfer2(self, payload):
            self.transferred = payload
            return [0x00, 0xEF, 0x60, 0x18]

        def close(self):
            self.closed = True

    device = Device()
    monkeypatch.setitem(sys.modules, "spidev", types.SimpleNamespace(SpiDev=lambda: device))
    transport = SpiDevTransport(0, 1, 1_000_000)
    assert device.opened == (0, 1)
    assert device.mode == 0
    assert device.bits_per_word == 8
    assert device.lsbfirst is False
    assert device.cshigh is False
    assert device.no_cs is False
    assert device.threewire is False
    assert device.loop is False
    assert transport.exchange(bytes.fromhex("9f000000")) == bytes.fromhex("00ef6018")


def test_pyftdi_transport_uses_one_full_duplex_exchange(monkeypatch) -> None:
    class Port:
        def exchange(self, payload, *, duplex):
            self.call = (payload, duplex)
            return bytes.fromhex("00ef6018")

    port = Port()

    class Controller:
        def __init__(self, *, cs_count):
            self.cs_count = cs_count

        def configure(self, url):
            self.url = url

        def get_port(self, *, cs, freq, mode):
            self.settings = (cs, freq, mode)
            return port

        def terminate(self):
            self.closed = True

    spi_module = types.ModuleType("pyftdi.spi")
    spi_module.SpiController = Controller
    monkeypatch.setitem(sys.modules, "pyftdi", types.ModuleType("pyftdi"))
    monkeypatch.setitem(sys.modules, "pyftdi.spi", spi_module)
    transport = PyFtdiTransport("ftdi://test/1", 5_000_000)
    response = transport.exchange(bytes.fromhex("9f000000"))
    assert response == bytes.fromhex("00ef6018")
    assert port.call == (bytes.fromhex("9f000000"), True)
    assert transport._controller.settings == (0, 5_000_000, 0)
