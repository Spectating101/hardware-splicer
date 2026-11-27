"""Any component-level board, from a JSON design to checked KiCad files and fab outputs.

The pipeline HS-BUS-A proved, for any design an agent writes:

    schematic   symbols from the KiCad libraries, pin coverage, KiCad's read-back netlist == design, ERC
    pcb         footprints placed where the design says, every net routed by FreeRouting in one pass (net classes set
                the power widths), router leftovers removed, ground stitching and pours, reference labels moved off copper
                and other parts' outlines, DRC with schematic parity
    fab         Gerbers + drill (zipped), pick-and-place, BOM, schematic PDF, 3D renders

Design JSON::

    {"name": "my_board", "title": "...", "parts": [{"ref": "R1", "lib_id": "Device:R", "value": "10k",
      "footprint": "Resistor_SMD:R_0603_1608Metric", "sch_xy": [50.8, 50.8], "pcb_xy": [110, 120], "pcb_rot": 0,
      "fields": {"MPN": "...", "LCSC": "C25804"}}],
     "nets": {"VIN": ["J1.1", "R1.1"]}, "unused": ["U1.7"], "power_flag_nets": ["VIN", "GND"],
     "board": {"outline_mm": [100, 100, 150, 140], "rules": {...}, "netclasses": [...], "gnd_net": "GND",
               "net_currents_a": {"*VIN_12V": 5}}}

``board.net_currents_a`` (amperes by net name or KiCad pattern) adds a net class per current, wide enough by IPC-2221 for a
10 C rise, before routing; after routing the narrowest track on each of those nets is checked (``trace_capacity``).
An explicit net class with the same pattern wins over the generated one.

Each stage stops at the first failed check and says so. A part with ``pcb_xy`` stays where the design puts it; a part
without one is placed by ``_pcbnew_helpers/place_free_footprints.py`` (by connectivity, decoupling capacitors beside
their IC's supply pin, clear of every other courtyard), optionally steered by ``board.placement_hints``
(``{"C3": ["U1"]}`` to sit near a part, or ``{"U2": [x0, y0, x1, y1]}`` for a region).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import kicad_component_board as kb
from .routing_engine import resolve_kicad_python, route_pcb

HELPER = Path(__file__).resolve().parent / "_pcbnew_helpers" / "build_component_board.py"
PLACER = Path(__file__).resolve().parent / "_pcbnew_helpers" / "place_free_footprints.py"
DEFAULT_RULES = {"clearance": 0.15, "track": 0.2, "min_track": 0.2, "via_d": 0.6, "via_drill": 0.3, "edge_clearance": 0.3}


def design_from_json(spec: dict[str, Any]) -> kb.Design:
    parts = [kb.Part(ref=p["ref"], lib_id=p["lib_id"], value=str(p.get("value", "")), footprint=p.get("footprint", ""),
                     sch_xy=tuple(p.get("sch_xy") or (0, 0)), pcb_xy=tuple(p["pcb_xy"]) if p.get("pcb_xy") else None,
                     pcb_rot=float(p.get("pcb_rot", 0)), fields=dict(p.get("fields") or {}))
             for p in spec["parts"]]
    return kb.Design(name=spec["name"], title=spec.get("title", spec["name"]), parts=parts, nets=dict(spec["nets"]),
                     unused=list(spec.get("unused") or []), power_flag_nets=list(spec.get("power_flag_nets") or []),
                     paper=spec.get("paper", "A3"), revision=spec.get("revision", "A"))


def _lib_tables(out: Path, design: kb.Design) -> None:
    syms = sorted({p.lib_id.split(":")[0] for p in design.parts} | {"power"})
    fps = sorted({p.footprint.split(":")[0] for p in design.parts if p.footprint})
    (out / "sym-lib-table").write_text("(sym_lib_table\n  (version 7)\n" + "".join(
        f'  (lib (name "{n}")(type "KiCad")(uri "{kb.symbol_dir()}/{n}.kicad_sym")(options "")(descr ""))\n' for n in syms) + ")\n")
    (out / "fp-lib-table").write_text("(fp_lib_table\n  (version 7)\n" + "".join(
        f'  (lib (name "{n}")(type "KiCad")(uri "{kb.footprint_dir()}/{n}.pretty")(options "")(descr ""))\n' for n in fps) + ")\n")


def _pcbnew(*args: str) -> str:
    python = resolve_kicad_python() or "/usr/bin/python3"
    run = subprocess.run([python, str(HELPER), *args], capture_output=True, text=True, timeout=600)
    if run.returncode != 0:
        raise RuntimeError(f"pcbnew helper failed: {run.stderr[-1500:]}")
    return run.stdout


def decoupling_report(board_path: Path, max_mm: float = 5.0) -> dict[str, Any] | None:
    """Nearest 1 uF-or-smaller capacitor to every IC supply pad (pcbnew). Over ``max_mm`` is HS's rule of thumb, not a
    datasheet figure: makers ask for the capacitor 'as close as possible' to the pin."""
    python = resolve_kicad_python() or "/usr/bin/python3"
    run = subprocess.run([python, str(HELPER.parent / "decoupling_report.py"), str(board_path), "--max-mm", str(max_mm)],
                         capture_output=True, text=True, timeout=300)
    if run.returncode != 0:
        return None
    return json.loads(run.stdout)


def clear_silk_labels(board_path: Path, refs: tuple[str, ...] = ()) -> dict[str, Any] | None:
    """Move reference labels that sit on copper, another part's outline or the board edge to a clear spot beside their part
    (pcbnew, in place); only label text moves. ``refs`` limits it to those parts."""
    python = resolve_kicad_python() or "/usr/bin/python3"
    run = subprocess.run([python, str(HELPER.parent / "clear_silk_labels.py"), str(board_path), *refs], capture_output=True, text=True, timeout=300)
    if run.returncode != 0:
        return None
    return json.loads(run.stdout)


def _place_free(board_path: Path, locked: list[str], hints: dict[str, Any] | None) -> dict[str, Any]:
    """Run the placer on the built board in place; the design's own positions are locked."""
    python = resolve_kicad_python() or "/usr/bin/python3"
    out = board_path.with_name("free_placed.kicad_pcb")
    argv = [python, str(PLACER), str(board_path), str(out), "--locked", ",".join(locked)]
    if hints:
        hints_path = board_path.with_name("placement_hints.json")
        hints_path.write_text(json.dumps(hints))
        argv += ["--hints", str(hints_path)]
    run = subprocess.run(argv, capture_output=True, text=True, timeout=900)
    if run.returncode != 0:
        raise RuntimeError(f"placer failed: {run.stderr[-1500:]}")
    report_path = Path(str(out) + ".placement.json")
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    out.replace(board_path)
    for tmp in (report_path, board_path.with_name("placement_hints.json")):
        tmp.unlink(missing_ok=True)
    return {"placed_by_hs": sorted(report.get("placed") or []), "decoupling": report.get("decoupling"), "locked": locked}


