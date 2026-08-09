"""Separate nominal capacitor selection from effective-capacitance closure.

Ceramic capacitor nominal value is not the same as effective capacitance under DC bias,
tolerance, temperature, aging, and package effects. A model may propose a nominal capacitor,
but Hardware Splicer must not convert that proposal into regulator-stability proof unless the
persisted evidence actually closes the effective value at the operating condition.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


def _nets(proposal: Mapping[str, Any]) -> Dict[str, set[str]]:
    return {
        str(row.get("name")): {str(ep) for ep in list(row.get("endpoints") or [])}
        for row in list(proposal.get("nets") or [])
        if isinstance(row, Mapping) and row.get("name")
    }


def _net_for_endpoint(nets: Mapping[str, set[str]], endpoint: str) -> str | None:
    hits = [name for name, endpoints in nets.items() if endpoint in endpoints]
    return hits[0] if len(hits) == 1 else None


def audit_ldo_capacitance_evidence(proposal: Mapping[str, Any], evidence: Mapping[str, Any]) -> Dict[str, Any]:
    """Audit LDO input/output capacitors without laundering nominal value into effective value."""

    selected = {
        str(row.get("ref")): dict(row)
        for row in list(proposal.get("selected_parts") or [])
        if isinstance(row, Mapping) and row.get("ref")
    }
    parts = {
        str(row.get("evidence_id")): dict(row)
        for row in list(evidence.get("parts") or [])
        if isinstance(row, Mapping) and row.get("evidence_id")
    }
    ldo = parts.get(str((selected.get("U1") or {}).get("evidence_id") or ""))
    if ldo is None:
        return {
            "status": "failed",
            "hard_failures": [{"code": "LDO_EVIDENCE_MISSING"}],
            "unresolved": [],
            "authority_effect": "none",
            "power_on_authorized": False,
        }

    constraints = dict(ldo.get("constraints") or {})
    minimum_nominal_in = float(constraints.get("input_capacitor_min_nominal_uf") or 0.0)
    minimum_nominal_out = float(constraints.get("output_capacitor_min_nominal_uf") or 0.0)
    minimum_effective = float(constraints.get("effective_capacitance_min_uf") or 0.0)
    nets = _nets(proposal)

    rows: list[Dict[str, Any]] = []
    hard_failures: list[Dict[str, Any]] = []
    unresolved: list[Dict[str, Any]] = []
    for passive in list(proposal.get("passives") or []):
        if not isinstance(passive, Mapping) or passive.get("kind") != "capacitor":
            continue
        ref = str(passive.get("ref") or "")
        n1 = _net_for_endpoint(nets, f"{ref}.1")
        n2 = _net_for_endpoint(nets, f"{ref}.2")
        rail_pair = {n1, n2}
        role = None
        nominal_min = None
        operating_bias_v = None
        if rail_pair == {"+5V", "GND"}:
            role = "ldo_input"
            nominal_min = minimum_nominal_in
            operating_bias_v = 5.0
        elif rail_pair == {"+3V3", "GND"}:
            role = "ldo_output"
            nominal_min = minimum_nominal_out
            operating_bias_v = 3.3
        if role is None:
            continue

        nominal = float(passive.get("value_uf") or 0.0)
        exact_mpn = str(passive.get("mpn") or "").strip() or None
        effective = passive.get("effective_capacitance_uf_at_operating_bias")
        effective_value = float(effective) if effective is not None else None
        row = {
            "ref": ref,
            "role": role,
            "nominal_capacitance_uf": nominal,
            "minimum_nominal_uf": nominal_min,
            "minimum_effective_uf": minimum_effective,
            "operating_bias_v": operating_bias_v,
            "mpn": exact_mpn,
            "effective_capacitance_uf_at_operating_bias": effective_value,
        }
        if nominal < float(nominal_min or 0.0):
            row["status"] = "fail"
            hard_failures.append(
                {
                    "code": "NOMINAL_CAPACITANCE_BELOW_DATASHEET_MINIMUM",
                    "ref": ref,
                    "role": role,
                    "nominal_uf": nominal,
                    "minimum_uf": nominal_min,
                }
            )
        elif exact_mpn is None or effective_value is None:
            row["status"] = "unresolved"
            unresolved.append(
                {
                    "code": "EFFECTIVE_CAPACITANCE_UNRESOLVED",
                    "ref": ref,
                    "role": role,
                    "reason": "Nominal capacitance is present, but exact capacitor identity and/or effective capacitance at operating DC bias is not persisted.",
                    "minimum_effective_uf": minimum_effective,
                }
            )
        elif effective_value < minimum_effective:
            row["status"] = "fail"
            hard_failures.append(
                {
                    "code": "EFFECTIVE_CAPACITANCE_BELOW_STABILITY_MINIMUM",
                    "ref": ref,
                    "role": role,
                    "effective_uf": effective_value,
                    "minimum_effective_uf": minimum_effective,
                }
            )
        else:
            row["status"] = "closed"
        rows.append(row)

    roles = {row["role"] for row in rows}
    for required_role in ("ldo_input", "ldo_output"):
        if required_role not in roles:
            hard_failures.append(
                {
                    "code": "REQUIRED_LDO_CAPACITOR_MISSING",
                    "role": required_role,
                }
            )

    status = "failed" if hard_failures else ("blocked" if unresolved else "closed")
    return {
        "status": status,
        "nominal_requirement_pass": not hard_failures,
        "effective_capacitance_closed": status == "closed",
        "rows": rows,
        "hard_failures": hard_failures,
        "unresolved": unresolved,
        "authority_effect": "none",
        "fabrication_authorized": False,
        "power_on_authorized": False,
    }
