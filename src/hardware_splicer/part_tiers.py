"""One catalogue over every part HS knows, saying what HS can do with each.

HS keeps parts in two libraries that grew apart:

* the device planner's library (``data/device_modules.json``): few parts, each with a measured outline, pin positions and a
  cited source for every figure. Only these can be planned into a case, given firmware, made into a lab or reviewed;
* the engine library (``data/engine_pcb_data.json``): many parts with pin roles, voltages and usually a datasheet link. Those
  with a KiCad footprint can be placed on a schematic and PCB; the rest can only have their wiring checked.

This module lists both, with each part's capabilities, and links an engine part to a planner module only where the planner
module's cited chip marking or the engine part's part number names the same chip. That link says "this cited board carries
this chip", never "these are the same product": a bare chip, a generic breakout and an Adafruit board differ in regulators,
pull-ups and pin order. Nothing here promotes a part from one tier to another.

    PYTHONPATH=src python -m hardware_splicer.part_tiers [search text]
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from typing import Any

from .device_plan import module_library
from .i2c_addresses import i2c_addresses_for
from .pcb.module_registry import _MODULE_FOOTPRINTS, _load_library

SCHEMA = "hardware_splicer.part_catalog.v1"
CAPABILITIES = {
    "device_plan": "wired plan, printable case, firmware, lab pack and engineering review (cited outline and pins)",
    "pcb_compose": "placed on a KiCad schematic and PCB (has a footprint)",
    "wiring_check": "wiring checked by pin role and voltage (no outline, so no case)",
    "design_review": "WireStudio part or board: HS reviews WireStudio designs that use it (wirestudio_bridge)",
}


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def unified_catalog(query: str | None = None) -> dict[str, Any]:
    planner = module_library()["modules"]
    engine = list(_load_library().values())
    footprints = set(_MODULE_FOOTPRINTS)
    rows: list[dict[str, Any]] = []
    chip_to_planner: dict[str, list[str]] = defaultdict(list)
    for module in planner:
        for chip in module.get("chips", []):
            chip_to_planner[_norm(chip["marking"])].append(module["id"])
        rows.append({
            "id": module["id"], "label": module["name"], "library": "device_planner", "category": module["kind"],
            "capabilities": ["device_plan", "wiring_check"],
            "i2c_addresses": module.get("i2c", {}).get("addresses", []),
            "sources": [s["url"] for s in module["sources"]], "evidence": "every figure cited, outline and pins measured or from the maker's files",
        })
    for part in engine:
        caps = (["pcb_compose"] if part["id"] in footprints else []) + ["wiring_check"]
        addresses = i2c_addresses_for(str(part["id"]))
        keys = {_norm(part.get("partNumber")), _norm(part["id"])} - {""}
        boards = sorted({m for key in keys for m in chip_to_planner.get(key, [])})
        rows.append({
            "id": part["id"], "label": part.get("label", part["id"]), "library": "engine", "category": part.get("category"),
            "capabilities": caps, "i2c_addresses": addresses["addresses"] if addresses else [],
            "sources": [u for u in (part.get("datasheetUrl"), part.get("source")) if isinstance(u, str) and u.startswith("http")],
            "price_usd": part.get("priceUsd"),
            "evidence": "engine library data: pin roles and voltages, not cited figure by figure",
            **({"cited_boards_with_this_chip": boards} if boards else {}),
        })
    from .wirestudio_bridge import PART_FILE_ERRATA, snapshot

    ws = snapshot()
    for kind, items in (("component", ws["components"]), ("board", ws["boards"])):
        for ws_id, item in items.items():
            rows.append({
                "id": f"wirestudio:{ws_id}", "label": item.get("name", ws_id), "library": "wirestudio",
                "category": item.get("category") or ("board" if kind == "board" else None), "capabilities": ["design_review"],
                "i2c_addresses": [], "sources": [f"{ws['meta']['source']}/tree/{ws['meta']['commit']}"],
                "evidence": "WireStudio's part data, imported unchanged (MIT); HS has not cited it figure by figure",
                **({"known_part_file_error": PART_FILE_ERRATA[ws_id]["maker_value"]} if ws_id in PART_FILE_ERRATA else {}),
            })
    # Engine entries that name the same part twice (an id with and without "_board", hyphen and underscore spellings).
    by_number: dict[str, list[str]] = defaultdict(list)
    for part in engine:
        if part.get("partNumber"):
            by_number[_norm(part["partNumber"])].append(part["id"])
    duplicates = sorted(sorted(ids) for ids in by_number.values() if len(ids) > 1)
    if query:
        needle = query.strip().lower()
        rows = [r for r in rows if needle in r["id"].lower() or needle in str(r["label"]).lower()]
    counts = {cap: sum(1 for r in rows if cap in r["capabilities"]) for cap in CAPABILITIES}
    return {"schema_version": SCHEMA, "count": len(rows), "capability_counts": counts, "capabilities": CAPABILITIES,
            "engine_entries_sharing_a_part_number": duplicates, "parts": rows,
            "note": "A part gains a capability only by adding its evidence (an outline, pin positions, cited figures); nothing is inferred."}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    catalog = unified_catalog(" ".join(args) or None)
    print(json.dumps({k: v for k, v in catalog.items() if k != "parts"}, indent=2))
    for row in catalog["parts"]:
        extra = f"  -> cited board: {', '.join(row['cited_boards_with_this_chip'])}" if row.get("cited_boards_with_this_chip") else ""
        print(f"{row['id']:<40} {row['library']:<15} {','.join(row['capabilities']):<35}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


class PartCheckError(ValueError):
    pass


def check_any_wiring(spec: Any) -> dict[str, Any]:
    """Check a device spec's wiring whichever library its parts come from.

    A spec whose parts are all planner modules gets the full device plan (case, steps, cited findings). A spec of engine parts
    gets the engine's wiring rules (shorts, supply voltage, logic level, I2C, unpowered or unearthed modules) and says plainly
    that no case or lab can be made, because those parts have no measured outline. Mixing the two libraries in one spec is
    refused: a planner module and an engine part are not interchangeable records.
    """
    from .device_plan import DevicePlanError, build_device_plan
    from .pcb.module_registry import find_module, find_pin
    from .pcb.safety_rules import analyze_build

    if not isinstance(spec, dict) or not isinstance(spec.get("modules"), list) or not spec["modules"]:
        raise PartCheckError("the spec needs a modules list of {id, module}")
    planner_ids = {m["id"] for m in module_library()["modules"]}
    chosen = []
    for row in spec["modules"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("module"), str):
            raise PartCheckError("each module needs a text id and module")
        chosen.append((row["id"], row["module"]))
    if len({ref for ref, _ in chosen}) != len(chosen):
        raise PartCheckError("module ids must be unique")
    in_planner = {ref for ref, mod in chosen if mod in planner_ids}
    if len(in_planner) == len(chosen):
        try:
            plan = build_device_plan(spec)
        except DevicePlanError as exc:
            raise PartCheckError(str(exc)) from exc
        return {"schema_version": SCHEMA, "library": "device_planner", "capabilities": ["device_plan", "wiring_check"],
                "findings": plan["findings"], "counts": plan["counts"], "plan": plan}
    if in_planner:
        raise PartCheckError(f"{', '.join(sorted(in_planner))} come from the device planner and the rest from the engine library; "
                             "use engine ids for every part (see cited_boards_with_this_chip in the catalogue for the links)")
    nodes, errors = [], []
    for ref, mod in chosen:
        if find_module(mod) is None:
            errors.append(f"{ref}: no part {mod!r} in either library")
        nodes.append({"id": ref, "moduleId": mod})
    wires = []
    for index, wire in enumerate(spec.get("connections", [])):
        ends = []
        for key in ("from", "to"):
            end = wire.get(key) if isinstance(wire, dict) else None
            if not isinstance(end, str) or end.count(".") != 1:
                errors.append(f"connections[{index}].{key} must look like module.PIN")
                break
            ref, pin = end.split(".")
            mod = dict(chosen).get(ref)
            spec_mod = find_module(mod) if mod else None
            if spec_mod is None:
                errors.append(f"connections[{index}].{key}: there is no module {ref!r}")
                break
            if find_pin(spec_mod, pin) is None:
                names = ", ".join(p["id"] for p in spec_mod.get("pins", []))
                errors.append(f"connections[{index}].{key}: {mod} has no pin {pin!r} (it has {names})")
                break
            ends.append({"nodeId": ref, "pinId": pin})
        if len(ends) == 2:
            wires.append({"id": f"wire-{index + 1:02d}", "from": ends[0], "to": ends[1]})
    if errors:
        raise PartCheckError("; ".join(errors))
    warnings = analyze_build({"nodes": nodes, "wires": wires})
    severity = {"error": "error", "warn": "warning", "info": "info"}
    findings = [{"severity": severity.get(w.get("level"), "info"), "rule": w["id"].split("-")[-1] if "-" in w["id"] else w["id"],
                 "message": w["message"], "basis": "engine library pin roles and voltages, not cited figure by figure",
                 **({"wire": w["wireId"]} if w.get("wireId") else {})} for w in warnings]
    missing_logic = sorted({mod for _, mod in chosen if find_module(mod).get("logicVoltage") is None})
    if missing_logic:
        findings.append({"severity": "info", "rule": "logic_level_unknown",
                         "message": f"The engine library gives no logic voltage for {', '.join(missing_logic)}, so a 5 V signal into a 3.3 V pin "
                                    "cannot be ruled out for their wires. Check each part's datasheet.",
                         "basis": "engine library: logicVoltage missing"})
    findings.append({"severity": "info", "rule": "no_case", "message": "These are engine-library parts with no measured outline or pin "
                     "positions, so HS makes no case, wire lengths, lab or engineering review for this spec.", "basis": "part_tiers"})
    counts = {"errors": sum(f["severity"] == "error" for f in findings), "warnings": sum(f["severity"] == "warning" for f in findings)}
    return {"schema_version": SCHEMA, "library": "engine", "capabilities": ["wiring_check"], "findings": findings, "counts": counts,
            "physical_correctness": "UNPROVEN"}