def _netname(readback: dict, plain: str) -> str:
    return next(n for n in readback["nets"] if kb._plain(n) == plain)


def schematic_stage(design: kb.Design, out: Path, symbol_uuids: dict[str, str] | None = None) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    _lib_tables(out, design)
    coverage = kb.pin_coverage(design)
    if not coverage["pass"]:
        return {"ok": False, "stage": "schematic", "coverage": coverage,
                "problems": ["pin coverage: " + json.dumps({k: coverage[k] for k in ("unknown_endpoints", "on_several_nets",
                                                                                      "pins_neither_connected_nor_declared_unused")})]}
    sch = out / f"{design.name}.kicad_sch"
    kb.write_schematic(design, sch, symbol_uuids)
    readback = kb.schematic_netlist(sch)
    parity = kb.netlist_parity(design, readback)
    erc = kb.run_erc(sch, out)
    problems = ([] if parity["pass"] else [f"KiCad read-back differs from the design: {parity}"]) + \
               [f"ERC {v['severity']}: {v['type']}: {v['description']}" for v in erc["violations"] if v["severity"] == "error"]
    return {"ok": not problems, "stage": "schematic", "schematic": str(sch), "readback": readback,
            "coverage": {"pins": coverage["pins_total"], "pass": True}, "parity": parity,
            "erc": {"errors": erc["errors"], "warnings": erc["warnings"]}, "problems": problems}


def current_netclasses(board: dict[str, Any], rules: dict[str, Any]) -> list[dict[str, Any]]:
    """The design's own net classes, plus one per stated current that no explicit class already covers."""
    from . import trace_capacity

    explicit = list(board.get("netclasses") or [])
    taken = {p for nc in explicit for p in nc.get("patterns", [])}
    generated = trace_capacity.netclasses_for_currents(board.get("net_currents_a") or {}, min_track_mm=float(rules.get("track", 0.2)),
                                                       clearance_mm=max(0.2, float(rules.get("clearance", 0.15))))
    return explicit + [nc for nc in generated if not set(nc["patterns"]) & taken]


