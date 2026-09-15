"""Bounded host-side execution for the SPI flash adapter physical campaign.

The runner intentionally exposes only the JEDEC-ID command (0x9f).  It does not
control bench power, translator OE, or project authority.  Those remain physical
operator actions governed by the revision-bound handoff.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Protocol


SPI_JEDEC_RESULT_SCHEMA = "hardware_splicer.spi_read_only_jedec_id.v1"
JEDEC_ID_COMMAND = b"\x9f"
MAX_CAMPAIGN_CLOCK_HZ = 5_000_000
DEFAULT_EXPECTED_ID = bytes.fromhex("ef6018")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class SpiTransport(Protocol):
    """Minimum transport contract needed by the read-only transaction."""

    identity: str

    def exchange(self, payload: bytes) -> bytes: ...

    def close(self) -> None: ...


@dataclass
class PyFtdiTransport:
    """FT232H-compatible transport, loaded lazily for provider workstations."""

    url: str
    frequency_hz: int
    chip_select: int = 0

    def __post_init__(self) -> None:
        try:
            from pyftdi.spi import SpiController
        except ImportError as exc:  # pragma: no cover - provider dependency
            raise RuntimeError("pyftdi is required for the pyftdi transport") from exc
        self._controller = SpiController(cs_count=max(1, self.chip_select + 1))
        try:
            self._controller.configure(self.url)
            self._port = self._controller.get_port(
                cs=self.chip_select,
                freq=self.frequency_hz,
                mode=0,
            )
        except Exception:
            self._controller.terminate()
            raise
        self.identity = f"pyftdi:{self.url}:cs{self.chip_select}"

    def exchange(self, payload: bytes) -> bytes:
        return bytes(self._port.exchange(payload, duplex=True))

    def close(self) -> None:
        self._controller.terminate()


@dataclass
class SpiDevTransport:
    """Linux spidev transport, loaded lazily for provider workstations."""

    bus: int
    device: int
    frequency_hz: int

    def __post_init__(self) -> None:
        try:
            import spidev
        except ImportError as exc:  # pragma: no cover - provider dependency
            raise RuntimeError("spidev is required for the spidev transport") from exc
        self._spi = spidev.SpiDev()
        try:
            self._spi.open(self.bus, self.device)
            self._spi.mode = 0
            self._spi.bits_per_word = 8
            self._spi.lsbfirst = False
            self._spi.cshigh = False
            self._spi.no_cs = False
            self._spi.threewire = False
            self._spi.loop = False
            self._spi.max_speed_hz = self.frequency_hz
        except Exception:
            self._spi.close()
            raise
        self.identity = f"spidev:{self.bus}.{self.device}"

    def exchange(self, payload: bytes) -> bytes:
        return bytes(self._spi.xfer2(list(payload)))

    def close(self) -> None:
        self._spi.close()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _self_sha256() -> str:
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def validate_physical_execution_context(
    *, campaign_sha256: str | None, test_article_id: str | None, operator_id: str | None
) -> None:
    """Validate all physical identities before a transport may be opened."""

    if not campaign_sha256 or not _SHA256_RE.fullmatch(campaign_sha256):
        raise ValueError("physical execution requires a sha256 campaign identity")
    if not str(test_article_id or "").strip():
        raise ValueError("physical execution requires test_article_id")
    if not str(operator_id or "").strip():
        raise ValueError("physical execution requires operator_id")


def run_read_only_jedec_id(
    transport: SpiTransport,
    *,
    frequency_hz: int,
    trials: int = 10,
    expected_id: bytes = DEFAULT_EXPECTED_ID,
    clock: Callable[[], str] = _utc_now,
    delay: Callable[[float], None] = time.sleep,
    capture_origin: str = "physical_test_article",
    campaign_sha256: str | None = None,
    test_article_id: str | None = None,
    operator_id: str | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute only 0x9f and return a non-authorizing raw transaction record."""

    if not 1 <= frequency_hz <= MAX_CAMPAIGN_CLOCK_HZ:
        raise ValueError(
            f"frequency_hz must be between 1 and {MAX_CAMPAIGN_CLOCK_HZ}"
        )
    if not 1 <= trials <= 100:
        raise ValueError("trials must be between 1 and 100")
    if len(expected_id) != 3:
        raise ValueError("expected_id must contain exactly three bytes")
    if capture_origin not in {"physical_test_article", "ci_mock"}:
        raise ValueError("capture_origin must be physical_test_article or ci_mock")
    if capture_origin == "physical_test_article":
        if expected_id != DEFAULT_EXPECTED_ID:
            raise ValueError("physical campaign expected_id is fixed to ef6018")
        validate_physical_execution_context(
            campaign_sha256=campaign_sha256,
            test_article_id=test_article_id,
            operator_id=operator_id,
        )
        if frequency_hz == MAX_CAMPAIGN_CLOCK_HZ and trials < 10:
            raise ValueError("5 MHz physical campaign execution requires at least 10 trials")

    responses: list[dict[str, Any]] = []
    failure_reason: str | None = None
    tx = JEDEC_ID_COMMAND + b"\x00\x00\x00"
    try:
        for index in range(trials):
            captured_at = clock()
            try:
                rx = bytes(transport.exchange(tx))
            except Exception as exc:  # physical I/O failures must survive in the log
                failure_reason = f"transport_error:{type(exc).__name__}:{exc}"
                responses.append(
                    {
                        "trial": index + 1,
                        "captured_at": captured_at,
                        "tx_hex": tx.hex(),
                        "rx_hex": None,
                        "response_hex": None,
                        "matches_expected": False,
                        "failure_reason": failure_reason,
                    }
                )
                if progress is not None:
                    progress(dict(responses[-1]))
                break
            if len(rx) != len(tx):
                failure_reason = (
                    f"short_exchange:received_{len(rx)}_bytes_expected_{len(tx)}"
                )
                responses.append(
                    {
                        "trial": index + 1,
                        "captured_at": captured_at,
                        "tx_hex": tx.hex(),
                        "rx_hex": rx.hex(),
                        "response_hex": rx[1:].hex() if len(rx) > 1 else "",
                        "matches_expected": False,
                        "failure_reason": failure_reason,
                    }
                )
                if progress is not None:
                    progress(dict(responses[-1]))
                break
            payload = rx[1:]
            responses.append(
                {
                    "trial": index + 1,
                    "captured_at": captured_at,
                    "tx_hex": tx.hex(),
                    "rx_hex": rx.hex(),
                    "response_hex": payload.hex(),
                    "matches_expected": payload == expected_id,
                }
            )
            if progress is not None:
                progress(dict(responses[-1]))
            if payload != expected_id:
                failure_reason = "jedec_id_mismatch"
                break
            if index + 1 < trials:
                delay(0.01)
    finally:
        try:
            transport.close()
        except Exception as exc:  # pragma: no cover - provider I/O failure
            failure_reason = failure_reason or f"transport_close_error:{type(exc).__name__}:{exc}"

    passed = len(responses) == trials and failure_reason is None
    return {
        "schema_version": SPI_JEDEC_RESULT_SCHEMA,
        "procedure_id": "hs.spi.read-only-jedec-id.v1",
        "command_hex": JEDEC_ID_COMMAND.hex(),
        "expected_response_hex": expected_id.hex(),
        "response_hex_by_trial": [
            row["response_hex"]
            for row in responses
            if isinstance(row.get("response_hex"), str) and len(row["response_hex"]) == 6
        ],
        "requested_trial_count": trials,
        "attempted_trial_count": len(responses),
        "completed_trial_count": sum(
            1 for row in responses if isinstance(row.get("rx_hex"), str) and len(row["rx_hex"]) == 8
        ),
        "configured_clock_hz": frequency_hz,
        "measured_clock_hz": None,
        "measured_clock_requires_waveform_evidence": True,
        "spi_mode": 0,
        "transport_identity": transport.identity,
        "campaign_sha256": campaign_sha256,
        "test_article_id": test_article_id,
        "operator_id": operator_id,
        "transactions": responses,
        "passed": passed,
        "result_scope": "bounded_read_only_transaction_only",
        "campaign_acceptance": False,
        "failure_reason": failure_reason,
        "capture_origin": capture_origin,
        "simulated": capture_origin != "physical_test_article",
        "write_program_erase_commands_exposed": False,
        "runner_sha256": _self_sha256(),
        "eligible_for_physical_evidence_import": False,
        "server_attestation_still_required": True,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def build_dry_run_plan(*, frequency_hz: int, trials: int, expected_id: bytes) -> dict[str, Any]:
    """Describe the exact bounded transfer without opening a device."""

    if not 1 <= frequency_hz <= MAX_CAMPAIGN_CLOCK_HZ:
        raise ValueError(
            f"frequency_hz must be between 1 and {MAX_CAMPAIGN_CLOCK_HZ}"
        )
    if not 1 <= trials <= 100:
        raise ValueError("trials must be between 1 and 100")
    if len(expected_id) != 3:
        raise ValueError("expected_id must contain exactly three bytes")
    return {
        "schema_version": SPI_JEDEC_RESULT_SCHEMA,
        "execution_state": "dry_run_no_device_opened",
        "procedure_id": "hs.spi.read-only-jedec-id.v1",
        "tx_hex": "9f000000",
        "expected_response_hex": expected_id.hex(),
        "requested_trial_count": trials,
        "clock_hz": frequency_hz,
        "spi_mode": 0,
        "simulated": True,
        "eligible_for_physical_evidence_import": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"
