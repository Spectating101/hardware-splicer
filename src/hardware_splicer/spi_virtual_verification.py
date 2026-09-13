"""Deterministic software-only verification for bounded SPI adapter candidates.

This module deliberately sits below physical evidence. It can reject unsafe or internally
inconsistent candidates and can record model/simulation results, but it cannot promote a
candidate to measured, physically correct, fabrication-ready, power-on-ready, or authorized.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from copy import deepcopy
from typing import Any, Mapping

SCHEMA_VERSION = "hardware_splicer.spi_virtual_verification.v1"

EXPECTED_SPI_DIRECTIONS = {
    "SCLK": "host_to_dut",
    "MOSI": "host_to_dut",
    "CS#": "host_to_dut",
    "MISO": "dut_to_host",
}

_REQUIRED_PROVENANCE_KEYS = {
    "host_logic_high_v",
    "dut_vcc_range",
    "dut_pin_abs_max_rule",
    "spi_directions",
    "translator_topology",
}


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _finding(
    check_id: str,
    status: str,
    message: str,
    *,
    severity: str = "info",
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "severity": severity,
        "message": message,
        "evidence": dict(evidence or {}),
    }


def _float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _grouped_direction_capacity(groups: list[int], *, forward: int, reverse: int) -> bool:
    """Return whether whole direction-sharing groups can satisfy the required channels."""

    if not groups or any((not isinstance(size, int) or isinstance(size, bool) or size <= 0) for size in groups):
        return False
    total = sum(groups)
    for orientations in itertools.product(("forward", "reverse"), repeat=len(groups)):
        forward_capacity = sum(size for size, direction in zip(groups, orientations) if direction == "forward")
        reverse_capacity = total - forward_capacity
        if forward_capacity >= forward and reverse_capacity >= reverse:
            return True
    return False


def build_raw_document_v4_candidate() -> dict[str, Any]:
    """Build a bounded virtual candidate from the published raw-document v4 evidence boundary.

    The fixture intentionally leaves the exact implementation, supply, timing, and physical
    identity unresolved. It should therefore be statically coherent but not virtually closed.
    """

    return {
        "candidate_id": "hs-astra-rawdoc-v4-spi-virtual-candidate",
        "candidate_origin": "published_raw_document_v4_boundary",
        "host_logic_high_v": 3.3,
        "dut_supply_target_v": 1.8,
        "dut_vcc_min_v": 1.7,
        "dut_vcc_max_v": 1.95,
        "dut_pin_abs_max_rule": {"kind": "vcc_plus_offset", "offset_v": 0.4},
        "signals": dict(EXPECTED_SPI_DIRECTIONS),
        "direct_connection": False,
        "translator": {
            "family": "TXU0304",
            "topology": "fixed_direction",
            "forward_channels": 3,
            "reverse_channels": 1,
            "exact_orderable_mpn": None,
            "package": None,
            "oe_strategy": None,
            "partial_power_behavior_verified": False,
            "dut_side_output_max_v": None,
        },
        "supply": None,
        "timing": None,
        "simulation": None,
        "source_claim_ids": {
            "host_logic_high_v": ["src-controller"],
            "dut_vcc_range": ["dut-operating-supply"],
            "dut_pin_abs_max_rule": ["dut-pin-absolute-maximum"],
            "spi_directions": ["dut-standard-spi-directions"],
            "translator_topology": ["txu-fixed-direction-map"],
        },
        "known_unresolved": [
            "Exact physical DUT marking, package, orderable suffix, and package-specific pinout.",
            "Exact programmer identity, voltage levels under load, supported clock rate, and timing behavior.",
            "Selected TXU0304 orderable package, footprint, availability, and assembly constraints.",
            "Complete VIH/VIL/VOH/VOL and propagation-delay timing budget at the selected supplies and load.",
            "Local 1.8 V supply implementation, current budget, sequencing, decoupling, protection, and OE behavior.",
            "Schematic/ERC/PCB/DRC results and all physical measurements.",
            "Independent review of all model-proposed document claims.",
        ],
    }


def apply_spi_fault(candidate: Mapping[str, Any], fault_id: str) -> dict[str, Any]:
    """Return a copied candidate with one deterministic adversarial fault injected."""

    mutated = deepcopy(dict(candidate))
    if fault_id == "direct_3v3_drive":
        mutated["direct_connection"] = True
        mutated["translator"] = None
    elif fault_id == "reversed_miso":
        signals = dict(mutated.get("signals") or {})
        signals["MISO"] = "host_to_dut"
        mutated["signals"] = signals
    elif fault_id == "grouped_direction_translator":
        mutated["translator"] = {
            "family": "SN74AXC4T245",
            "topology": "shared_direction_groups",
            "direction_groups": [2, 2],
            "exact_orderable_mpn": None,
            "package": None,
            "oe_strategy": None,
            "partial_power_behavior_verified": False,
            "dut_side_output_max_v": None,
        }
        refs = dict(mutated.get("source_claim_ids") or {})
        refs["translator_topology"] = ["axc-direction-grouping", "axc-function-table"]
        mutated["source_claim_ids"] = refs
    elif fault_id == "missing_absmax_provenance":
        refs = dict(mutated.get("source_claim_ids") or {})
        refs["dut_pin_abs_max_rule"] = []
        mutated["source_claim_ids"] = refs
    else:
        raise ValueError(f"unknown SPI virtual-verification fault: {fault_id}")
    mutated["fault_id"] = fault_id
    return mutated


def verify_spi_virtual_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Verify one SPI candidate without model inference or physical-authority promotion."""

    cand = deepcopy(dict(candidate))
    findings: list[dict[str, Any]] = []

    signals = cand.get("signals")
    if not isinstance(signals, Mapping):
        findings.append(_finding("spi_signal_contract", "fail", "SPI signal map is missing.", severity="error"))
    else:
        mismatches = {
            signal: {"expected": expected, "actual": signals.get(signal)}
            for signal, expected in EXPECTED_SPI_DIRECTIONS.items()
            if signals.get(signal) != expected
        }
        missing = sorted(set(EXPECTED_SPI_DIRECTIONS) - set(signals))
        if missing or mismatches:
            findings.append(
                _finding(
                    "spi_signal_contract",
                    "fail",
                    "SPI signal directions do not match the required three-forward/one-reverse contract.",
                    severity="error",
                    evidence={"missing": missing, "mismatches": mismatches},
                )
            )
        else:
            findings.append(
                _finding(
                    "spi_signal_contract",
                    "pass",
                    "SCLK, MOSI, and CS# are host-to-DUT while MISO is DUT-to-host.",
                    evidence={"signals": dict(signals)},
                )
            )

    host_high_v = _float(cand.get("host_logic_high_v"))
    dut_vcc_min_v = _float(cand.get("dut_vcc_min_v"))
    abs_rule = cand.get("dut_pin_abs_max_rule")
    guaranteed_pin_max_v: float | None = None
    if isinstance(abs_rule, Mapping) and abs_rule.get("kind") == "vcc_plus_offset":
        offset_v = _float(abs_rule.get("offset_v"))
        if dut_vcc_min_v is not None and offset_v is not None:
            guaranteed_pin_max_v = dut_vcc_min_v + offset_v

    if guaranteed_pin_max_v is None:
        findings.append(
            _finding(
                "dut_pin_absolute_maximum",
                "blocked",
                "No deterministic DUT pin absolute-maximum bound can be derived from the candidate.",
                severity="warn",
            )
        )
    elif bool(cand.get("direct_connection")):
        if host_high_v is None:
            findings.append(
                _finding(
                    "direct_drive_absolute_maximum",
                    "blocked",
                    "Host logic-high voltage is missing, so direct-drive safety cannot be checked.",
                    severity="warn",
                )
            )
        elif host_high_v > guaranteed_pin_max_v:
            findings.append(
                _finding(
                    "direct_drive_absolute_maximum",
                    "fail",
                    "Direct host drive exceeds the conservative DUT pin absolute-maximum bound.",
                    severity="error",
                    evidence={
                        "host_logic_high_v": host_high_v,
                        "guaranteed_pin_max_v": round(guaranteed_pin_max_v, 6),
                        "margin_v": round(guaranteed_pin_max_v - host_high_v, 6),
                    },
                )
            )
        else:
            findings.append(
                _finding(
                    "direct_drive_absolute_maximum",
                    "pass",
                    "Direct host drive is within the derived DUT pin absolute-maximum bound.",
                    evidence={
                        "host_logic_high_v": host_high_v,
                        "guaranteed_pin_max_v": round(guaranteed_pin_max_v, 6),
                    },
                )
            )
    else:
        findings.append(
            _finding(
                "direct_drive_absolute_maximum",
                "pass",
                "The candidate does not propose direct 3.3 V host drive into the DUT domain.",
                evidence={"guaranteed_pin_max_v": round(guaranteed_pin_max_v, 6)},
            )
        )

    translator = cand.get("translator")
    if not bool(cand.get("direct_connection")):
        if not isinstance(translator, Mapping):
            findings.append(
                _finding(
                    "translator_topology",
                    "blocked",
                    "A translated candidate has no translator topology.",
                    severity="warn",
                )
            )
        else:
            topology = str(translator.get("topology") or "")
            topology_ok = False
            topology_evidence: dict[str, Any] = {"family": translator.get("family"), "topology": topology}
            if topology == "fixed_direction":
                forward = translator.get("forward_channels")
                reverse = translator.get("reverse_channels")
                topology_evidence.update({"forward_channels": forward, "reverse_channels": reverse})
                topology_ok = (
                    isinstance(forward, int)
                    and not isinstance(forward, bool)
                    and isinstance(reverse, int)
                    and not isinstance(reverse, bool)
                    and forward >= 3
                    and reverse >= 1
                )
            elif topology == "shared_direction_groups":
                groups_raw = translator.get("direction_groups")
                groups = list(groups_raw) if isinstance(groups_raw, list) else []
                topology_evidence["direction_groups"] = groups
                topology_ok = _grouped_direction_capacity(groups, forward=3, reverse=1)

            if topology_ok:
                findings.append(
                    _finding(
                        "translator_topology",
                        "pass",
                        "Translator channel-direction topology can host the SPI 3+1 direction split.",
                        evidence=topology_evidence,
                    )
                )
            else:
                findings.append(
                    _finding(
                        "translator_topology",
                        "fail",
                        "Translator channel-direction topology cannot host the required SPI 3+1 direction split.",
                        severity="error",
                        evidence=topology_evidence,
                    )
                )

            exact_fields = {
                "exact_orderable_mpn": translator.get("exact_orderable_mpn"),
                "package": translator.get("package"),
                "oe_strategy": translator.get("oe_strategy"),
            }
            if not all(exact_fields.values()) or not bool(translator.get("partial_power_behavior_verified")):
                findings.append(
                    _finding(
                        "translator_implementation_closure",
                        "blocked",
                        "Exact translator ordering/package/OE/partial-power behavior is not closed.",
                        severity="warn",
                        evidence={**exact_fields, "partial_power_behavior_verified": bool(translator.get("partial_power_behavior_verified"))},
                    )
                )
            else:
                findings.append(
                    _finding(
                        "translator_implementation_closure",
                        "pass",
                        "Exact translator identity and control/partial-power boundary are supplied.",
                        evidence=exact_fields,
                    )
                )

            dut_output_max_v = _float(translator.get("dut_side_output_max_v"))
            if dut_output_max_v is None:
                findings.append(
                    _finding(
                        "translator_dut_output_level",
                        "blocked",
                        "DUT-side translator output maximum is not supplied for deterministic absolute-maximum comparison.",
                        severity="warn",
                    )
                )
            elif guaranteed_pin_max_v is None:
                findings.append(
                    _finding(
                        "translator_dut_output_level",
                        "blocked",
                        "DUT-side output is supplied but the DUT absolute-maximum bound is unavailable.",
                        severity="warn",
                    )
                )
            elif dut_output_max_v > guaranteed_pin_max_v:
                findings.append(
                    _finding(
                        "translator_dut_output_level",
                        "fail",
                        "Translator DUT-side output can exceed the derived DUT pin absolute maximum.",
                        severity="error",
                        evidence={"dut_side_output_max_v": dut_output_max_v, "guaranteed_pin_max_v": guaranteed_pin_max_v},
                    )
                )
            else:
                findings.append(
                    _finding(
                        "translator_dut_output_level",
                        "pass",
                        "Translator DUT-side output is within the derived DUT pin absolute maximum.",
                        evidence={"dut_side_output_max_v": dut_output_max_v, "guaranteed_pin_max_v": guaranteed_pin_max_v},
                    )
                )

    supply = cand.get("supply")
    if not isinstance(supply, Mapping):
        findings.append(
            _finding(
                "dut_supply_closure",
                "blocked",
                "No exact local DUT supply implementation is bound to the candidate.",
                severity="warn",
            )
        )
    else:
        out_min = _float(supply.get("output_min_v"))
        out_max = _float(supply.get("output_max_v"))
        dut_min = _float(cand.get("dut_vcc_min_v"))
        dut_max = _float(cand.get("dut_vcc_max_v"))
        if None in {out_min, out_max, dut_min, dut_max}:
            findings.append(
                _finding(
                    "dut_supply_closure",
                    "blocked",
                    "Supply or DUT voltage limits are incomplete.",
                    severity="warn",
                )
            )
        elif out_min < dut_min or out_max > dut_max:
            findings.append(
                _finding(
                    "dut_supply_closure",
                    "fail",
                    "Candidate supply tolerance escapes the DUT operating range.",
                    severity="error",
                    evidence={"supply_range_v": [out_min, out_max], "dut_range_v": [dut_min, dut_max]},
                )
            )
        elif not bool(supply.get("current_budget_verified")) or not bool(supply.get("sequencing_verified")):
            findings.append(
                _finding(
                    "dut_supply_closure",
                    "blocked",
                    "Supply voltage range fits, but current-budget or sequencing closure is missing.",
                    severity="warn",
                    evidence={"supply_range_v": [out_min, out_max], "dut_range_v": [dut_min, dut_max]},
                )
            )
        else:
            findings.append(
                _finding(
                    "dut_supply_closure",
                    "pass",
                    "Supply range, current budget, and sequencing are supplied within the declared DUT range.",
                    evidence={"supply_range_v": [out_min, out_max], "dut_range_v": [dut_min, dut_max]},
                )
            )

    timing = cand.get("timing")
    if not isinstance(timing, Mapping):
        findings.append(
            _finding(
                "spi_timing_closure",
                "blocked",
                "No deterministic SPI timing/load budget is bound to the candidate.",
                severity="warn",
            )
        )
    else:
        clock_hz = _float(timing.get("spi_clock_hz"))
        max_clock_hz = _float(timing.get("max_supported_spi_clock_hz"))
        load_verified = bool(timing.get("selected_load_verified"))
        if clock_hz is None or max_clock_hz is None:
            findings.append(
                _finding(
                    "spi_timing_closure",
                    "blocked",
                    "SPI clock or supported-clock boundary is missing.",
                    severity="warn",
                )
            )
        elif clock_hz > max_clock_hz:
            findings.append(
                _finding(
                    "spi_timing_closure",
                    "fail",
                    "Requested SPI clock exceeds the candidate's declared supported-clock boundary.",
                    severity="error",
                    evidence={"spi_clock_hz": clock_hz, "max_supported_spi_clock_hz": max_clock_hz},
                )
            )
        elif not load_verified:
            findings.append(
                _finding(
                    "spi_timing_closure",
                    "blocked",
                    "Clock comparison passes but the selected load/timing conditions are not verified.",
                    severity="warn",
                    evidence={"spi_clock_hz": clock_hz, "max_supported_spi_clock_hz": max_clock_hz},
                )
            )
        else:
            findings.append(
                _finding(
                    "spi_timing_closure",
                    "pass",
                    "Requested SPI clock is within the supplied timing boundary at the selected load.",
                    evidence={"spi_clock_hz": clock_hz, "max_supported_spi_clock_hz": max_clock_hz},
                )
            )

    refs = cand.get("source_claim_ids")
    refs = refs if isinstance(refs, Mapping) else {}
    missing_provenance = sorted(
        key
        for key in _REQUIRED_PROVENANCE_KEYS
        if not isinstance(refs.get(key), list) or not refs.get(key)
    )
    if missing_provenance:
        findings.append(
            _finding(
                "critical_input_provenance",
                "blocked",
                "One or more critical virtual-verification inputs lack explicit source/claim identities.",
                severity="warn",
                evidence={"missing": missing_provenance},
            )
        )
    else:
        findings.append(
            _finding(
                "critical_input_provenance",
                "pass",
                "Critical voltage, direction, and translator-topology inputs carry explicit source/claim identities.",
                evidence={key: list(refs[key]) for key in sorted(_REQUIRED_PROVENANCE_KEYS)},
            )
        )

    simulation = cand.get("simulation")
    if not isinstance(simulation, Mapping):
        findings.append(
            _finding(
                "bound_simulation",
                "blocked",
                "No exact candidate-bound simulator result is attached; static verification remains below simulated closure.",
                severity="warn",
            )
        )
    else:
        simulation_pass = simulation.get("simulation_pass")
        if simulation_pass is True:
            findings.append(
                _finding(
                    "bound_simulation",
                    "pass",
                    "A candidate-bound simulator result reports pass; this remains simulated rather than measured evidence.",
                    evidence={"schema_version": simulation.get("schema_version"), "scope": simulation.get("scope")},
                )
            )
        elif simulation_pass is False:
            findings.append(
                _finding(
                    "bound_simulation",
                    "fail",
                    "Candidate-bound simulation reports failure.",
                    severity="error",
                    evidence={"schema_version": simulation.get("schema_version"), "scope": simulation.get("scope")},
                )
            )
        else:
            findings.append(
                _finding(
                    "bound_simulation",
                    "blocked",
                    "Simulator result is present but has no determinate pass/fail result.",
                    severity="warn",
                )
            )

    fail_count = sum(1 for row in findings if row["status"] == "fail")
    blocked_count = sum(1 for row in findings if row["status"] == "blocked")
    pass_count = sum(1 for row in findings if row["status"] == "pass")
    static_fail_count = sum(
        1 for row in findings if row["status"] == "fail" and row["check_id"] != "bound_simulation"
    )
    verification_status = "failed" if fail_count else ("blocked" if blocked_count else "passed_virtual")

    return {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": str(cand.get("candidate_id") or "unnamed-spi-candidate"),
        "candidate_hash": _canonical_hash(cand),
        "verification_mode": "deterministic_software_only",
        "verification_status": verification_status,
        "static_verification_pass": static_fail_count == 0,
        "counts": {"pass": pass_count, "blocked": blocked_count, "fail": fail_count},
        "findings": findings,
        "known_unresolved": list(cand.get("known_unresolved") or []),
        "evidence_class": "derived_or_simulated_only",
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def run_spi_fault_corpus(base_candidate: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Run a deterministic adversarial corpus without invoking any model."""

    base = deepcopy(dict(base_candidate or build_raw_document_v4_candidate()))
    cases = {"baseline": verify_spi_virtual_candidate(base)}
    for fault_id in (
        "direct_3v3_drive",
        "reversed_miso",
        "grouped_direction_translator",
        "missing_absmax_provenance",
    ):
        cases[fault_id] = verify_spi_virtual_candidate(apply_spi_fault(base, fault_id))

    expected = {
        "baseline": "blocked",
        "direct_3v3_drive": "failed",
        "reversed_miso": "failed",
        "grouped_direction_translator": "failed",
        "missing_absmax_provenance": "blocked",
    }
    expectations = {
        case_id: {"expected": status, "actual": cases[case_id]["verification_status"], "pass": cases[case_id]["verification_status"] == status}
        for case_id, status in expected.items()
    }
    return {
        "schema_version": "hardware_splicer.spi_virtual_fault_corpus.v1",
        "model_inference_used": False,
        "all_expectations_pass": all(row["pass"] for row in expectations.values()),
        "expectations": expectations,
        "cases": cases,
        "physical_correctness": "UNPROVEN",
        "physical_authority_granted": False,
        "authority_effect": "none",
    }
