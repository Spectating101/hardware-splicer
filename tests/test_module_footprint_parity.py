"""Python and TypeScript resolve the same module footprints, because both read one data file.

``src/hardware_splicer/data/module_footprints.json`` is the single source of truth. The
TypeScript table is generated from it, and these tests fail if either side drifts: a stale
generated file, a different synthetic fallback, or an edit made in only one language.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from hardware_splicer.pcb import module_registry as registry

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "src" / "hardware_splicer" / "data" / "module_footprints.json"
FRONTEND = ROOT / "apps" / "circuit-ai" / "circuit-ai-frontend"
GENERATED_TS = FRONTEND / "lib" / "modules" / "module-footprint-data.generated.ts"


def _payload() -> Dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _pads(pads: List[Dict[str, Any]] | None) -> List[Tuple[str, float, float]]:
    return [(p["pinId"], round(float(p["x"]), 4), round(float(p["y"]), 4)) for p in (pads or [])]


def _fit(fit: Dict[str, Any]) -> Tuple[str, str]:
    if fit["status"] == "verified_against":
        return fit["status"], fit.get("verified_against") or fit.get("verifiedAgainst")
    return fit["status"], fit["reason"]


def test_data_file_is_the_only_source_of_python_footprints() -> None:
    payload = _payload()
    assert payload["schema_version"] == "hardware_splicer.module_footprints.v1"
    assert set(registry._MODULE_FOOTPRINTS) == set(payload["modules"])
    for module_id, meta in payload["modules"].items():
        assert _pads(registry.resolve_module_pads(module_id)) == _pads(meta.get("pads")), module_id
        assert registry.resolve_module_footprint(module_id) == meta.get("kicadFootprint", f"Circuit.AI:{module_id}")
        assert registry.resolve_module_body_mm(module_id) == meta.get("bodyMm")


def test_every_footprint_record_is_well_formed() -> None:
    for module_id, meta in _payload()["modules"].items():
        if meta.get("pinsFrom"):
            assert meta["fit"]["status"] == "unverified_variant", module_id
            assert not any(key in meta for key in ("pads", "bodyMm")), module_id
            base = registry.find_module(meta["pinsFrom"])
            assert base, module_id
            count = len(base["pins"])
            assert meta["kicadFootprint"] == (
                f"Connector_PinHeader_2.54mm:PinHeader_2x{count // 2:02d}_P2.54mm_Vertical"
            ), module_id
            spec = registry.find_module(module_id)
            pads = registry.resolve_module_pads(module_id, spec)
            assert len(pads) == count and len({p["pinId"] for p in pads}) == count, module_id
            continue
        assert meta["kicadFootprint"], module_id
        assert meta["bodyMm"]["w"] > 0 and meta["bodyMm"]["h"] > 0, module_id
        pad_ids = [p["pinId"] for p in meta["pads"]]
        assert pad_ids, module_id
        assert len(pad_ids) == len(set(pad_ids)), f"{module_id}: duplicate pad id"
        fit = meta["fit"]
        assert fit["status"] in ("verified_against", "unverified_variant"), module_id
        if fit["status"] == "verified_against":
            assert str(fit.get("verified_against") or "").strip(), f"{module_id}: empty citation"
        else:
            assert str(fit.get("reason") or "").strip(), f"{module_id}: empty reason"


# Declared pins that are deliberately not header pads: the USB port of the CH340 adapter is an
# on-board connector, not a pad the carrier PCB can accept.
PINS_WITHOUT_A_PAD = {
    "ch340-usb-ttl": {"USB"},
}


def test_every_declared_pin_has_a_pad() -> None:
    """A pin the registry declares needs a physical pad, or a recipe wire can vanish before DRC."""
    library = registry._load_library()
    for module_id, meta in _payload()["modules"].items():
        spec = library.get(module_id)
        if spec is None or meta.get("pinsFrom"):
            continue
        spec_pins = {p["id"] for p in spec["pins"]}
        pad_ids = {p["pinId"] for p in meta["pads"]}
        missing = spec_pins - pad_ids - PINS_WITHOUT_A_PAD.get(module_id, set())
        assert not missing, f"{module_id}: declared pins without a pad {sorted(missing)}"


def test_generated_typescript_table_is_current() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("export_module_footprints_ts", ROOT / "scripts" / "export_module_footprints_ts.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert GENERATED_TS.read_text(encoding="utf-8") == module.render(_payload()), (
        "module-footprint-data.generated.ts is stale: run python scripts/export_module_footprints_ts.py"
    )


def _typescript_node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    if not (FRONTEND / "node_modules" / "typescript").exists():
        try:
            subprocess.run([node, "-e", "require('typescript')"], cwd=ROOT, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pytest.skip("the typescript package is not installed (run npm ci in the frontend)")
    return node


def _typescript_resolution() -> Dict[str, Any]:
    node = _typescript_node()
    proc = subprocess.run(
        [node, str(ROOT / "scripts" / "dump_ts_module_pads.cjs")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return json.loads(proc.stdout)


def test_typescript_registry_reload_does_not_mutate_sources_or_allocations() -> None:
    node = _typescript_node()
    script = """
