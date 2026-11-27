"""Build HS-BUS-A from design.py: schematic, ERC, read-back parity, placed and routed PCB, DRC with schematic parity,
fabrication outputs and the board's own electrical checks.

    PYTHONPATH=src .venv/bin/python projects/hs-bus-a/build_board.py [--out DIR] [--stage place]

Needs kicad-cli and a pcbnew-capable python (KiCad 9), Java and a FreeRouting jar (HARDWARE_SPLICER_FREEROUTING_JAR).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))

from design import DESIGN  # noqa: E402
import checks  # noqa: E402
from hardware_splicer import kicad_component_board as kb  # noqa: E402
from hardware_splicer.routing_engine import resolve_kicad_python, route_pcb  # noqa: E402
from hardware_splicer import jlcparts_lookup  # noqa: E402

MODELS = Path(os.environ.get("HARDWARE_SPLICER_TMP_ROOT") or HERE.parents[1] / ".cache" / "hardware-splicer") / "kicad-3dmodels-9.0.2"
HELPER = HERE.parents[1] / "src" / "hardware_splicer" / "_pcbnew_helpers" / "build_component_board.py"
OUTLINE = (100.0, 100.0, 170.0, 156.0)
RULES = {"clearance": 0.15, "track": 0.2, "min_track": 0.2, "via_d": 0.6, "via_drill": 0.3, "edge_clearance": 0.3}
# 12 V copper widths. VIN carries the whole supply (5 A from the BOM's 12 V 5 A adapter); each port is fused at 2.5 A.
VIN_TRACK_MM = 2.5
PORT_TRACK_MM = 1.2
NETCLASSES = [{"name": "VIN", "track": VIN_TRACK_MM, "clearance": 0.3, "via_d": 1.0, "via_drill": 0.5, "patterns": ["*VIN_12V"]},
              {"name": "PORT", "track": PORT_TRACK_MM, "clearance": 0.3, "via_d": 1.0, "via_drill": 0.5, "patterns": ["*DXL_VDD*"]}]
ROUTE_TIMEOUT_S = 600


def verification(result: dict) -> dict:
    drc = result["drc"]
    return {
        "schema_version": "hardware_splicer.hs_bus_a.verification.v1",
        "design": {"name": DESIGN.name, "title": DESIGN.title, "revision": DESIGN.revision, "parts": len(DESIGN.parts),
                   "nets": len(DESIGN.nets)},
        "schematic": {"pins_checked": result["schematic"]["coverage"]["pins_total"],
                      "every_pin_connected_or_declared_unused": result["schematic"]["coverage"]["pass"],
                      "kicad_readback_matches_design": result["schematic"]["parity"]["pass"],
                      "nets_compared": result["schematic"]["parity"]["nets_compared"],
                      "erc_errors": result["schematic"]["erc"]["errors"],
                      "erc_warnings": result["schematic"]["erc"]["warnings"],
                      "erc_warning_types": sorted({v["type"] for v in result["schematic"]["erc"]["violations"]})},
        "routing": result["routing"],
        "silk_labels_moved": (result.get("silk_labels") or {}).get("moved", {}),
        "drc": {group: {"errors": drc[group]["errors"], "warnings": drc[group]["warnings"],
                        "items": [f"{i['severity']}: {i['type']}: {'; '.join(w for w in i['where'] if w)}" for i in drc[group]["items"]]}
                for group in ("violations", "unconnected_items", "schematic_parity")},
        "kicad_version": drc.get("kicad_version"),
        "board": result["board"],
        "electrical": result["electrical"],
        "bom_pricing": result["bom_pricing"],
        "fab": result["fab"],
        "not_checked": [
            "Signal integrity and USB 2.0 full-speed impedance (12 Mb/s over short tracks; no controlled impedance asked for)",
            "Thermal behaviour of the fuses and pour under load (only the IPC-2221 track rise is computed)",
            "Firmware or host software; the board appears as an FTDI serial port and works with the DYNAMIXEL SDK by assumption",
            "Nothing has been fabricated or powered",
        ],
    }


def _lib_tables(out: Path) -> None:
    syms = sorted({p.lib_id.split(":")[0] for p in DESIGN.parts} | {"power"})
    fps = sorted({p.footprint.split(":")[0] for p in DESIGN.parts if p.footprint})
    (out / "sym-lib-table").write_text("(sym_lib_table\n  (version 7)\n" + "".join(
        f'  (lib (name "{n}")(type "KiCad")(uri "{kb.symbol_dir()}/{n}.kicad_sym")(options "")(descr ""))\n' for n in syms) + ")\n")
    (out / "fp-lib-table").write_text("(fp_lib_table\n  (version 7)\n" + "".join(
        f'  (lib (name "{n}")(type "KiCad")(uri "{kb.footprint_dir()}/{n}.pretty")(options "")(descr ""))\n' for n in fps) + ")\n")


def _pcbnew(*args: str) -> None:
    python = resolve_kicad_python() or "/usr/bin/python3"
    run = subprocess.run([python, str(HELPER), *args], capture_output=True, text=True, timeout=300)
    if run.returncode != 0:
        raise SystemExit(f"pcbnew helper failed: {run.stderr[-2000:]}")


def schematic(out: Path, symbol_uuids: dict[str, str] | None = None) -> dict:
    sch = out / f"{DESIGN.name}.kicad_sch"
    coverage = kb.pin_coverage(DESIGN)
    kb.write_schematic(DESIGN, sch, symbol_uuids)
    readback = kb.schematic_netlist(sch)
    parity = kb.netlist_parity(DESIGN, readback)
    erc = kb.run_erc(sch, out)
    return {"sch": sch, "readback": readback, "coverage": coverage, "parity": parity, "erc": erc}


def spec_for(readback: dict) -> dict:
    """Every net is routed by FreeRouting in one pass; the 12 V nets get wide-track net classes so the router sizes them.
    Ground pours and stitching vias go on afterwards. (Keep-out areas and pre-placed locked power tracks left FreeRouting
    unable to finish; with neither it completes the board.)"""
    spec = kb.pcb_spec(DESIGN, readback, outline_mm=OUTLINE, rules=RULES, netclasses=NETCLASSES)
    x0, y0, x1, y1 = OUTLINE
    board = [(x0 + 0.4, y0 + 0.4), (x1 - 0.4, y0 + 0.4), (x1 - 0.4, y1 - 0.4), (x0 + 0.4, y1 - 0.4)]
    gnd = _netname(readback, "GND")
    spec["stitch"] = {"net": gnd, "pitch": 4.0, "d": 0.6, "drill": 0.3, "avoid": []}
    spec["zones"] = [{"net": gnd, "layer": layer, "polygon": board, "priority": 1, "clearance": 0.3, "solid_pads": True,
                      "name": f"GND {layer}"} for layer in ("F.Cu", "B.Cu")]
    return spec


def _netname(readback: dict, plain: str) -> str:
    return next(n for n in readback["nets"] if kb._plain(n) == plain)


def pcb(out: Path, readback: dict, stage: str) -> dict:
    spec_path = out / "pcb_spec_full.json"
    spec_path.write_text(json.dumps(spec_for(readback), indent=1))
    placed = out / "placed.kicad_pcb"
    _pcbnew(str(spec_path), str(placed))
    if stage == "place":
        return {"placed": placed}
    routed = route_pcb(placed.read_text(), timeout_s=ROUTE_TIMEOUT_S, max_passes=20,
                       project_text=placed.with_suffix(".kicad_pro").read_text())
    routed_path = out / "routed.kicad_pcb"
    routed_path.write_text(routed.text)
    board = out / f"{DESIGN.name}.kicad_pcb"
    _pcbnew("--finish", str(spec_path), str(routed_path), str(board))
    for tmp in (placed, routed_path):
        tmp.unlink()
    return {"board": board, "routing": {"engine": routed.engine, **routed.stats}}


def _cli(*args: str) -> None:
    run = subprocess.run([kb.kicad_cli(), *args], capture_output=True, text=True, timeout=600,
                         env={**os.environ, "KICAD9_3DMODEL_DIR": os.environ.get("KICAD9_3DMODEL_DIR", str(MODELS))})
    if run.returncode != 0:
        raise SystemExit(f"kicad-cli {' '.join(args[:3])} failed: {run.stderr[-1500:]}")


# Labels KiCad's DRC found on copper or on another part's outline after the 2026-11-27 decoupling moves; only their text moves.
SILK_LABELS = ("C4", "U3")


def clear_silk_labels(board: Path) -> dict:
    from hardware_splicer.component_board_pipeline import clear_silk_labels as move_labels

    result = move_labels(board, SILK_LABELS)
    if result is None:
        raise SystemExit("clear_silk_labels failed: is KiCad's pcbnew module installed?")
    return result


def fab(out: Path, board: Path, sch: Path, renders: Path) -> dict:
    """Gerbers and drill files (zipped for a board house), pick-and-place, BOM, schematic PDF and board pictures."""
    fab_dir = out.parent / "fab"
    # Only what this step writes is replaced: the quote (quote_*.json) and the JLCPCB order files (jlc/) are kept.
    gerbers = fab_dir / "gerbers"
    if gerbers.exists():
        shutil.rmtree(gerbers)
    for generated in fab_dir.glob(f"{DESIGN.name}_*"):
        generated.unlink()
    gerbers.mkdir(parents=True)
    layers = "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
    _cli("pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask", "-o", str(gerbers) + "/", str(board))
    _cli("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2",
         "-o", str(gerbers) + "/", str(board))
    shutil.make_archive(str(fab_dir / f"{DESIGN.name}_gerbers"), "zip", gerbers)
    _cli("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--exclude-fp-th",
         "-o", str(fab_dir / f"{DESIGN.name}_pos.csv"), str(board))
    _cli("sch", "export", "bom", "--fields", "Reference,Value,Footprint,MPN,${QUANTITY}", "--labels", "Refs,Value,Footprint,MPN,Qty",
         "--group-by", "Value,Footprint,MPN", "-o", str(fab_dir / f"{DESIGN.name}_bom.csv"), str(sch))
    _cli("sch", "export", "pdf", "-o", str(fab_dir / f"{DESIGN.name}_schematic.pdf"), str(sch))
    renders.mkdir(exist_ok=True)
    models = ["-D", f"KICAD9_3DMODEL_DIR={os.environ.get('KICAD9_3DMODEL_DIR', str(MODELS))}"]  # kicad-cli takes it as a project variable
    _cli("pcb", "render", *models, "--output", str(renders / "HS_BUS_A_TOP.png"), "--side", "top", "--quality", "high", "--width", "1600",
         "--height", "1200", "--zoom", "1.1", str(board))
    _cli("pcb", "render", *models, "--output", str(renders / "HS_BUS_A_ISO.png"), "--quality", "high", "--rotate", "'-40,0,-25'",
         "--perspective", "--width", "1600", "--height", "1000", str(board))
    files = sorted(p for p in fab_dir.rglob("*") if p.is_file())
    return {"files": [str(p.relative_to(out.parent)) for p in files],
            "zip_sha256": hashlib.sha256((fab_dir / f"{DESIGN.name}_gerbers.zip").read_bytes()).hexdigest()}


def bom_pricing(boards: tuple[int, ...] = (1, 10)) -> dict:
    """JLCPCB/LCSC unit prices for the parts list: the part's LCSC code when the design names one, else a search on its
    manufacturer number or description (best-stocked match)."""
    groups: dict[tuple, list[str]] = {}
    for p in DESIGN.parts:
        if p.lib_id.startswith("Mechanical:"):
            continue
        key = (p.fields.get("LCSC", ""), p.fields.get("MPN", p.value))
        groups.setdefault(key, []).append(p.ref)
    lines = [{"refs": refs, "qty_per_board": len(refs), **({"lcsc": code} if code else {"query": mpn}), "mpn_wanted": mpn}
             for (code, mpn), refs in groups.items()]
    return {f"{n}_boards": jlcparts_lookup.price_bom(lines, boards=n) for n in boards}


def board_stats(board: Path) -> dict:
    text = board.read_text()
    tree = kb.parse_sexpr(text)
    segs = [n for n in tree if isinstance(n, list) and n and n[0] == "segment"]
    widths = sorted({float(kb._child(s, "width")[1]) for s in segs})
    vias = [n for n in tree if isinstance(n, list) and n and n[0] == "via"]
    fps = [n for n in tree if isinstance(n, list) and n and n[0] == "footprint"]
    x0, y0, x1, y1 = OUTLINE
    return {"size_mm": [x1 - x0, y1 - y0], "copper_layers": 2, "footprints": len(fps), "track_segments": len(segs),
            "track_widths_mm": widths, "vias": len(vias), "rules": RULES,
            "port_track_mm": PORT_TRACK_MM, "vin_track_mm": VIN_TRACK_MM, "copper_weight": "1 oz assumed (board-house default)"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "kicad"))
    ap.add_argument("--stage", choices=["place", "all"], default="all")
    ap.add_argument("--reuse-pcb", help="a finished, routed hs_bus_a.kicad_pcb (with its .kicad_sch beside it) to keep: "
                                        "the schematic is rewritten with the same symbol IDs and every check re-runs, so a "
                                        "field-only edit does not need another FreeRouting run; DRC parity catches anything more")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _lib_tables(out)
    reuse = Path(args.reuse_pcb).resolve() if args.reuse_pcb else None
    uuids = None
    if reuse:
        old = kb.schematic_netlist(reuse.with_suffix(".kicad_sch"))
        uuids = {ref: c["uuid"].strip("/").split("/")[-1] for ref, c in old["components"].items()}
        for suffix in (".kicad_pcb", ".kicad_pro"):
            if reuse.with_suffix(suffix) != (out / f"{DESIGN.name}{suffix}").resolve():
                shutil.copy(reuse.with_suffix(suffix), out / f"{DESIGN.name}{suffix}")
    sch = schematic(out, uuids)
    result = {"schematic": {k: sch[k] for k in ("coverage", "parity", "erc")}}
    if not (sch["coverage"]["pass"] and sch["parity"]["pass"] and sch["erc"]["errors"] == 0):
        print(json.dumps(result, indent=1, default=str))
        return 1
    if reuse:
        board = {"board": out / f"{DESIGN.name}.kicad_pcb",
                 "routing": {"engine": "freerouting (earlier run of this build)", "reused_board": True}}
    else:
        board = pcb(out, sch["readback"], args.stage)
    if args.stage == "place":
        print(board)
        return 0
    result["routing"] = board["routing"]
    result["silk_labels"] = clear_silk_labels(board["board"])
    result["drc"] = kb.run_drc(board["board"], out)
    result["board"] = board_stats(board["board"])
    result["electrical"] = checks.run(PORT_TRACK_MM, VIN_TRACK_MM)
    result["bom_pricing"] = bom_pricing()
    result["fab"] = fab(out, board["board"], sch["sch"], HERE / "renders")
    (out / "build_result.json").write_text(json.dumps(result, indent=1, default=str))
    (HERE / "verification.json").write_text(json.dumps(verification(result), indent=1, default=str) + "\n")
    for scratch in ("pcb_spec_full.json", "build_result.json", "erc.json", "drc.json", f"{DESIGN.name}.kicad_prl", "placed.kicad_pro",
                    "placed.kicad_prl"):
        (out / scratch).unlink(missing_ok=True)
    print(json.dumps({k: (v if k != "drc" else {g: {"errors": v[g]["errors"], "warnings": v[g]["warnings"]} for g in ("violations", "unconnected_items", "schematic_parity")})
                      for k, v in result.items() if k != "schematic"}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
