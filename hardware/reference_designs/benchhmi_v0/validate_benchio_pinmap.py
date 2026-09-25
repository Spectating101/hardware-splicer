#!/usr/bin/env python3
"""Validate the frozen BenchIO STM32G0B1 LQFP48 pin map."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

EXPECTED = {
    "USB_DM": (33, "PA11", "USB_DM", None),
    "USB_DP": (34, "PA12", "USB_DP", None),
    "SWDIO": (35, "PA13", "SWDIO", 0),
    "SWCLK": (36, "PA14", "SWCLK", 0),
    "RS485_A_DE": (12, "PA1", "USART2_RTS_DE_CK", 1),
    "RS485_A_TX": (13, "PA2", "USART2_TX", 1),
    "RS485_A_RX": (14, "PA3", "USART2_RX", 1),
    "RS485_B_DE": (20, "PB1", "USART3_RTS_DE_CK", 4),
    "RS485_B_TX": (22, "PB10", "USART3_TX", 4),
    "RS485_B_RX": (23, "PB11", "USART3_RX", 4),
    "CAN_RX": (44, "PB5", "FDCAN2_RX", 3),
    "CAN_TX": (45, "PB6", "FDCAN2_TX", 3),
    "DI0_LOGIC": (15, "PA4", "GPIO_INPUT", None),
    "DI1_LOGIC": (16, "PA5", "GPIO_INPUT", None),
    "DI2_LOGIC": (17, "PA6", "GPIO_INPUT", None),
    "DI3_LOGIC": (18, "PA7", "GPIO_INPUT", None),
    "DO0_LOGIC": (21, "PB2", "GPIO_OUTPUT", None),
    "DO1_LOGIC": (42, "PB3", "GPIO_OUTPUT", None),
    "DO2_LOGIC": (43, "PB4", "GPIO_OUTPUT", None),
    "DO3_LOGIC": (46, "PB7", "GPIO_OUTPUT", None),
    "SPARE_GPIO0": (11, "PA0", "GPIO_OUTPUT", None),
    "STATUS_LED": (47, "PB8", "GPIO_OUTPUT", None),
    "FAULT_LED": (48, "PB9", "GPIO_OUTPUT", None),
}


def validate(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema") != "hardware_splicer.benchio_mcu_pinmap.v1":
        raise ValueError("unsupported pinmap schema")
    mcu = payload.get("mcu") or {}
    if mcu.get("part") != "STM32G0B1CBT6" or mcu.get("package") != "LQFP48":
        raise ValueError("unexpected MCU/package")

    assignments = payload.get("assignments")
    if not isinstance(assignments, list):
        raise ValueError("assignments must be a list")
    by_signal = {str(row.get("signal")): row for row in assignments if isinstance(row, Mapping)}
    if set(by_signal) != set(EXPECTED):
        missing = sorted(set(EXPECTED) - set(by_signal))
        extra = sorted(set(by_signal) - set(EXPECTED))
        raise ValueError(f"pinmap signal inventory mismatch missing={missing} extra={extra}")

    used_pins: dict[int, str] = {}
    used_gpio: dict[str, str] = {}
    errors: list[str] = []
    for signal, expected in EXPECTED.items():
        row = by_signal[signal]
        actual = (row.get("pin_number"), row.get("gpio"), row.get("function"), row.get("af"))
        if actual != expected:
            errors.append(f"{signal}: expected {expected}, got {actual}")
        pin = int(row["pin_number"])
        gpio = str(row["gpio"])
        if pin in used_pins:
            errors.append(f"physical pin conflict: {pin} {used_pins[pin]} {signal}")
        if gpio in used_gpio:
            errors.append(f"GPIO conflict: {gpio} {used_gpio[gpio]} {signal}")
        used_pins[pin] = signal
        used_gpio[gpio] = signal

    if by_signal["USB_DM"]["gpio"] in {by_signal["CAN_RX"]["gpio"], by_signal["CAN_TX"]["gpio"]}:
        errors.append("USB/CAN conflict")
    if by_signal["USB_DP"]["gpio"] in {by_signal["CAN_RX"]["gpio"], by_signal["CAN_TX"]["gpio"]}:
        errors.append("USB/CAN conflict")
    if {by_signal["SWDIO"]["gpio"], by_signal["SWCLK"]["gpio"]} & {
        by_signal["RS485_A_TX"]["gpio"], by_signal["RS485_A_RX"]["gpio"],
        by_signal["RS485_B_TX"]["gpio"], by_signal["RS485_B_RX"]["gpio"],
    }:
        errors.append("SWD/UART conflict")

    if errors:
        raise ValueError("; ".join(errors))

    return {
        "schema": "hardware_splicer.benchio_pinmap_validation.v1",
        "result": "PASS",
        "assignment_count": len(assignments),
        "unique_physical_pin_count": len(used_pins),
        "unique_gpio_count": len(used_gpio),
        "peripherals": {
            "usb":"PA11/PA12",
            "rs485_a":"USART2 PA1/PA2/PA3",
            "rs485_b":"USART3 PB1/PB10/PB11",
            "can":"FDCAN2 PB5/PB6",
            "swd":"PA13/PA14",
        },
        "authority": {
            "pinmap_frozen_for_schematic": True,
            "schematic_verified": False,
            "fabrication_authorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pinmap", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.pinmap.read_text(encoding="utf-8"))
    print(json.dumps(validate(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
