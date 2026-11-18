from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

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


@pytest.mark.parametrize("phrase", ["play a tone on a speaker", "audio amp for notifications"])
def test_registry_reloads_and_lookup_order_preserve_audio_allocations(monkeypatch, phrase: str) -> None:
    from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
    from hardware_splicer.module_picker import pick_modules_for_goal

    modules = json.loads(module_registry._DATA_PATH.read_text(encoding="utf-8"))["module_library"]
    footprints = deepcopy(module_registry._MODULE_FOOTPRINTS)
    original_modules = deepcopy(modules)
    original_footprints = deepcopy(footprints)
    library = module_registry._build_library(modules, footprints)
    assert modules == original_modules and footprints == original_footprints
    monkeypatch.setattr(module_registry, "_MODULE_LIBRARY", library)

    def compose() -> dict:
        return compose_build_graph_from_module_ids(pick_modules_for_goal(phrase).module_ids)["graph"]

    expected = compose()
    for _ in range(2):
        monkeypatch.setattr(module_registry, "_MODULE_LIBRARY", None)
        for mid in ("dht22-breakout-3pin", "esp32-doit-30pin", "dht22", "esp32-devkit"):
            module_registry.find_module(mid)
        assert compose() == expected

    rebuilt = module_registry._build_library(list(library.values()), footprints)
    reversed_library = module_registry._build_library(list(reversed(modules)), dict(reversed(footprints.items())))
    assert library == rebuilt == reversed_library
    for candidate in (rebuilt, reversed_library):
        monkeypatch.setattr(module_registry, "_MODULE_LIBRARY", candidate)
        assert compose() == expected

    # Consumers may edit returned specs without changing the registry or later allocations.
    specs = [module_registry.find_module("esp32-devkit")]
    specs += module_registry.list_canvas_modules()
    specs += module_registry.find_modules_by_capabilities([["controller"]])
    for spec in specs:
        spec["pins"].reverse()
        spec.setdefault("capabilityTags", []).append("test-only")
        for pin in spec["pins"]:
            pin.pop("reserved", None)
    assert compose() == expected
    assert module_registry._load_library() == library
    assert library["esp32-doit-30pin"]["pins"] is not library["esp32-devkit"]["pins"]


def test_audio_allocations_and_drc_do_not_depend_on_python_hash_seed() -> None:
    script = """
import json
from hardware_splicer.auto_wire import compose_build_graph_from_module_ids
from hardware_splicer.module_picker import pick_modules_for_goal
from hardware_splicer.pcb.build_to_geometry import build_graph_to_geometry
from hardware_splicer.pcb.drc import run_drc
results = []
for phrase in ('play a tone on a speaker', 'audio amp for notifications'):
    ids = pick_modules_for_goal(phrase).module_ids
    graph = compose_build_graph_from_module_ids(ids)['graph']
    results.append((graph, run_drc(build_graph_to_geometry(graph))))
print(json.dumps(results, sort_keys=True))
"""
    results = []
    source = str(Path(__file__).resolve().parents[1] / "src")
    for seed in ("1", "2", "3"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            env={**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": source},
            check=True, capture_output=True, text=True, timeout=60,
        )
        results.append(json.loads(proc.stdout))
    assert results[0] == results[1] == results[2]
