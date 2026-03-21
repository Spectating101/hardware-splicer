from __future__ import annotations

from typing import Any, Dict, List, Set

from src.engines.evidence_extractor import is_power_net


def _normalize_net(net: str) -> str:
    return (net or "").strip()


def _infer_nominal_voltage(net: str) -> float | None:
    up = _normalize_net(net).upper().lstrip("/")
    for suffix in ("_RAIL", "-RAIL"):
        if up.endswith(suffix):
            up = up[: -len(suffix)]
    aliases = {
        "+1V8": 1.8,
        "1V8": 1.8,
        "+2V5": 2.5,
        "2V5": 2.5,
        "+3V3": 3.3,
        "3V3": 3.3,
        "VCC3V3": 3.3,
        "+5V": 5.0,
        "5V": 5.0,
        "VBUS": 5.0,
        "VUSB": 5.0,
        "+12V": 12.0,
        "12V": 12.0,
        "VIN": 12.0,
        "VBAT": 12.0,
        "+24V": 24.0,
        "24V": 24.0,
    }
    return aliases.get(up)


def _blob(ref: str, meta: Dict[str, Any]) -> str:
    return f"{str(ref or '').upper()} {str(meta.get('value') or '').upper()} {str(meta.get('footprint') or '').upper()}"


def _shared_nets(ref_nets: Dict[str, Set[str]], ref: str, target_nets: Set[str]) -> Set[str]:
    return {net for net in (ref_nets.get(ref) or set()) if net in target_nets}


def _component_refs_by_keyword(components: Dict[str, Dict[str, Any]], *keywords: str) -> List[str]:
    tokens = tuple(keyword.upper() for keyword in keywords)
    rows: List[str] = []
    for ref, meta in (components or {}).items():
        text = _blob(ref, meta if isinstance(meta, dict) else {})
        if any(keyword in text for keyword in tokens):
            rows.append(str(ref))
    return sorted(rows)