def _trace_current(pcb: Path | str, board: dict[str, Any]) -> dict[str, Any] | None:
    if not board.get("net_currents_a"):
        return None
    from . import trace_capacity

    return trace_capacity.check_routed(Path(pcb), board["net_currents_a"])


def pcb_stage(design: kb.Design, readback: dict, out: Path, board: dict[str, Any], *, route_timeout_s: int = 600,
              route_attempts: int = 6) -> dict[str, Any]:
    rules = {**DEFAULT_RULES, **(board.get("rules") or {})}
    outline = board["outline_mm"]
    free = [p.ref for p in design.parts if p.pcb_xy is None]
    if free:  # built at the board centre first; the placer then moves each one
        centre = ((outline[0] + outline[2]) / 2, (outline[1] + outline[3]) / 2)
        design = replace(design, parts=[replace(p, pcb_xy=centre) if p.pcb_xy is None else p for p in design.parts])
    spec = kb.pcb_spec(design, readback, outline_mm=outline, rules=rules, netclasses=current_netclasses(board, rules))
    gnd = _netname(readback, board.get("gnd_net", "GND")) if board.get("gnd_net", "GND") else None
    if gnd:
        x0, y0, x1, y1 = outline
        poly = [(x0 + 0.4, y0 + 0.4), (x1 - 0.4, y0 + 0.4), (x1 - 0.4, y1 - 0.4), (x0 + 0.4, y1 - 0.4)]
        spec["stitch"] = {"net": gnd, "pitch": 4.0, "d": 0.6, "drill": 0.3, "avoid": []}
        spec["zones"] = [{"net": gnd, "layer": layer, "polygon": poly, "priority": 1, "clearance": 0.3, "solid_pads": True,
                          "name": f"GND {layer}"} for layer in ("F.Cu", "B.Cu")]
    spec_path = out / "pcb_spec.json"
    spec_path.write_text(json.dumps(spec, indent=1))
    placed = out / "placed.kicad_pcb"
    _pcbnew(str(spec_path), str(placed))
    placement = _place_free(placed, [p.ref for p in design.parts if p.ref not in free], board.get("placement_hints")) if free else None
    routed_path = out / "routed.kicad_pcb"
    pcb = out / f"{design.name}.kicad_pcb"
    attempts = []
    # FreeRouting differs between runs: on HS-BUS-A 5 of 14 attempts came back DRC-clean (2026-11-27), so keep the first
    # clean result of up to six
    for _ in range(max(1, route_attempts)):
        routed = route_pcb(placed.read_text(), timeout_s=route_timeout_s, max_passes=20,
                           project_text=placed.with_suffix(".kicad_pro").read_text())
        routed_path.write_text(routed.text)
        _pcbnew("--finish", str(spec_path), str(routed_path), str(pcb))
        labels = clear_silk_labels(pcb)
        drc = kb.run_drc(pcb, out)
        problems = [f"DRC {g}: {i['severity']}: {i['type']}: {'; '.join(w for w in i['where'] if w)}"
                    for g in ("violations", "unconnected_items", "schematic_parity") for i in drc[g]["items"] if i["severity"] == "error"]
        attempts.append(len(problems))
        if not problems:
            break
    copper = None
    if problems:
        # Every FreeRouting attempt left errors: hand the same placement to Copper (copper-kicad-mcp, MIT) when it is
        # configured. Its result is a KiCad 10 board, judged by KiCad 10's DRC; the KiCad 9 board above is kept.
        from . import copper_route
        try:
            copper = copper_route.route_with_copper(placed, out / "copper", pour_net=gnd)
        except copper_route.CopperRouteError as exc:
            copper = {"complete": False, "error": str(exc)}
    for tmp in (placed, routed_path, placed.with_suffix(".kicad_pro"), placed.with_suffix(".kicad_prl"), spec_path):
        tmp.unlink(missing_ok=True)
    if copper and copper.get("complete"):
        return {"ok": True, "stage": "pcb", "pcb": copper["routed_board"], "kicad_format": "KiCad 10", "router": copper["router"],
                "placement": placement, "route_attempts": attempts, "freerouting_board": str(pcb),
                "drc": {"errors": copper["drc_errors"], "unconnected": copper["drc_unconnected"], "warnings": copper["drc_warnings"]},
                "problems": [], "copper": {k: v for k, v in copper.items() if k not in ("rounds", "elegance")},
                "trace_current": _trace_current(copper["routed_board"], board),
                "note": (f"FreeRouting left DRC errors in all {len(attempts)} attempts; Copper routed the same placement clean. "
                         "Its board is KiCad 10: export fabrication files with a KiCad 10 kicad-cli.")}
    decoupling = decoupling_report(pcb)
    far = [r for r in (decoupling or {}).get("pads", []) if r["over_limit"]]
    trace_current = _trace_current(pcb, board)
    return {"ok": not problems, "stage": "pcb", "pcb": str(pcb), "routing": routed.stats, "placement": placement,
            "copper": copper, "decoupling": decoupling, "trace_current": trace_current, "silk_labels": labels,
            "trace_current_warnings": [f["message"] for f in (trace_current or {}).get("findings", []) if f["severity"] == "warning"],
            "decoupling_warnings": [f"{r['ic']} pad {r['pad']} ({r['net']}): nearest capacitor {r['nearest_cap']} is {r['distance_mm']} mm away"
                                    for r in far],
            "route_attempts": attempts,
            "drc": {g: {"errors": drc[g]["errors"], "warnings": drc[g]["warnings"]} for g in ("violations", "unconnected_items", "schematic_parity")},
            "drc_warnings": [f"{i['type']}: {'; '.join(w for w in i['where'] if w)}" for g in ("violations",) for i in drc[g]["items"]
                             if i["severity"] == "warning"],
            "problems": problems,
            "note": "FreeRouting varies between runs; the stage re-routes up to route_attempts times and reports each "
                    "attempt's DRC error count."}


