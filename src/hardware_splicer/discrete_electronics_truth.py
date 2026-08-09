"""Datasheet-backed truth contracts for discrete electronic designs.

This is intentionally separate from the historical module catalog. A model may select exact
parts and propose a circuit only from persisted manufacturer evidence. Deterministic checks
then validate part identity, rails, control modes, required bypass/stability capacitors, and
full-duplex directionality. Unknown package-to-KiCad footprint mappings remain unresolved and
therefore block fabrication readiness rather than being guessed.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


SCHEMA_VERSION = "hardware_splicer.discrete_electronics_truth.v1"


def load_json_object(path: str | Path) -> Dict[str, Any]:
    body = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(body, Mapping):
        raise ValueError(f"{path} must contain one JSON object")
    return dict(body)


def _parts_by_id(evidence: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(row["evidence_id"]): dict(row)
        for row in list(evidence.get("parts") or [])
        if isinstance(row, Mapping) and row.get("evidence_id")
    }


def _selected_by_ref(proposal: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(row["ref"]): dict(row)
        for row in list(proposal.get("selected_parts") or [])
        if isinstance(row, Mapping) and row.get("ref")
    }


def _passives_by_ref(proposal: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(row["ref"]): dict(row)
        for row in list(proposal.get("passives") or [])
        if isinstance(row, Mapping) and row.get("ref")
    }


def _nets(proposal: Mapping[str, Any]) -> Dict[str, set[str]]:
    return {
        str(row.get("name")): {str(ep) for ep in list(row.get("endpoints") or [])}
        for row in list(proposal.get("nets") or [])
        if isinstance(row, Mapping) and row.get("name")
    }


def _net_for_endpoint(nets: Mapping[str, set[str]], endpoint: str) -> str | None:
    hits = [name for name, endpoints in nets.items() if endpoint in endpoints]
    return hits[0] if len(hits) == 1 else None


def _cap_between(
    proposal: Mapping[str, Any],
    *,
    supply_net: str,
    ground_net: str,
    minimum_uf: float,
) -> list[str]:
    passives = _passives_by_ref(proposal)
    nets = _nets(proposal)
    result: list[str] = []
    for ref, row in passives.items():
        if str(row.get("kind")) != "capacitor":
            continue
        try:
            value = float(row.get("value_uf"))
        except (TypeError, ValueError):
            continue
        if value < minimum_uf:
            continue
        n1 = _net_for_endpoint(nets, f"{ref}.1")
        n2 = _net_for_endpoint(nets, f"{ref}.2")
        if {n1, n2} == {supply_net, ground_net}:
            result.append(ref)
    return result


def _finding(code: str, message: str, *, severity: str = "error", **data: Any) -> Dict[str, Any]:
    return {"code": code, "severity": severity, "message": message, **data}


def validate_exact_part_identity(proposal: Mapping[str, Any], evidence: Mapping[str, Any]) -> Dict[str, Any]:
    parts = _parts_by_id(evidence)
    findings: list[Dict[str, Any]] = []
    for row in list(proposal.get("selected_parts") or []):
        if not isinstance(row, Mapping):
            continue
        evidence_id = str(row.get("evidence_id") or "")
        part = parts.get(evidence_id)
        if part is None:
            findings.append(_finding("UNKNOWN_PART_EVIDENCE", "Selected part has no persisted evidence.", ref=row.get("ref"), evidence_id=evidence_id))
            continue
        if str(row.get("mpn") or "") != str(part.get("mpn") or ""):
            findings.append(_finding("PART_MPN_EVIDENCE_MISMATCH", "Selected MPN does not match the referenced manufacturer evidence.", ref=row.get("ref"), selected_mpn=row.get("mpn"), evidence_mpn=part.get("mpn")))
    return {"pass": not findings, "findings": findings, "authority_effect": "none"}


def validate_ldo_3v3(proposal: Mapping[str, Any], evidence: Mapping[str, Any]) -> Dict[str, Any]:
    req = dict(proposal.get("requirements") or {})
    selected = _selected_by_ref(proposal)
    parts = _parts_by_id(evidence)
    nets = _nets(proposal)
    findings: list[Dict[str, Any]] = []
    row = selected.get("U1")
    part = parts.get(str((row or {}).get("evidence_id") or ""))
    if part is None or part.get("function") != "fixed_3v3_ldo":
        findings.append(_finding("LDO_IDENTITY_UNRESOLVED", "U1 must resolve to an evidenced fixed 3.3 V LDO."))
        return {"pass": False, "findings": findings, "authority_effect": "none"}

    c = dict(part.get("constraints") or {})
    vin = float(req.get("input_voltage_v") or 0.0)
    load = float(req.get("local_3v3_load_max_a") or 0.0)
    if not (float(c["input_voltage_min_v"]) <= vin <= float(c["input_voltage_max_v"])):
        findings.append(_finding("LDO_INPUT_OUT_OF_RANGE", "Declared input voltage is outside the evidenced LDO operating range.", input_voltage_v=vin))
    if load > float(c["output_current_max_a"]):
        findings.append(_finding("LDO_LOAD_EXCEEDS_RATING", "Declared 3.3 V load exceeds the evidenced LDO output-current limit.", load_a=load))
    if float(c.get("output_voltage_v") or 0.0) != 3.3:
        findings.append(_finding("LDO_WRONG_FIXED_OUTPUT", "Selected LDO evidence is not the required 3.3 V fixed-output variant."))

    if _net_for_endpoint(nets, "U1.IN") != "+5V":
        findings.append(_finding("LDO_INPUT_NET_MISMATCH", "U1.IN must be connected to the declared +5V rail."))
    if _net_for_endpoint(nets, "U1.OUT") != "+3V3":
        findings.append(_finding("LDO_OUTPUT_NET_MISMATCH", "U1.OUT must source the +3V3 rail."))
    if _net_for_endpoint(nets, "U1.GND") != "GND":
        findings.append(_finding("LDO_GROUND_MISSING", "U1.GND must be connected to GND."))
    if req.get("translator_always_enabled") and c.get("enable_may_tie_to_input_when_shutdown_not_required"):
        if _net_for_endpoint(nets, "U1.EN") != "+5V":
            findings.append(_finding("LDO_ENABLE_NOT_TIED_TO_INPUT", "Shutdown is not required; the proposed always-on LDO should tie EN to IN as supported by the datasheet evidence."))

    cin = _cap_between(proposal, supply_net="+5V", ground_net="GND", minimum_uf=float(c["input_capacitor_min_nominal_uf"]))
    cout = _cap_between(proposal, supply_net="+3V3", ground_net="GND", minimum_uf=float(c["output_capacitor_min_nominal_uf"]))
    if not cin:
        findings.append(_finding("LDO_INPUT_CAPACITOR_MISSING", "No input capacitor meeting the evidenced nominal minimum is connected from +5V to GND."))
    if not cout:
        findings.append(_finding("LDO_OUTPUT_CAPACITOR_MISSING", "No output capacitor meeting the evidenced nominal minimum is connected from +3V3 to GND."))

    return {"pass": not findings, "findings": findings, "input_capacitors": cin, "output_capacitors": cout, "authority_effect": "none"}


def validate_full_duplex_translator(proposal: Mapping[str, Any], evidence: Mapping[str, Any]) -> Dict[str, Any]:
    req = dict(proposal.get("requirements") or {})
    selected = _selected_by_ref(proposal)
    parts = _parts_by_id(evidence)
    nets = _nets(proposal)
    findings: list[Dict[str, Any]] = []
    row = selected.get("U2")
    part = parts.get(str((row or {}).get("evidence_id") or ""))
    if part is None:
        findings.append(_finding("TRANSLATOR_IDENTITY_UNRESOLVED", "U2 has no exact manufacturer evidence."))
        return {"pass": False, "findings": findings, "authority_effect": "none"}
    c = dict(part.get("constraints") or {})

    if req.get("uart_full_duplex_simultaneous_opposite_directions") and not c.get("direction_controls_independent"):
        findings.append(_finding("TRANSLATOR_DIRECTION_TOPOLOGY_INCOMPATIBLE", "The selected translator shares one direction control across both channels and cannot implement simultaneous opposite UART directions."))

    host_v = float(req.get("host_logic_v") or 0.0)
    dut_v = float(req.get("dut_logic_v") or 0.0)
    if not (float(c.get("vcca_min_v") or 1e9) <= host_v <= float(c.get("vcca_max_v") or -1e9)):
        findings.append(_finding("TRANSLATOR_VCCA_OUT_OF_RANGE", "Host-side VCCA is outside the evidenced translator supply range.", vcca_v=host_v))
    if not (float(c.get("vccb_min_v") or 1e9) <= dut_v <= float(c.get("vccb_max_v") or -1e9)):
        findings.append(_finding("TRANSLATOR_VCCB_OUT_OF_RANGE", "DUT-side VCCB is outside the evidenced translator supply range.", vccb_v=dut_v))

    expected_nets = {
        "U2.VCCA": "+3V3",
        "U2.VCCB": "+1V8_DUT",
        "U2.GND": "GND",
        "U2.A1": "HOST_TX_3V3",
        "U2.B1": "DUT_RX_1V8",
        "U2.B2": "DUT_TX_1V8",
        "U2.A2": "HOST_RX_3V3",
    }
    for endpoint, expected in expected_nets.items():
        if _net_for_endpoint(nets, endpoint) != expected:
            findings.append(_finding("TRANSLATOR_SIGNAL_NET_MISMATCH", f"{endpoint} is not on the required {expected} net.", endpoint=endpoint, expected_net=expected))

    # DIR high (VCCA) means A→B; DIR low (GND) means B→A. For the full-duplex proposal,
    # channel 1 carries host TX A1→B1 while channel 2 carries DUT TX B2→A2.
    if c.get("direction_controls_independent"):
        if _net_for_endpoint(nets, "U2.DIR1") != "+3V3":
            findings.append(_finding("TRANSLATOR_DIR1_WRONG", "DIR1 must be high on VCCA for host TX A1-to-B1."))
        if _net_for_endpoint(nets, "U2.DIR2") != "GND":
            findings.append(_finding("TRANSLATOR_DIR2_WRONG", "DIR2 must be low for DUT TX B2-to-A2."))
        if req.get("translator_always_enabled") and _net_for_endpoint(nets, "U2.OE") != "GND":
            findings.append(_finding("TRANSLATOR_OE_WRONG", "OE must be low for always-enabled translation; high isolates all outputs."))

    bypass_min = float(c.get("bypass_capacitor_recommended_uf") or 0.0)
    cap_a = _cap_between(proposal, supply_net="+3V3", ground_net="GND", minimum_uf=bypass_min)
    cap_b = _cap_between(proposal, supply_net="+1V8_DUT", ground_net="GND", minimum_uf=bypass_min)
    if bypass_min and not cap_a:
        findings.append(_finding("TRANSLATOR_VCCA_BYPASS_MISSING", "No bypass capacitor meeting the evidenced recommendation is connected from VCCA/+3V3 to GND."))
    if bypass_min and not cap_b:
        findings.append(_finding("TRANSLATOR_VCCB_BYPASS_MISSING", "No bypass capacitor meeting the evidenced recommendation is connected from VCCB/+1V8_DUT to GND."))

    return {"pass": not findings, "findings": findings, "vcca_bypass": cap_a, "vccb_bypass": cap_b, "authority_effect": "none"}


def audit_footprint_closure(proposal: Mapping[str, Any], evidence: Mapping[str, Any]) -> Dict[str, Any]:
    selected = _selected_by_ref(proposal)
    parts = _parts_by_id(evidence)
    unresolved: list[Dict[str, Any]] = []
    for ref, row in selected.items():
        part = parts.get(str(row.get("evidence_id") or ""))
        if part and not part.get("kicad_footprint"):
            unresolved.append({
                "ref": ref,
                "mpn": part.get("mpn"),
                "package_code": part.get("package_code"),
                "package_family": part.get("package_family"),
                "reason": "Exact verified KiCad land-pattern mapping is unresolved and must not be guessed.",
            })
    return {"closed": not unresolved, "unresolved": unresolved, "fabrication_authorized": False, "authority_effect": "none"}


def run_discrete_electronics_benchmark(proposal: Mapping[str, Any], evidence: Mapping[str, Any]) -> Dict[str, Any]:
    identity = validate_exact_part_identity(proposal, evidence)
    ldo = validate_ldo_3v3(proposal, evidence)
    translator = validate_full_duplex_translator(proposal, evidence)
    footprints = audit_footprint_closure(proposal, evidence)

    # Adversarial comparator 1: replace the independent-DIR translator with the visually
    # similar shared-DIR 2T45. A retrieval/copy system may accept it; engineering should not.
    wrong_translator = copy.deepcopy(dict(proposal))
    for row in wrong_translator["selected_parts"]:
        if row.get("ref") == "U2":
            row["evidence_id"] = "part-sn74axc2t45dcur"
            row["mpn"] = "SN74AXC2T45DCUR"
    wrong_translator_result = validate_full_duplex_translator(wrong_translator, evidence)

    # Adversarial comparator 2: remove the LDO output stability capacitor.
    missing_cout = copy.deepcopy(dict(proposal))
    missing_cout["passives"] = [row for row in missing_cout["passives"] if row.get("ref") != "C2"]
    missing_cout["nets"] = [
        {**row, "endpoints": [ep for ep in row.get("endpoints") or [] if not str(ep).startswith("C2.")]}
        for row in missing_cout["nets"]
    ]
    missing_cout_result = validate_ldo_3v3(missing_cout, evidence)

    checks = {
        "exact_part_identity_grounded": identity["pass"],
        "ldo_rail_and_stability_contracts_pass": ldo["pass"],
        "full_duplex_translator_contract_pass": translator["pass"],
        "shared_direction_translator_rejected_for_full_duplex_uart": not wrong_translator_result["pass"],
        "missing_ldo_output_capacitor_rejected": not missing_cout_result["pass"],
        "unresolved_footprints_block_fabrication_instead_of_being_guessed": not footprints["closed"],
        "physical_authority_closed": True,
    }
    diagnostic_pass = all(checks.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "datasheet_backed_5v_to_3v3_full_duplex_3v3_1v8_uart",
        "diagnostic_pass": diagnostic_pass,
        "design_ready": False,
        "fabrication_ready": False,
        "power_on_ready": False,
        "checks": checks,
        "proposal": dict(proposal),
        "identity_audit": identity,
        "ldo_audit": ldo,
        "translator_audit": translator,
        "footprint_closure": footprints,
        "adversarial": {
            "shared_direction_translator": wrong_translator_result,
            "missing_ldo_output_capacitor": missing_cout_result,
        },
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
        "release_authorized": False,
    }