def _external_power_connectors(connectors: List[Dict[str, Any]], rails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    input_rails = {str(row.get("net") or "") for row in (rails or []) if row.get("is_input_root")}
    rows: List[Dict[str, Any]] = []
    for connector in connectors or []:
        power_nets = [str(net) for net in (connector.get("power_nets") or [])]
        if not power_nets:
            continue
        if any(net in input_rails for net in power_nets) or any((_infer_nominal_voltage(net) or 0.0) >= 5.0 for net in power_nets):
            rows.append({"ref": connector.get("ref"), "power_nets": power_nets})
    return rows


def _actuation_connectors(connectors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for connector in connectors or []:
        value = str(connector.get("value") or "").upper()
        footprint = str(connector.get("footprint") or "").upper()
        nets = {str(net).upper() for net in (connector.get("pin_nets") or {}).values()}
        interface_names = {str(row.get("interface") or "").lower() for row in (connector.get("interfaces") or []) if isinstance(row, dict)}
        if any(token in value or token in footprint for token in ("MOTOR", "SERVO", "ESC", "FAN", "PUMP", "PHASE")):
            rows.append(connector)
            continue
        if any(net.startswith(("OUT", "PHASE", "MOT", "PWM")) or net in {"U", "V", "W", "A", "B"} for net in nets):
            rows.append(connector)
            continue
        if "power" in interface_names and any(net.startswith(("VM", "VBAT", "VIN")) for net in nets):
            rows.append(connector)
    return rows


def _shunt_rows(resistors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in resistors or []:
        ohms = row.get("ohms")
        if isinstance(ohms, (int, float)) and 0 < float(ohms) <= 0.25:
            rows.append(row)
    return rows


def _stage_kind(
    regulator: Dict[str, Any],
    inductor_refs: List[str],
    ref_nets: Dict[str, Set[str]],
    components: Dict[str, Dict[str, Any]],
) -> str:
    vin_net = str(regulator.get("vin_net") or "")
    vout_net = str(regulator.get("vout_net") or "")
    kind = str(regulator.get("kind") or "")
    ref = str(regulator.get("ref") or "")
    text = _blob(ref, (components or {}).get(ref) or {})
    touching_inductors = [ref for ref in inductor_refs if _shared_nets(ref_nets, ref, {vin_net, vout_net})]
    if ("ldo" in kind or any(token in text for token in ("1117", "AP2112", "XC620", "LDO"))) and not touching_inductors:
        return "ldo"
    vin_v = _infer_nominal_voltage(vin_net)
    vout_v = _infer_nominal_voltage(vout_net)
    if touching_inductors:
        if vin_v is not None and vout_v is not None and vin_v > vout_v:
            return "buck_like"
        if vin_v is not None and vout_v is not None and vin_v < vout_v:
            return "boost_like"
        return "switching_regulator"
    return "linear_regulator"


def analyze_power_control(
    *,
    components: Dict[str, Dict[str, Any]],
    ref_nets: Dict[str, Set[str]],
    category_by_ref: Dict[str, str],
    rails: List[Dict[str, Any]],
    regulators: List[Dict[str, Any]],
    connectors: List[Dict[str, Any]],
    active_components: List[Dict[str, Any]],
    resistors: List[Dict[str, Any]],
    capacitors: List[Dict[str, Any]],
    primary_role: str,
) -> Dict[str, Any]:
    del capacitors  # reserved for later deeper support heuristics

    inductor_refs = sorted(ref for ref, category in (category_by_ref or {}).items() if category == "inductor")
    protection_refs = sorted(
        set(_component_refs_by_keyword(components, "TVS", "ESD", "TRANSORB", "FUSE", "POLYFUSE", "PTC"))
        | {str(ref) for ref, category in (category_by_ref or {}).items() if category == "diode"}
    )
    external_inputs = _external_power_connectors(connectors, rails)
    actuator_connectors = _actuation_connectors(connectors)
    shunts = _shunt_rows(resistors)

    power_stages: List[Dict[str, Any]] = []
    risk_findings: List[Dict[str, Any]] = []
    protection_findings: List[Dict[str, Any]] = []
    control_stages: List[Dict[str, Any]] = []
    questions: List[str] = []

    for regulator in regulators or []:
        stage_kind = _stage_kind(regulator, inductor_refs, ref_nets, components)
        vin_net = str(regulator.get("vin_net") or "")
        vout_net = str(regulator.get("vout_net") or "")
        vin_v = _infer_nominal_voltage(vin_net)
        vout_v = _infer_nominal_voltage(vout_net)
        stage = {
            "ref": regulator.get("ref"),
            "kind": stage_kind,
            "vin_net": vin_net,
            "vout_net": vout_net,
            "vin_nominal_v": vin_v,
            "vout_nominal_v": vout_v,
            "support": {
                "inductor_refs": [ref for ref in inductor_refs if _shared_nets(ref_nets, ref, {vin_net, vout_net})],
            },
            "confidence": regulator.get("confidence"),
        }
        power_stages.append(stage)
        if stage_kind in {"ldo", "linear_regulator"} and vin_v is not None and vout_v is not None and (vin_v - vout_v) >= 5.0:
            risk_findings.append(
                {
                    "severity": "warning",
                    "topic": "linear_regulator_drop",
                    "message": f"{regulator.get('ref')} drops {vin_v:.1f}V to {vout_v:.1f}V as a linear stage; thermal headroom may be poor under load.",
                    "evidence": [vin_net, vout_net],
                }
            )

    for connector in external_inputs:
        power_nets = {str(net) for net in connector.get("power_nets") or []}
        touching_protection = [ref for ref in protection_refs if _shared_nets(ref_nets, ref, power_nets)]
        if touching_protection:
            protection_findings.append(
                {
                    "severity": "info",
                    "topic": "input_protection",
                    "status": "present",
                    "message": f"{connector.get('ref')} has protection-like components on its input rail.",
                    "evidence": touching_protection,
                }
            )
        else:
            protection_findings.append(
                {
                    "severity": "warning",
                    "topic": "input_protection",
                    "status": "missing",
                    "message": f"{connector.get('ref')} exposes external input power without obvious protection components on the same rail.",
                    "evidence": sorted(power_nets),
                }
            )
            questions.append(f"Confirm fuse/TVS/reverse-polarity strategy for external power connector {connector.get('ref')}.")

    motor_driver_refs = [str(row.get("ref")) for row in (active_components or []) if row.get("category") == "motor_driver"]
    for ref in motor_driver_refs:
        driver_nets = {net for net in (ref_nets.get(ref) or set()) if net and not is_power_net(net)}
        linked_connectors = [
            str(connector.get("ref"))
            for connector in actuator_connectors
            if driver_nets & {str(net) for net in (connector.get("pin_nets") or {}).values()}
        ]
        linked_shunts = [row["ref"] for row in shunts if {row.get("n1"), row.get("n2")} & (ref_nets.get(ref) or set())]
        control_stages.append(
            {
                "ref": ref,
                "kind": "motor_driver",
                "actuator_connectors": sorted(set(linked_connectors)),
                "current_sense_refs": sorted(set(linked_shunts)),
                "nets": sorted(driver_nets),
            }
        )
        if not linked_connectors:
            risk_findings.append(
                {
                    "severity": "warning",
                    "topic": "actuation_outputs",
                    "message": f"{ref} looks like a motor/actuation driver, but no matching actuator connector was extracted.",
                    "evidence": [ref],
                }
            )
        if not linked_shunts:
            risk_findings.append(
                {
                    "severity": "warning",
                    "topic": "current_sense",
                    "message": f"{ref} looks like a motor/actuation driver without obvious low-ohm current-sense resistors.",
                    "evidence": [ref],
                }
            )

    if primary_role == "motor_control" and not motor_driver_refs:
        questions.append("Board role looks motor-control-like, but no explicit motor-driver component was extracted.")

    summary = {
        "external_power_input_count": len(external_inputs),
        "actuation_connector_count": len(actuator_connectors),
        "power_stage_count": len(power_stages),
        "motor_driver_count": len(motor_driver_refs),
        "current_sense_count": len(shunts),
        "protection_component_count": len(protection_refs),
    }
    return {
        "summary": summary,
        "power_stages": power_stages,
        "control_stages": control_stages,
        "current_sense_refs": [row["ref"] for row in shunts],
        "protection_refs": protection_refs,
        "protection_findings": protection_findings,
        "risk_findings": risk_findings,
        "questions": questions,
    }
