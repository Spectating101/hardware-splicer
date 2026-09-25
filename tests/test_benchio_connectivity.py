from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/"hardware"/"reference_designs"/"benchhmi_v0"
CONNECTIVITY_PATH=DESIGN/"benchio_connectivity_v0.json"
VALIDATOR_PATH=DESIGN/"validate_benchio_connectivity.py"

SPEC=importlib.util.spec_from_file_location("benchio_connectivity_validator",VALIDATOR_PATH)
MODULE=importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
CONN=json.loads(CONNECTIVITY_PATH.read_text())


def test_benchio_active_connectivity_is_machine_consistent() -> None:
    result=MODULE.validate(CONN)
    assert result["result"]=="PASS"
    assert result["host_field_domain_separation"]=="PASS"
    assert result["authority"]["schematic_generation_authorized"] is True
    assert result["authority"]["schematic_verification_authorized"] is False


def test_rs485_half_duplex_enable_mapping_is_intentional() -> None:
    for ref,prefix in [("U2","RS485_A"),("U3","RS485_B")]:
        pins=CONN["parts"][ref]["pins"]
        assert pins["4"]==f"{prefix}_DE"
        assert pins["5"]==f"{prefix}_DE"
        assert pins["12"]==f"{prefix}_A"
        assert pins["13"]==f"{prefix}_B"


def test_field_power_never_comes_from_usb() -> None:
    u9=CONN["parts"]["U9"]["pins"]
    u10=CONN["parts"]["U10"]["pins"]
    assert u9["2"]=="FIELD_PROTECTED"
    assert u10["1"]=="USB_VBUS_5V"
    assert "USB_VBUS_5V" not in set(u9.values())
    assert "5V_FIELD" not in set(u10.values())


def test_iso1212_substrate_pins_are_floating_islands() -> None:
    for ref in ["U5","U6"]:
        pins=CONN["parts"][ref]["pins"]
        assert pins["12"].endswith("_SUB_FLOAT")
        assert pins["13"].endswith("_SUB_FLOAT")
        assert pins["12"] not in {"GND_HOST","GND_FIELD"}
        assert pins["13"] not in {"GND_HOST","GND_FIELD"}


def test_unfrozen_protection_parts_keep_verification_closed() -> None:
    assert CONN["pending_exact_parts"]
    assert CONN["authority"]["schematic_generation_authorized"] is True
    assert CONN["authority"]["schematic_verification_authorized"] is False
    assert CONN["authority"]["fabrication_authorized"] is False
