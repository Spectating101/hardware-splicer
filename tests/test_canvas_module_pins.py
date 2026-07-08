"""Canvas module catalog pin + footprint contract — guards agent/Design Studio compose."""

from __future__ import annotations

from hardware_splicer.pcb.module_registry import (
    _MODULE_FOOTPRINTS,
    find_module,
    list_canvas_modules,
    resolve_module_footprint,
    resolve_module_pads,
)


def test_canvas_catalog_matches_footprint_registry() -> None:
    modules = list_canvas_modules()
    assert len(modules) >= 50
    assert len(modules) == len(_MODULE_FOOTPRINTS)
    ids = {m["id"] for m in modules}
    assert ids == set(_MODULE_FOOTPRINTS.keys())


def test_canvas_modules_have_unique_pins_and_pads() -> None:
    errors: list[str] = []
    for module in list_canvas_modules():
        module_id = str(module["id"])
        pins = module.get("pins") or []
        pin_ids = [str(p.get("id") or "") for p in pins]
        if not pin_ids:
            errors.append(f"{module_id}: no pins")
            continue
        if len(pin_ids) != len(set(pin_ids)):
            errors.append(f"{module_id}: duplicate pin ids")
        footprint = resolve_module_footprint(module_id)
        if not footprint or footprint.startswith("Circuit.AI:"):
            errors.append(f"{module_id}: missing KiCad footprint")
        pads = resolve_module_pads(module_id, module) or []
        if not pads:
            errors.append(f"{module_id}: no pads resolved")
            continue
        pad_ids = {str(p.get("pinId") or "") for p in pads}
        unknown = pad_ids - set(pin_ids)
        if unknown:
            errors.append(f"{module_id}: pads not in spec pins: {sorted(unknown)}")
    assert not errors, "canvas pin contract errors:\n" + "\n".join(errors)


def test_find_module_covers_canvas_ids() -> None:
    for module_id in _MODULE_FOOTPRINTS:
        assert find_module(module_id) is not None, module_id