const assert = require('node:assert/strict');
const path = require('node:path');
require('./scripts/compile_geometry.cjs'); // Installs the existing TypeScript loader.
const modules = path.resolve('apps/circuit-ai/circuit-ai-frontend/lib/modules');
const libraryPath = path.join(modules, 'module-library.ts');
const data = require(path.join(modules, 'module-footprint-data.generated.ts'));
const planPath = path.join(modules, '../salvage/plan-to-graph.ts');
const first = require(libraryPath).MODULE_LIBRARY;
const snapshot = JSON.stringify(first);
const ids = ['esp32-devkit', 'max98357a-i2s-amp', 'usb-power-5v'];
const allocate = () => require(planPath).composeBuildGraphFromModuleIds(ids);
const expected = allocate();
function freeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
}
for (const source of ['curated-extended', 'ingested-kb', 'ingested-datasheets', 'ingested', 'ingested-pinouts']) {
  freeze(require(path.join(modules, source + '.ts')));
}
freeze(first);
for (let i = 0; i < 2; i++) {
  data.MODULE_FOOTPRINT_DATA = Object.fromEntries(Object.entries(data.MODULE_FOOTPRINT_DATA).reverse());
  delete require.cache[libraryPath];
  delete require.cache[require.resolve(planPath)];
  const next = require(libraryPath).MODULE_LIBRARY;
  assert.equal(new Set(next.map((m) => m.id)).size, next.length);
  assert.deepEqual(Object.fromEntries(next.map((m) => [m.id, m])), Object.fromEntries(first.map((m) => [m.id, m])));
  assert.deepEqual(allocate(), expected);
  assert.equal(JSON.stringify(first), snapshot);
  for (const [id, meta] of Object.entries(data.MODULE_FOOTPRINT_DATA)) {
    if (!meta.pinsFrom) continue;
    const variant = next.find((m) => m.id === id);
    const base = next.find((m) => m.id === meta.pinsFrom);
    assert.notEqual(variant.pins, base.pins);
    assert.notEqual(variant.pins[0], base.pins[0]);
  }
}
"""
    proc = subprocess.run(
        [node, "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_python_and_typescript_resolve_identical_pads_for_every_module() -> None:
    """Includes the synthetic fallback every module without a registered footprint uses."""
    ts = _typescript_resolution()
    library = registry._load_library()
    ids = set(ts) | set(library) | set(registry._MODULE_FOOTPRINTS)
    assert ts, "the TypeScript side resolved no modules"
    differing: List[str] = []
    for module_id in sorted(ids):
        if module_id not in ts:
            # Python-only alias of a TypeScript module (mini-pump-5v is an explicit footprint,
            # so it is always listed); anything else would be a missing TypeScript module.
            differing.append(f"{module_id}: absent from the TypeScript library")
            continue
        spec = library.get(module_id)
        py_pads = _pads(registry.resolve_module_pads(module_id, spec))
        ts_pads = _pads(ts[module_id]["pads"])
        if py_pads != ts_pads:
            differing.append(f"{module_id}: python {py_pads[:3]}... != typescript {ts_pads[:3]}...")
            continue
        if registry.resolve_module_footprint(module_id) != ts[module_id]["kicadFootprint"]:
            differing.append(f"{module_id}: footprint name differs")
        if registry.resolve_module_body_mm(module_id) != ts[module_id]["bodyMm"]:
            differing.append(f"{module_id}: body envelope differs")
        if _fit(registry.resolve_module_fit(module_id)) != _fit(ts[module_id]["fit"]):
            differing.append(f"{module_id}: fit record differs")
    assert not differing, "Python and TypeScript disagree:\n" + "\n".join(differing)


@pytest.mark.parametrize("module_id,expected", [
    ("esp32-cam-module", {"GPIO16"}),
    ("esp32-devkit", {f"GPIO{i}" for i in range(6, 12)}),
    ("arduino-nano", {"D0", "D1"}),
])
def test_reserved_pins_carry_shared_reasons_and_remain_in_geometry(module_id: str, expected: set[str]) -> None:
    spec = registry.find_module(module_id)
    assert spec
    reserved = {p["id"]: p["reserved"] for p in spec["pins"] if p.get("reserved")}
    assert set(reserved) == expected
    assert reserved == _payload()["modules"][module_id]["reservedPins"]
    assert expected <= {p["pinId"] for p in registry.resolve_module_pads(module_id, spec)}


def test_no_python_pin_allocator_returns_a_reserved_pin() -> None:
    from hardware_splicer.auto_wire import _alloc_gpio, _alloc_pin_by_role, _first_pin, _pin_by_role
    from hardware_splicer.inventory_topology import _module_pin_ids

    for module_id, spec in registry._load_library().items():
        reserved = {p["id"] for p in spec["pins"] if p.get("reserved")}
        assert not reserved.intersection(_module_pin_ids(module_id))
        used: set[str] = set()
        while (pin_id := _alloc_gpio(spec, used)) is not None:
            assert pin_id not in reserved
        for role in {p["role"] for p in spec["pins"]}:
            assert _pin_by_role(spec, role) not in reserved
            used = set()
            while (pin_id := _alloc_pin_by_role(spec, used, role)) is not None:
                assert pin_id not in reserved
        assert _first_pin(spec, lambda p: p["id"] in reserved) is None

    # Check both the preferred list and generic fallback even if pin roles change later.
    only_reserved = {"pins": [
        {"id": "GPIO12", "role": "digital_io", "reserved": "test preferred"},
        {"id": "GPIO99", "role": "digital_io", "reserved": "test fallback"},
    ]}
    assert _alloc_gpio(only_reserved, set()) is None
    assert _alloc_pin_by_role(only_reserved, set(), "digital_io") is None
