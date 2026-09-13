"""Conservative 1.8-V virtual-rail budget for the SPI adapter target."""

from __future__ import annotations

from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_power_budget.v1"


def build_grounded_spi_power_inputs() -> dict[str, Any]:
    """Return source-bound known terms without inventing a worst-case DUT load."""

    return {
        "schema_version": "hardware_splicer.spi_power_inputs.v1",
        "regulator": {
            "part": "TLV75518PDBVR",
            "output_nominal_v": 1.8,
            "output_min_v": 1.773,
            "output_max_v": 1.827,
            "rated_output_current_ma": 500.0,
            "minimum_output_capacitance_uf": 1.0,
            "soft_start_present": True,
            "source": {
                "publisher": "Texas Instruments",
                "url": "https://www.ti.com/product/TLV755P/part-details/TLV75518PDBVR",
                "review_status": "manufacturer_product_page",
            },
        },
        "dut": {
            "part": "W25Q128JWSIQ",
            # Product-family marketing material reports a low active-read current, but this is
            # intentionally not promoted into a worst-case rail requirement.
            "active_read_current_typical_ma": 1.0,
            "worst_case_current_ma": None,
            "transient_current_bound_ma": None,
            "source": {
                "publisher": "Winbond Electronics",
                "family": "W25Q128JW",
                "authority_note": "typical/family value only; not a worst-case design current",
            },
        },
        "translator": {
            "part": "TXU0304PWR",
            "supply_current_max_ma": 0.008,
            "source": {
                "publisher": "Texas Instruments",
                "url": "https://www.ti.com/product/TXU0304",
                "review_status": "manufacturer_product_page_parametric",
            },
        },
        "implementation": {
            "selected_output_capacitance_uf": None,
            "selected_input_capacitance_uf": None,
            "sequencing_policy_bound": False,
            "protection_policy_bound": False,
            "pcb_power_path_bound": False,
        },
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_spi_power_budget(inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = dict(inputs or build_grounded_spi_power_inputs())
    regulator = data.get("regulator") if isinstance(data.get("regulator"), Mapping) else {}
    dut = data.get("dut") if isinstance(data.get("dut"), Mapping) else {}
    translator = data.get("translator") if isinstance(data.get("translator"), Mapping) else {}
    implementation = (
        data.get("implementation") if isinstance(data.get("implementation"), Mapping) else {}
    )

    capacity_ma = _number(regulator.get("rated_output_current_ma"))
    dut_worst_ma = _number(dut.get("worst_case_current_ma"))
    transient_ma = _number(dut.get("transient_current_bound_ma"))
    translator_ma = _number(translator.get("supply_current_max_ma"))
    selected_cout_uf = _number(implementation.get("selected_output_capacitance_uf"))
    minimum_cout_uf = _number(regulator.get("minimum_output_capacitance_uf"))

    unresolved: list[str] = []
    if dut_worst_ma is None:
        unresolved.append("dut_worst_case_current_ma")
    if transient_ma is None:
        unresolved.append("dut_transient_current_bound_ma")
    if selected_cout_uf is None:
        unresolved.append("selected_output_capacitance_uf")
    if not bool(implementation.get("sequencing_policy_bound")):
        unresolved.append("sequencing_policy_bound")
    if not bool(implementation.get("protection_policy_bound")):
        unresolved.append("protection_policy_bound")
    if not bool(implementation.get("pcb_power_path_bound")):
        unresolved.append("pcb_power_path_bound")

    known_required_ma = None
    if dut_worst_ma is not None and translator_ma is not None:
        known_required_ma = dut_worst_ma + translator_ma

    capacity_margin_ma = (
        capacity_ma - known_required_ma
        if capacity_ma is not None and known_required_ma is not None
        else None
    )

    fail_reasons: list[str] = []
    if capacity_margin_ma is not None and capacity_margin_ma < 0:
        fail_reasons.append("steady_state_current_capacity_exceeded")
    if (
        selected_cout_uf is not None
        and minimum_cout_uf is not None
        and selected_cout_uf < minimum_cout_uf
    ):
        fail_reasons.append("output_capacitance_below_regulator_minimum")

    if fail_reasons:
        status = "failed_known_terms"
    elif unresolved:
        status = "blocked_incomplete_power_model"
    else:
        status = "passed_modeled_power_budget"

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "known_terms": {
            "regulator_capacity_ma": capacity_ma,
            "dut_worst_case_current_ma": dut_worst_ma,
            "dut_transient_current_bound_ma": transient_ma,
            "translator_supply_current_max_ma": translator_ma,
            "steady_state_required_ma": known_required_ma,
            "steady_state_capacity_margin_ma": capacity_margin_ma,
            "minimum_output_capacitance_uf": minimum_cout_uf,
            "selected_output_capacitance_uf": selected_cout_uf,
        },
        "typical_only_context": {
            "dut_active_read_current_typical_ma": _number(dut.get("active_read_current_typical_ma")),
            "used_for_design_closure": False,
        },
        "unresolved_terms": unresolved,
        "fail_reasons": fail_reasons,
        "power_validated": False,
        "modeled_evidence_only": True,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
