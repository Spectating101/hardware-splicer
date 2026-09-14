"""Derived, non-authoritative virtual laboratory for the SPI adapter.

This module turns the source-bound virtual target into a large deterministic software-only
experiment.  It is deliberately *not* manufacturer-model evidence: every case, result, repair,
and benchmark report is stamped ``derived_surrogate_only`` and is ineligible for vendor-model
campaign credit, measured evidence, or physical authority.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from copy import deepcopy
from typing import Any, Mapping

from .spi_virtual_target import build_grounded_virtual_spi_target

CASE_SCHEMA_VERSION = "hardware_splicer.spi_derived_surrogate_case.v1"
RESULT_SCHEMA_VERSION = "hardware_splicer.spi_derived_surrogate_result.v1"
BENCHMARK_SCHEMA_VERSION = "hardware_splicer.spi_derived_virtual_lab_benchmark.v1"
REPAIR_SCHEMA_VERSION = "hardware_splicer.spi_derived_surrogate_repair.v1"
PROTOCOL_SCHEMA_VERSION = "hardware_splicer.spi_readonly_protocol_oracle.v1"

CLOCK_POINTS_HZ = (1_000_000, 5_000_000, 20_000_000, 100_000_000)
LOAD_POINTS_A = (0.02, 0.10, 0.30, 0.55)
DUT_RAIL_POINTS_V = (1.773, 1.800, 1.827, 1.900)
FAULT_PROFILES = (
    "clean",
    "direct_3v3_drive",
    "reversed_miso",
    "grouped_direction_translator",
    "oe_enabled_without_dut_rail",
    "missing_absmax_provenance",
    "translator_output_overvoltage",
    "supply_out_of_range",
)

_REQUIRED_PROVENANCE = {
    "host_logic_high_v",
    "dut_vcc_range",
    "dut_pin_abs_max_rule",
    "spi_directions",
    "translator_topology",
}

_HARD_FAULT_PROFILES = {
    "direct_3v3_drive",
    "reversed_miso",
    "grouped_direction_translator",
    "oe_enabled_without_dut_rail",
    "translator_output_overvoltage",
    "supply_out_of_range",
}

_REPAIRABLE_PROFILES = _HARD_FAULT_PROFILES | {"missing_absmax_provenance"}
_FORBIDDEN_MUTATING_COMMANDS = {0x01, 0x02, 0x04, 0x06, 0x20, 0x32, 0x52, 0x60, 0xC7, 0xD8}
_REFERENCE_JEDEC_ID = (0xEF, 0x60, 0x18)


def _authority_envelope() -> dict[str, Any]:
    return {
        "evidence_class": "derived_surrogate_only",
        "vendor_model_campaign_credit_eligible": False,
        "model_inference_used": False,
        "measured_evidence_present": False,
        "physical_correctness": "UNPROVEN",
        "fabrication_ready": False,
        "power_on_ready": False,
        "physical_authority_granted": False,
        "authority_effect": "none",
    }


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _finding(
    check_id: str,
    status: str,
    message: str,
    *,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "message": message,
        "evidence": dict(evidence or {}),
    }


def run_readonly_spi_protocol_oracle(
    command: int,
    *,
    powered: bool = True,
    chip_selected: bool = True,
    jedec_id: tuple[int, int, int] = _REFERENCE_JEDEC_ID,
) -> dict[str, Any]:
    """Execute one bounded read-only SPI reference transaction.

    Only JEDEC-ID read ``0x9F`` receives a positive behavioral response.  Commands that could
    mutate flash state are rejected rather than modeled.  This is a derived protocol oracle,
    not a Winbond Verilog model and not vendor-model evidence.
    """

    if isinstance(command, bool) or not isinstance(command, int) or not 0 <= command <= 0xFF:
        raise ValueError("command must be an integer byte")
    if len(jedec_id) != 3 or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 0xFF for v in jedec_id):
        raise ValueError("jedec_id must contain exactly three integer bytes")

    response: list[int] = []
    accepted = False
    reason = "unsupported_readonly_command"
    if not powered:
        reason = "dut_not_powered"
    elif not chip_selected:
        reason = "chip_not_selected"
    elif command in _FORBIDDEN_MUTATING_COMMANDS:
        reason = "mutating_command_forbidden"
    elif command == 0x9F:
        accepted = True
        response = list(jedec_id)
        reason = "jedec_id_read"

    return {
        "schema_version": PROTOCOL_SCHEMA_VERSION,
        "command_hex": f"{command:02X}",
        "accepted": accepted,
        "response_bytes": response,
        "reason": reason,
        "state_mutated": False,
        **_authority_envelope(),
    }


def _baseline_case() -> dict[str, Any]:
    target = build_grounded_virtual_spi_target()
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "candidate_id": target["candidate_id"],
        "host_logic_high_v": 3.3,
        "dut_vcc_v": 1.8,
        "dut_vcc_min_v": 1.7,
        "dut_vcc_max_v": 1.95,
        "dut_pin_abs_max_offset_v": 0.4,
        "direct_connection": False,
        "signals": {
            "SCLK": "host_to_dut",
            "MOSI": "host_to_dut",
            "CS#": "host_to_dut",
            "MISO": "dut_to_host",
        },
        "translator": {
            "topology": "fixed_direction",
            "forward_channels": 3,
            "reverse_channels": 1,
            "dut_side_output_max_v": 1.9,
        },
        "dut_rail_present": True,
        "oe_enabled": True,
        "oe_tied_to_dut_rail": True,
        "spi_clock_hz": 5_000_000,
        "txu_forward_delay_ns": 19.0,
        "txu_reverse_delay_ns": 15.0,
        "dut_clock_to_output_ns": 6.0,
        "derived_load_delay_ns": 5.0,
        "host_setup_allowance_ns": 10.0,
        "regulator_capacity_a": 0.5,
        "estimated_load_a": 0.1,
        "source_claim_ids": deepcopy(target["source_claim_ids"]),
        "fault_profile": "clean",
        **_authority_envelope(),
    }


def _background_is_unsafe(case: Mapping[str, Any]) -> bool:
    clock_hz = float(case["spi_clock_hz"])
    half_cycle_ns = 0.5e9 / clock_hz
    return_delay_ns = (
        float(case["txu_reverse_delay_ns"])
        + float(case["dut_clock_to_output_ns"])
        + float(case["derived_load_delay_ns"])
        + float(case["host_setup_allowance_ns"])
    )
    forward_delay_ns = float(case["txu_forward_delay_ns"]) + float(case["derived_load_delay_ns"])
    timing_unsafe = return_delay_ns > half_cycle_ns or forward_delay_ns > half_cycle_ns
    power_unsafe = float(case["estimated_load_a"]) > float(case["regulator_capacity_a"])
    return timing_unsafe or power_unsafe


def _expected_outcome(case: Mapping[str, Any]) -> str:
    profile = str(case.get("fault_profile") or "clean")
    if profile in _HARD_FAULT_PROFILES or _background_is_unsafe(case):
        return "unsafe"
    if profile == "missing_absmax_provenance":
        return "blocked"
    return "safe"


def build_derived_surrogate_case(
    *,
    profile: str,
    spi_clock_hz: int,
    estimated_load_a: float,
    dut_vcc_v: float,
    ordinal: int,
) -> dict[str, Any]:
    """Build one source-derived case with one explicit fault profile."""

    if profile not in FAULT_PROFILES:
        raise ValueError(f"unknown derived surrogate profile: {profile}")
    case = _baseline_case()
    case.update(
        {
            "case_id": f"dv1-{ordinal:04d}",
            "fault_profile": profile,
            "spi_clock_hz": int(spi_clock_hz),
            "estimated_load_a": float(estimated_load_a),
            "dut_vcc_v": float(dut_vcc_v),
        }
    )

    if profile == "direct_3v3_drive":
        case["direct_connection"] = True
        case["translator"] = None
    elif profile == "reversed_miso":
        case["signals"]["MISO"] = "host_to_dut"
    elif profile == "grouped_direction_translator":
        case["translator"] = {
            "topology": "shared_direction_groups",
            "direction_groups": [2, 2],
            "dut_side_output_max_v": 1.9,
        }
    elif profile == "oe_enabled_without_dut_rail":
        case["dut_rail_present"] = False
        case["oe_enabled"] = True
    elif profile == "missing_absmax_provenance":
        case["source_claim_ids"]["dut_pin_abs_max_rule"] = []
    elif profile == "translator_output_overvoltage":
        case["translator"]["dut_side_output_max_v"] = 2.6
    elif profile == "supply_out_of_range":
        case["dut_vcc_v"] = 2.1

    case["expected_outcome"] = _expected_outcome(case)
    case["case_hash"] = _canonical_hash({key: value for key, value in case.items() if key != "case_hash"})
    return case


def generate_derived_surrogate_corpus() -> list[dict[str, Any]]:
    """Generate the frozen 512-case Derived Virtual Lab v1 corpus."""

    cases: list[dict[str, Any]] = []
    for ordinal, (profile, clock_hz, load_a, vcc_v) in enumerate(
        itertools.product(FAULT_PROFILES, CLOCK_POINTS_HZ, LOAD_POINTS_A, DUT_RAIL_POINTS_V),
        start=1,
    ):
        cases.append(
            build_derived_surrogate_case(
                profile=profile,
                spi_clock_hz=clock_hz,
                estimated_load_a=load_a,
                dut_vcc_v=vcc_v,
                ordinal=ordinal,
            )
        )
    return cases


def evaluate_derived_surrogate_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate one derived case with deterministic analytical rules."""

    candidate = deepcopy(dict(case))
    findings: list[dict[str, Any]] = []

    refs = candidate.get("source_claim_ids") if isinstance(candidate.get("source_claim_ids"), Mapping) else {}
    missing_provenance = sorted(
        key for key in _REQUIRED_PROVENANCE if not isinstance(refs.get(key), list) or not refs.get(key)
    )
    findings.append(
        _finding(
            "surrogate_provenance",
            "blocked" if missing_provenance else "pass",
            "Critical derived inputs are source-bound." if not missing_provenance else "Critical derived inputs are missing source identities.",
            evidence={"missing_keys": missing_provenance},
        )
    )

    vcc = float(candidate["dut_vcc_v"])
    vcc_min = float(candidate["dut_vcc_min_v"])
    vcc_max = float(candidate["dut_vcc_max_v"])
    findings.append(
        _finding(
            "dut_operating_rail",
            "pass" if vcc_min <= vcc <= vcc_max else "fail",
            "DUT rail is inside the declared operating range." if vcc_min <= vcc <= vcc_max else "DUT rail is outside the declared operating range.",
            evidence={"dut_vcc_v": vcc, "allowed_range_v": [vcc_min, vcc_max]},
        )
    )

    pin_abs_max_v = vcc + float(candidate["dut_pin_abs_max_offset_v"])
    if candidate.get("direct_connection"):
        host_high_v = float(candidate["host_logic_high_v"])
        direct_ok = host_high_v <= pin_abs_max_v
        findings.append(
            _finding(
                "direct_drive_absolute_maximum",
                "pass" if direct_ok else "fail",
                "Direct drive remains within the derived pin limit." if direct_ok else "Direct drive exceeds the derived pin absolute maximum.",
                evidence={"host_logic_high_v": host_high_v, "pin_abs_max_v": pin_abs_max_v},
            )
        )
    else:
        findings.append(_finding("direct_drive_absolute_maximum", "pass", "Candidate does not use direct 3.3-V drive."))

    expected_signals = {
        "SCLK": "host_to_dut",
        "MOSI": "host_to_dut",
        "CS#": "host_to_dut",
        "MISO": "dut_to_host",
    }
    actual_signals = candidate.get("signals") if isinstance(candidate.get("signals"), Mapping) else {}
    signal_mismatches = {
        name: {"expected": direction, "actual": actual_signals.get(name)}
        for name, direction in expected_signals.items()
        if actual_signals.get(name) != direction
    }
    findings.append(
        _finding(
            "spi_direction_contract",
            "fail" if signal_mismatches else "pass",
            "SPI direction contract is satisfied." if not signal_mismatches else "SPI direction contract is violated.",
            evidence={"mismatches": signal_mismatches},
        )
    )

    translator = candidate.get("translator")
    if candidate.get("direct_connection"):
        topology_ok = False
    elif not isinstance(translator, Mapping):
        topology_ok = False
    elif translator.get("topology") == "fixed_direction":
        topology_ok = int(translator.get("forward_channels") or 0) >= 3 and int(translator.get("reverse_channels") or 0) >= 1
    elif translator.get("topology") == "shared_direction_groups":
        groups = translator.get("direction_groups")
        topology_ok = isinstance(groups, list) and 3 in groups and 1 in groups
    else:
        topology_ok = False

    if candidate.get("direct_connection"):
        findings.append(_finding("translator_topology", "pass", "Translator topology is not applicable to a direct-drive fault case."))
    else:
        findings.append(
            _finding(
                "translator_topology",
                "pass" if topology_ok else "fail",
                "Translator topology can host the 3+1 SPI split." if topology_ok else "Translator topology cannot host the required 3+1 SPI split.",
                evidence={"translator": translator if isinstance(translator, Mapping) else None},
            )
        )

    if isinstance(translator, Mapping):
        output_max_v = float(translator.get("dut_side_output_max_v") or 0.0)
        output_ok = output_max_v <= pin_abs_max_v
        findings.append(
            _finding(
                "translator_output_absolute_maximum",
                "pass" if output_ok else "fail",
                "Translator output remains within the derived DUT pin limit." if output_ok else "Translator output exceeds the derived DUT pin limit.",
                evidence={"translator_output_max_v": output_max_v, "pin_abs_max_v": pin_abs_max_v},
            )
        )

    isolation_ok = bool(candidate.get("dut_rail_present")) or not bool(candidate.get("oe_enabled"))
    findings.append(
        _finding(
            "oe_unpowered_domain_isolation",
            "pass" if isolation_ok else "fail",
            "OE state does not intentionally drive an unpowered DUT domain." if isolation_ok else "OE is enabled while the DUT rail is absent.",
            evidence={"dut_rail_present": bool(candidate.get("dut_rail_present")), "oe_enabled": bool(candidate.get("oe_enabled"))},
        )
    )

    clock_hz = float(candidate["spi_clock_hz"])
    half_cycle_ns = 0.5e9 / clock_hz
    forward_delay_ns = float(candidate["txu_forward_delay_ns"]) + float(candidate["derived_load_delay_ns"])
    return_delay_ns = (
        float(candidate["txu_reverse_delay_ns"])
        + float(candidate["dut_clock_to_output_ns"])
        + float(candidate["derived_load_delay_ns"])
        + float(candidate["host_setup_allowance_ns"])
    )
    timing_ok = forward_delay_ns <= half_cycle_ns and return_delay_ns <= half_cycle_ns
    findings.append(
        _finding(
            "derived_half_cycle_timing",
            "pass" if timing_ok else "fail",
            "Derived known-delay terms fit inside the selected half-cycle." if timing_ok else "Derived known-delay terms exceed the selected half-cycle.",
            evidence={
                "spi_clock_hz": int(clock_hz),
                "half_cycle_ns": half_cycle_ns,
                "forward_delay_ns": forward_delay_ns,
                "return_delay_ns": return_delay_ns,
                "residual_return_margin_ns": half_cycle_ns - return_delay_ns,
            },
        )
    )

    load_a = float(candidate["estimated_load_a"])
    capacity_a = float(candidate["regulator_capacity_a"])
    power_ok = load_a <= capacity_a
    findings.append(
        _finding(
            "derived_regulator_capacity",
            "pass" if power_ok else "fail",
            "Derived load remains within regulator current capacity." if power_ok else "Derived load exceeds regulator current capacity.",
            evidence={"estimated_load_a": load_a, "regulator_capacity_a": capacity_a, "margin_a": capacity_a - load_a},
        )
    )

    protocol = run_readonly_spi_protocol_oracle(0x9F)
    protocol_ok = protocol["accepted"] is True and protocol["response_bytes"] == list(_REFERENCE_JEDEC_ID) and protocol["state_mutated"] is False
    findings.append(
        _finding(
            "readonly_jedec_protocol_oracle",
            "pass" if protocol_ok else "fail",
            "Derived read-only protocol oracle returned the frozen JEDEC identity without state mutation." if protocol_ok else "Derived read-only protocol oracle failed.",
            evidence={"protocol": protocol},
        )
    )

    counts = {
        "pass": sum(row["status"] == "pass" for row in findings),
        "blocked": sum(row["status"] == "blocked" for row in findings),
        "fail": sum(row["status"] == "fail" for row in findings),
    }
    if counts["fail"]:
        status = "failed_surrogate"
        predicted_outcome = "unsafe"
    elif counts["blocked"]:
        status = "blocked_surrogate"
        predicted_outcome = "blocked"
    else:
        status = "passed_surrogate"
        predicted_outcome = "safe"

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "case_id": candidate.get("case_id"),
        "case_hash": candidate.get("case_hash"),
        "fault_profile": candidate.get("fault_profile"),
        "expected_outcome": candidate.get("expected_outcome"),
        "predicted_outcome": predicted_outcome,
        "status": status,
        "counts": counts,
        "findings": findings,
        **_authority_envelope(),
    }


