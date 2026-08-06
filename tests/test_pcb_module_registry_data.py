from __future__ import annotations

import json
from pathlib import Path

from hardware_splicer.pcb import module_registry


def test_canonical_pcb_engine_data_is_present_and_loadable() -> None:
    data_path = Path(module_registry.__file__).resolve().parent.parent / "data" / "engine_pcb_data.json"

    assert data_path.is_file(), f"missing packaged PCB engine data: {data_path}"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "hardware_splicer.engine_pcb_data.v1"
    assert len(payload["module_library"]) >= 10

    usb_power = module_registry.find_module("usb-power-5v")
    assert usb_power is not None
    assert usb_power["id"] == "usb-power-5v"


def test_generated_registry_contains_footprint_metadata() -> None:
    footprint = module_registry.resolve_module_footprint("usb-power-5v")

    assert isinstance(footprint, str)
    assert footprint