def fab_stage(design: kb.Design, out: Path, models_dir: str | None = None) -> dict[str, Any]:
    pcb, sch = out / f"{design.name}.kicad_pcb", out / f"{design.name}.kicad_sch"
    fab = out / "fab"
    if fab.exists():
        shutil.rmtree(fab)
    gerbers = fab / "gerbers"
    gerbers.mkdir(parents=True)

    def cli(*args: str) -> None:
        run = subprocess.run([kb.kicad_cli(), *args], capture_output=True, text=True, timeout=600)
        if run.returncode != 0:
            raise RuntimeError(f"kicad-cli {' '.join(args[:3])} failed: {run.stderr[-800:]}")

    cli("pcb", "export", "gerbers", "--layers", "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
        "--subtract-soldermask", "-o", str(gerbers) + "/", str(pcb))
    cli("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "-o", str(gerbers) + "/", str(pcb))
    shutil.make_archive(str(fab / f"{design.name}_gerbers"), "zip", gerbers)
    cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--exclude-fp-th",
        "-o", str(fab / f"{design.name}_pos.csv"), str(pcb))
    cli("sch", "export", "bom", "--fields", "Reference,Value,Footprint,MPN,LCSC,${QUANTITY}",
        "--labels", "Refs,Value,Footprint,MPN,LCSC,Qty", "--group-by", "Value,Footprint,MPN,LCSC",
        "-o", str(fab / f"{design.name}_bom.csv"), str(sch))
    cli("sch", "export", "pdf", "-o", str(fab / f"{design.name}_schematic.pdf"), str(sch))
    models = models_dir or os.environ.get("KICAD9_3DMODEL_DIR")
    render = fab / f"{design.name}_iso.png"
    cli("pcb", "render", *(["-D", f"KICAD9_3DMODEL_DIR={models}"] if models else []), "--output", str(render), "--quality", "high",
        "--rotate", "'-40,0,-25'", "--perspective", "--width", "1600", "--height", "1000", str(pcb))
    zip_path = fab / f"{design.name}_gerbers.zip"
    return {"ok": True, "stage": "fab", "files": sorted(str(p.relative_to(out)) for p in fab.rglob("*") if p.is_file()),
            "gerbers_zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(), "render": str(render), "problems": []}


def run(spec: dict[str, Any], out: Path, *, stages: tuple[str, ...] = ("schematic", "pcb", "fab")) -> dict[str, Any]:
    design = design_from_json(spec)
    result: dict[str, Any] = {"design": design.name, "stages": {}}
    sch = schematic_stage(design, out)
    readback = sch.pop("readback", None)
    result["stages"]["schematic"] = sch
    if not sch["ok"] or "pcb" not in stages:
        return {**result, "ok": sch["ok"], "problems": sch["problems"]}
    pcb = pcb_stage(design, readback, out, spec["board"])
    result["stages"]["pcb"] = pcb
    if not pcb["ok"] or "fab" not in stages:
        return {**result, "ok": pcb["ok"], "problems": pcb["problems"]}
    fab = fab_stage(design, out)
    result["stages"]["fab"] = fab
    return {**result, "ok": True, "problems": []}
