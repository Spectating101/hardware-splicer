"""Conservative spec-level timing budget for the grounded SPI virtual target.

This layer intentionally separates known source-bound delays from unresolved host/load terms.
It can quantify residual clock budget, but it cannot promote timing to validated until all
required terms and model/load checks are present.
"""

from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_timing_budget.v1"


def build_grounded_spi_timing_inputs() -> dict[str, Any]:
    """Return the frozen spec inputs used by the first virtual timing campaign.

    TXU0304 propagation bounds are from the TI Rev. A switching-characteristics table for
    VCCA=3.3 +/-0.3 V and VCCB=1.8 +/-0.15 V at -40..125 C.

    W25Q128JW tCLQV is tied to the previously captured Winbond Rev. G datasheet byte identity.
    It remains below independently reviewed/measured authority and is not, by itself, a path
    validation.
    """

    return {
        "schema_version": "hardware_splicer.spi_timing_inputs.v1",
        "requested_spi_clock_hz": 5_000_000,
        "txu0304": {
            "a_to_b_tpd_max_ns": 19.0,
            "b_to_a_tpd_max_ns": 15.0,
            "conditions": {
                "vcca_nominal_v": 3.3,
                "vcca_tolerance_v": 0.3,
                "vccb_nominal_v": 1.8,
                "vccb_tolerance_v": 0.15,
                "temperature_c": [-40, 125],
            },
            "source": {
                "publisher": "Texas Instruments",
                "document": "TXU0304 datasheet Rev. A",
                "section": "Switching Characteristics, VCCA = 3.3 +/- 0.3 V",
                "url": "https://www.ti.com/lit/ds/symlink/txu0304.pdf",
                "review_status": "manufacturer_document",
            },
        },
        "w25q128jw": {
            "clock_low_to_output_valid_max_ns": 6.0,
            "source": {
                "publisher": "Winbond Electronics",
                "document": "W25Q128JW Rev. G datasheet capture",
                "sha256": "sha256:4d065361637dcc10554a6384516e9e98cc000c986b03be874d4b5670b70e275e",
                "claim_status": "frozen_document_value_pending_independent_review",
            },
            "catalog_str_max_hz": 133_000_000,
            "catalog_rate_source": {
                "publisher": "Winbond Electronics",
                "document": "2025 Code Storage Flash product-selection guide",
                "part": "W25Q128JWSIQ",
                "url": (
                    "https://www.winbond.com/export/sites/winbond/product-selection-guide/file/"
                    "2025-Product-Selection-Guide-Winbond-Code-Storage-Flash-Memory.pdf"
                ),
            },
        },
        "host": {
            "input_setup_required_ns": None,
            "output_clock_to_data_valid_max_ns": None,
            "programmer_identity": None,
        },
        "interconnect": {
            "clock_skew_bound_ns": None,
            "signal_integrity_model_pass": False,
            "load_bound": None,
        },
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_spi_timing_budget(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate known timing terms and expose unresolved terms without inventing closure."""

    data = dict(inputs or build_grounded_spi_timing_inputs())
    requested_hz = _number(data.get("requested_spi_clock_hz"))
    if requested_hz is None or requested_hz <= 0:
        raise ValueError("requested_spi_clock_hz must be positive")

    period_ns = 1e9 / requested_hz
    half_period_ns = period_ns / 2.0

    txu = data.get("txu0304") if isinstance(data.get("txu0304"), Mapping) else {}
    dut = data.get("w25q128jw") if isinstance(data.get("w25q128jw"), Mapping) else {}
    host = data.get("host") if isinstance(data.get("host"), Mapping) else {}
    interconnect = data.get("interconnect") if isinstance(data.get("interconnect"), Mapping) else {}

    txu_ab_ns = _number(txu.get("a_to_b_tpd_max_ns"))
    txu_ba_ns = _number(txu.get("b_to_a_tpd_max_ns"))
    dut_tclqv_ns = _number(dut.get("clock_low_to_output_valid_max_ns"))
    host_setup_ns = _number(host.get("input_setup_required_ns"))
    host_output_ns = _number(host.get("output_clock_to_data_valid_max_ns"))
    skew_ns = _number(interconnect.get("clock_skew_bound_ns"))

    known_read_return_delay_ns = None
    if txu_ba_ns is not None and dut_tclqv_ns is not None:
        known_read_return_delay_ns = txu_ba_ns + dut_tclqv_ns

    known_read_halfcycle_residual_ns = (
        half_period_ns - known_read_return_delay_ns
        if known_read_return_delay_ns is not None
        else None
    )

    known_forward_translation_residual_ns = (
        half_period_ns - txu_ab_ns if txu_ab_ns is not None else None
    )

    unresolved: list[str] = []
    if host_setup_ns is None:
        unresolved.append("host_input_setup_required_ns")
    if host_output_ns is None:
        unresolved.append("host_output_clock_to_data_valid_max_ns")
    if skew_ns is None:
        unresolved.append("clock_skew_bound_ns")
    if not bool(interconnect.get("signal_integrity_model_pass")):
        unresolved.append("signal_integrity_model_pass")
    if interconnect.get("load_bound") in {None, ""}:
        unresolved.append("load_bound")

    catalog_max_hz = _number(dut.get("catalog_str_max_hz"))
    catalog_rate_exceeded = catalog_max_hz is not None and requested_hz > catalog_max_hz

    known_term_failure = bool(
        catalog_rate_exceeded
        or (known_read_halfcycle_residual_ns is not None and known_read_halfcycle_residual_ns <= 0)
        or (known_forward_translation_residual_ns is not None and known_forward_translation_residual_ns <= 0)
    )

    if known_term_failure:
        status = "failed_known_terms"
    elif unresolved:
        status = "blocked_incomplete_timing_model"
    else:
        # Even a complete arithmetic budget is still modeled/spec evidence, not bench proof.
        read_total_ns = (known_read_return_delay_ns or 0.0) + (host_setup_ns or 0.0) + (skew_ns or 0.0)
        forward_total_ns = (txu_ab_ns or 0.0) + (host_output_ns or 0.0) + (skew_ns or 0.0)
        status = "passed_modeled_timing" if max(read_total_ns, forward_total_ns) < half_period_ns else "failed_complete_budget"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "requested_spi_clock_hz": int(requested_hz),
        "period_ns": round(period_ns, 6),
        "half_period_ns": round(half_period_ns, 6),
        "known_terms": {
            "txu_a_to_b_tpd_max_ns": txu_ab_ns,
            "txu_b_to_a_tpd_max_ns": txu_ba_ns,
            "dut_clock_low_to_output_valid_max_ns": dut_tclqv_ns,
            "known_read_return_delay_ns": known_read_return_delay_ns,
            "known_read_halfcycle_residual_ns": (
                round(known_read_halfcycle_residual_ns, 6)
                if known_read_halfcycle_residual_ns is not None
                else None
            ),
            "known_forward_translation_residual_ns": (
                round(known_forward_translation_residual_ns, 6)
                if known_forward_translation_residual_ns is not None
                else None
            ),
        },
        "unresolved_terms": unresolved,
        "catalog_str_max_hz": int(catalog_max_hz) if catalog_max_hz is not None else None,
        "catalog_rate_exceeded": catalog_rate_exceeded,
        "timing_validated": False,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
        "note": (
            "Residual half-cycle time is diagnostic only; propagation delay, flash output-valid, "
            "host setup/launch, skew, and signal-integrity/load terms must be evaluated together."
        ),
    }
