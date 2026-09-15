"""Read-only SPI behavioral oracle for derived virtual-lab experiments.

This is not a Winbond model and must never be presented as one. It implements only the
preregistered behavior needed to test the HS pipeline: chip-select framing and JEDEC-ID 0x9F.
"""

from __future__ import annotations

from typing import Any, Iterable

SCHEMA_VERSION = "hardware_splicer.spi_behavioral_oracle.v1"

JEDEC_ID = (0xEF, 0x60, 0x18)


def transact(command: int, payload: Iterable[int] = (), *, cs_asserted: bool = True) -> dict[str, Any]:
    data = [int(x) & 0xFF for x in payload]
    if not cs_asserted:
        return _result("ignored_cs_not_asserted", [], False)
    if int(command) & 0xFF == 0x9F:
        return _result("read_jedec_id", list(JEDEC_ID), False)
    return _result("unsupported_readonly_command", [], False, command=int(command) & 0xFF, payload=data)


def _result(operation: str, response: list[int], state_mutated: bool, **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "oracle_id": "hs-readonly-w25q-like-oracle-v1",
        "evidence_class": "derived_surrogate_only",
        "vendor_model": False,
        "eligible_for_vendor_model_campaign_credit": False,
        "operation": operation,
        "response_bytes": response,
        "state_mutated": state_mutated,
        "write_or_erase_side_effect": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
        **extra,
    }
