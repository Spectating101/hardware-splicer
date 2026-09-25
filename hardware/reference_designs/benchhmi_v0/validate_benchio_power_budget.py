#!/usr/bin/env python3
"""Validate BenchIO host/field power budgets and domain separation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def close(a: float, b: float, tol: float = 0.2) -> bool:
    return abs(a - b) <= tol


def validate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != "hardware_splicer.benchio_power_budget.v1":
        raise ValueError("unsupported BenchIO power budget schema")

    host = payload["host_usb"]
    host_sum = sum(float(row["ma"]) for row in host["allocations_ma"])
    if not close(host_sum, float(host["total_design_allocation_ma"])):
        raise ValueError(f"host budget arithmetic mismatch: {host_sum}")
    if host_sum > float(host["usb_pre_configuration_limit_ma"]):
        raise ValueError("host USB design allocation exceeds pre-configuration target")
    if not close(
        float(host["usb_pre_configuration_limit_ma"]) - host_sum,
        float(host["headroom_ma"]),
    ):
        raise ValueError("host headroom mismatch")

    field = payload["field_logic_5v"]
    field_sum = sum(float(row["ma"]) for row in field["loads_ma"])
    if not close(field_sum, float(field["raw_worst_case_ma"])):
        raise ValueError(f"field budget arithmetic mismatch: {field_sum}")
    required = field_sum * (1 + float(field["design_margin_fraction"]))
    if not close(required, float(field["required_with_margin_ma"])):
        raise ValueError("field margin arithmetic mismatch")
    capacity = float(field["regulator_capacity_ma"])
    if required > capacity:
        raise ValueError("field logic regulator capacity does not close")
    if not close(capacity - required, float(field["regulator_headroom_ma"])):
        raise ValueError("field regulator headroom mismatch")

    rejected = field["rejected_previous_candidate"]
    if float(rejected["capacity_ma"]) >= field_sum:
        raise ValueError("rejected previous converter no longer fails raw budget")
    if rejected["decision"] != "REJECT":
        raise ValueError("undersized previous converter must remain rejected")

    loads = payload["switched_field_loads"]
    nominal = int(loads["channels"]) * float(loads["nominal_current_limit_ma_per_channel"])
    if not close(nominal, float(loads["nominal_all_channels_ma"])):
        raise ValueError("switched-load current arithmetic mismatch")
    if loads["included_in_5v_field_logic_budget"] is not False:
        raise ValueError("switched output load must not be hidden in 5V logic budget")
    if loads["included_in_usb_budget"] is not False:
        raise ValueError("switched output load must never be assigned to USB")

    if payload["authority"]["fabrication_authorized"] is not False:
        raise ValueError("power budget may not authorize fabrication")
    if payload["authority"]["power_on_authorized"] is not False:
        raise ValueError("power budget may not authorize power-on")

    return {
        "schema":"hardware_splicer.benchio_power_budget_validation.v1",
        "result":"PASS",
        "host_usb_allocation_ma":round(host_sum,2),
        "host_usb_headroom_ma":round(float(host["usb_pre_configuration_limit_ma"]) - host_sum,2),
        "field_logic_raw_ma":round(field_sum,2),
        "field_logic_with_margin_ma":round(required,2),
        "field_logic_regulator_headroom_ma":round(capacity-required,2),
        "switched_field_nominal_all_channels_ma":round(nominal,2),
        "authority":{
            "schematic_power_budget_closed":True,
            "fabrication_authorized":False,
            "power_on_authorized":False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("budget", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.budget.read_text(encoding="utf-8"))
    print(json.dumps(validate(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