def repair_derived_surrogate_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the minimal scripted repair for the injected profile only.

    Timing and load-corner failures are deliberately not repaired by silently lowering the
    experiment clock or swapping the regulator.  They remain separate design constraints.
    """

    original = deepcopy(dict(case))
    repaired = deepcopy(original)
    profile = str(repaired.get("fault_profile") or "clean")
    actions: list[str] = []

    if profile == "direct_3v3_drive":
        baseline = _baseline_case()
        repaired["direct_connection"] = False
        repaired["translator"] = deepcopy(baseline["translator"])
        actions.append("restore_fixed_direction_translator")
    elif profile == "reversed_miso":
        repaired["signals"]["MISO"] = "dut_to_host"
        actions.append("restore_miso_dut_to_host")
    elif profile == "grouped_direction_translator":
        repaired["translator"] = deepcopy(_baseline_case()["translator"])
        actions.append("replace_grouped_direction_with_fixed_3_plus_1")
    elif profile == "oe_enabled_without_dut_rail":
        repaired["oe_enabled"] = False
        actions.append("disable_oe_while_dut_rail_absent")
    elif profile == "missing_absmax_provenance":
        repaired["source_claim_ids"]["dut_pin_abs_max_rule"] = deepcopy(
            _baseline_case()["source_claim_ids"]["dut_pin_abs_max_rule"]
        )
        actions.append("restore_absmax_source_binding")
    elif profile == "translator_output_overvoltage":
        repaired["translator"]["dut_side_output_max_v"] = min(float(repaired["dut_vcc_v"]) + 0.1, 1.95)
        actions.append("restore_bounded_dut_side_output")
    elif profile == "supply_out_of_range":
        repaired["dut_vcc_v"] = 1.8
        actions.append("restore_nominal_1v8_rail")

    repaired["fault_profile"] = "clean"
    repaired["expected_outcome"] = _expected_outcome(repaired)
    repaired["case_hash"] = _canonical_hash({key: value for key, value in repaired.items() if key != "case_hash"})
    return {
        "schema_version": REPAIR_SCHEMA_VERSION,
        "case_id": original.get("case_id"),
        "original_fault_profile": profile,
        "repair_attempted": bool(actions),
        "repair_actions": actions,
        "repaired_case": repaired,
        **_authority_envelope(),
    }


def run_derived_virtual_lab_benchmark() -> dict[str, Any]:
    """Execute the frozen 512-case corpus and deterministic repair control."""

    corpus = generate_derived_surrogate_corpus()
    outcome_matrix = {
        expected: {predicted: 0 for predicted in ("safe", "blocked", "unsafe")}
        for expected in ("safe", "blocked", "unsafe")
    }
    profile_counts = {profile: 0 for profile in FAULT_PROFILES}
    authority_violations = 0
    repair_eligible = 0
    repair_success = 0
    repair_failures: list[str] = []

    for case in corpus:
        result = evaluate_derived_surrogate_case(case)
        expected = str(case["expected_outcome"])
        predicted = str(result["predicted_outcome"])
        outcome_matrix[expected][predicted] += 1
        profile_counts[str(case["fault_profile"])] += 1

        if (
            result.get("physical_authority_granted") is not False
            or result.get("vendor_model_campaign_credit_eligible") is not False
            or result.get("physical_correctness") != "UNPROVEN"
        ):
            authority_violations += 1

        profile = str(case["fault_profile"])
        background_safe = not _background_is_unsafe(case)
        if profile in _REPAIRABLE_PROFILES and background_safe:
            repair_eligible += 1
            repair = repair_derived_surrogate_case(case)
            repaired_result = evaluate_derived_surrogate_case(repair["repaired_case"])
            if repaired_result["predicted_outcome"] == "safe":
                repair_success += 1
            else:
                repair_failures.append(str(case["case_id"]))

    unsafe_false_negatives = outcome_matrix["unsafe"]["safe"] + outcome_matrix["unsafe"]["blocked"]
    safe_false_rejections = outcome_matrix["safe"]["unsafe"] + outcome_matrix["safe"]["blocked"]
    blocked_misclassifications = outcome_matrix["blocked"]["safe"] + outcome_matrix["blocked"]["unsafe"]
    repair_success_rate = (repair_success / repair_eligible) if repair_eligible else 0.0

    forbidden_command_checks = {
        f"{command:02X}": run_readonly_spi_protocol_oracle(command)
        for command in sorted(_FORBIDDEN_MUTATING_COMMANDS)
    }
    protocol_boundary_pass = all(
        row["accepted"] is False and row["state_mutated"] is False
        for row in forbidden_command_checks.values()
    ) and run_readonly_spi_protocol_oracle(0x9F)["accepted"] is True

    checks = {
        "frozen_case_count_512": len(corpus) == 512,
        "unique_case_ids": len({row["case_id"] for row in corpus}) == len(corpus),
        "all_fault_profiles_covered": all(profile_counts[profile] > 0 for profile in FAULT_PROFILES),
        "zero_unsafe_false_negatives": unsafe_false_negatives == 0,
        "zero_safe_false_rejections": safe_false_rejections == 0,
        "zero_blocked_misclassifications": blocked_misclassifications == 0,
        "repair_control_complete": repair_eligible > 0 and repair_success == repair_eligible,
        "readonly_protocol_boundary": protocol_boundary_pass,
        "zero_authority_violations": authority_violations == 0,
    }
    benchmark_pass = all(checks.values())

    return {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "benchmark_id": "hs-spi-derived-virtual-lab-v1",
        "status": "passed_derived_benchmark" if benchmark_pass else "failed_derived_benchmark",
        "benchmark_pass": benchmark_pass,
        "case_count": len(corpus),
        "dimensions": {
            "fault_profiles": list(FAULT_PROFILES),
            "spi_clock_hz": list(CLOCK_POINTS_HZ),
            "estimated_load_a": list(LOAD_POINTS_A),
            "dut_rail_v": list(DUT_RAIL_POINTS_V),
        },
        "profile_counts": profile_counts,
        "outcome_matrix": outcome_matrix,
        "unsafe_false_negatives": unsafe_false_negatives,
        "safe_false_rejections": safe_false_rejections,
        "blocked_misclassifications": blocked_misclassifications,
        "repair_control": {
            "eligible_cases": repair_eligible,
            "successful_repairs": repair_success,
            "success_rate": repair_success_rate,
            "failed_case_ids": repair_failures,
        },
        "protocol_oracle": {
            "jedec_id_read": run_readonly_spi_protocol_oracle(0x9F),
            "forbidden_mutating_commands": forbidden_command_checks,
            "boundary_pass": protocol_boundary_pass,
        },
        "authority_violation_count": authority_violations,
        "checks": checks,
        "corpus_digest": "sha256:" + hashlib.sha256(
            "\n".join(row["case_hash"] for row in corpus).encode("utf-8")
        ).hexdigest(),
        "nonclaims": [
            "This benchmark uses source-derived surrogate rules, not manufacturer IBIS or Verilog execution.",
            "Passing the benchmark does not establish physical correctness or physical identity.",
            "Passing the benchmark does not earn vendor-model campaign credit.",
            "Scripted repair success is not evidence of AI competence.",
        ],
        **_authority_envelope(),
    }
