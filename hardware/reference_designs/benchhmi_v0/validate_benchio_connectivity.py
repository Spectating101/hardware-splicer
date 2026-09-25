#!/usr/bin/env python3
"""Deterministic topology checks for the BenchIO net-level connectivity contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def validate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != "hardware_splicer.benchio_connectivity.v1":
        raise ValueError("unsupported BenchIO connectivity schema")
    parts = payload.get("parts")
    if not isinstance(parts, Mapping):
        raise ValueError("parts mapping required")

    errors: list[str] = []

    def pins(ref: str) -> dict[str, str]:
        row = parts.get(ref)
        if not isinstance(row, Mapping) or not isinstance(row.get("pins"), Mapping):
            errors.append(f"missing pins for {ref}")
            return {}
        return {str(k): str(v) for k, v in row["pins"].items()}

    u2,u3,u4,u5,u6,u7,u8,u9,u10,u11 = [pins(ref) for ref in ["U2","U3","U4","U5","U6","U7","U8","U9","U10","U11"]]

    for ref, p, prefix in [("U2",u2,"RS485_A"),("U3",u3,"RS485_B")]:
        if p.get("4") != f"{prefix}_DE" or p.get("5") != f"{prefix}_DE":
            errors.append(f"{ref} DE and active-low RE must share {prefix}_DE")
        if p.get("12") != f"{prefix}_A" or p.get("13") != f"{prefix}_B":
            errors.append(f"{ref} bus A/B mapping wrong")
        if p.get("1") != "3V3_HOST" or p.get("16") != "5V_FIELD":
            errors.append(f"{ref} isolation supply domains wrong")
        if p.get("2") != "GND_HOST" or p.get("9") != "GND_FIELD":
            errors.append(f"{ref} isolation ground domains wrong")

    expected_can={"1":"3V3_HOST","2":"CAN_TX","3":"CAN_RX","4":"GND_HOST","5":"GND_FIELD","6":"CAN_L","7":"CAN_H","8":"5V_FIELD"}
    if u4 != expected_can:
        errors.append("U4 must use exact ISO1042 DWV-8 mapping")

    if parts["U8"].get("part") != "ISO6740DWR":
        errors.append("U8 must be ISO6740DWR 4-forward variant")
    if [u8.get(str(n)) for n in [3,4,5,6]] != ["DO0_LOGIC","DO1_LOGIC","DO2_LOGIC","DO3_LOGIC"]:
        errors.append("U8 host inputs do not map DO0-DO3 in order")
    if [u8.get(str(n)) for n in [14,13,12,11]] != ["DO0_FIELD_CTL","DO1_FIELD_CTL","DO2_FIELD_CTL","DO3_FIELD_CTL"]:
        errors.append("U8 field outputs do not map DO0-DO3 in order")

    for ref,p,base in [("U5",u5,0),("U6",u6,2)]:
        if p.get("1")!="GND_HOST" or p.get("2")!="3V3_HOST" or p.get("8")!="GND_HOST":
            errors.append(f"{ref} host supply domain wrong")
        for subpin in ["12","13"]:
            net=p.get(subpin,"")
            if not net.endswith("_SUB_FLOAT"):
                errors.append(f"{ref}.{subpin} must use floating SUB island")
            if net in {"GND_HOST","GND_FIELD"}:
                errors.append(f"{ref}.{subpin} illegally grounded")

    if any(u7.get(str(pin))!="FIELD_PROTECTED" for pin in [20,21,22,23]):
        errors.append("TPS4H160 VS pins must all use FIELD_PROTECTED")
    if u7.get("13")!="5V_FIELD" or u7.get("14")!="GND_FIELD":
        errors.append("TPS THER/DIAG_EN safe-state mapping wrong")
    if [u7.get(str(pin)) for pin in [27,25,17,15]] != ["DO0","DO1","DO2","DO3"]:
        errors.append("TPS output channel ordering wrong")

    if u9.get("2")!="FIELD_PROTECTED" or u9.get("1")!="GND_FIELD" or u9.get("5")!="FIELD_FB":
        errors.append("LMR36510 field buck primary pins wrong")
    if u10 != {"1":"USB_VBUS_5V","2":"GND_HOST","3":"USB_VBUS_5V","4":"NC","5":"3V3_HOST"}:
        errors.append("TLV75533 DBV mapping wrong")
    if u11 != {"1":"USB_DP","2":"USB_DM","3":"GND_HOST"}:
        errors.append("USB ESD mapping wrong")

    host_nets={"USB_VBUS_5V","3V3_HOST","GND_HOST"}
    field_nets={"FIELD_PROTECTED","5V_FIELD","GND_FIELD"}
    for ref,row in parts.items():
        if not isinstance(row, Mapping) or not isinstance(row.get("pins"), Mapping):
            continue
        nets=set(map(str,row["pins"].values()))
        # Crossing both domains is legal only in the named isolation components.
        if nets & host_nets and nets & field_nets:
            if ref not in {"U2","U3","U4","U5","U6","U8"}:
                errors.append(f"{ref} illegally spans host and field domains")

    if not payload.get("pending_exact_parts"):
        errors.append("pending protection/mechanical exact parts must remain explicit until frozen")
    if payload["authority"].get("schematic_verification_authorized") is not False:
        errors.append("schematic verification must remain closed while exact protection parts are pending")
    if payload["authority"].get("fabrication_authorized") is not False:
        errors.append("connectivity contract may not authorize fabrication")

    if errors:
        raise ValueError("; ".join(errors))
    return {
        "schema":"hardware_splicer.benchio_connectivity_validation.v1",
        "result":"PASS",
        "checked_parts":len(parts),
        "pending_exact_part_count":len(payload["pending_exact_parts"]),
        "host_field_domain_separation":"PASS",
        "authority":{
            "schematic_generation_authorized":True,
            "schematic_verification_authorized":False,
            "fabrication_authorized":False,
        }
    }


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("connectivity",type=Path)
    args=parser.parse_args()
    payload=json.loads(args.connectivity.read_text(encoding="utf-8"))
    print(json.dumps(validate(payload),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
