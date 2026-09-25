from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PINMAP_PATH = ROOT / "hardware" / "reference_designs" / "benchhmi_v0" / "benchio_pinmap_v0.json"
VALIDATOR_PATH = ROOT / "hardware" / "reference_designs" / "benchhmi_v0" / "validate_benchio_pinmap.py"

SPEC = importlib.util.spec_from_file_location("benchio_pin_validator", VALIDATOR_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

PINMAP = json.loads(PINMAP_PATH.read_text())


def test_frozen_benchio_pinmap_is_conflict_free() -> None:
    result = MODULE.validate(PINMAP)
    assert result["result"] == "PASS"
    assert result["assignment_count"] == 23
    assert result["unique_physical_pin_count"] == 23


def test_usb_does_not_collide_with_fdcan() -> None:
    rows = {row["signal"]: row for row in PINMAP["assignments"]}
    assert rows["USB_DM"]["gpio"] == "PA11"
    assert rows["USB_DP"]["gpio"] == "PA12"
    assert rows["CAN_RX"]["gpio"] == "PB5"
    assert rows["CAN_TX"]["gpio"] == "PB6"


def test_debug_pins_stay_reserved_for_swd() -> None:
    rows = {row["signal"]: row for row in PINMAP["assignments"]}
    assert rows["SWDIO"]["gpio"] == "PA13"
    assert rows["SWCLK"]["gpio"] == "PA14"
    uart_gpio = {
        rows[key]["gpio"]
        for key in ["RS485_A_DE","RS485_A_TX","RS485_A_RX","RS485_B_DE","RS485_B_TX","RS485_B_RX"]
    }
    assert "PA13" not in uart_gpio
    assert "PA14" not in uart_gpio


def test_two_rs485_channels_use_separate_uart_instances() -> None:
    rows = {row["signal"]: row for row in PINMAP["assignments"]}
    assert rows["RS485_A_TX"]["function"] == "USART2_TX"
    assert rows["RS485_A_RX"]["function"] == "USART2_RX"
    assert rows["RS485_B_TX"]["function"] == "USART3_TX"
    assert rows["RS485_B_RX"]["function"] == "USART3_RX"
