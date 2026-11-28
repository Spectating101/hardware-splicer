"""Read-only data for the workbench screen: HS's board pipeline (the spine), one recorded run through it, and the
measured comparisons against outside tools.

Everything here is read from tracked records; nothing is computed or upgraded. A step the record does not cover says
so ("not recorded"), and the run's own ``not_checked`` list travels with it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
RENDER_FILES = {"top": "HS_BUS_A_TOP.png", "iso": "HS_BUS_A_ISO.png"}


def repo_root() -> Path:
    """The checkout whose records are read: HARDWARE_SPLICER_REPO_ROOT (hs-serve --repo-root) or this source tree."""
    explicit = os.environ.get("HARDWARE_SPLICER_REPO_ROOT", "").strip()
    return Path(explicit).expanduser().resolve() if explicit else PACKAGE_ROOT


def _paths() -> dict[str, Path]:
    root = repo_root()
    run = root / "projects" / "hs-bus-a"
    return {
        "root": root, "run": run,
        "held_out": root / "examples" / "schematic_bug_benchmark" / "heldout_benchmark_20261127.json",
        "krt_vs_copper": root / "examples" / "routing_trial" / "krt_vs_copper_20261128.json",
        "copper_vs_designer": root / "examples" / "routing_trial" / "copper_vs_designer_reference_boards_20261127.json",
        "predictions": root / "examples" / "backtests" / "PREDICTIONS.json",
    }


def _render(name: str) -> Path | None:
    file = RENDER_FILES.get(name)
    return _paths()["run"] / "renders" / file if file else None


# The steps of component_board_pipeline.run, in order. `runs` names entries of the outside-tool registry
# (data/external_tools.json) or HS's own module; `gate` steps stop the pipeline on an error.
SPINE: tuple[dict[str, Any], ...] = (
    {"n": 1, "key": "design", "title": "Design", "runs": ["HS component design (JSON)"], "gate": False,
     "stops_on": None, "tool": "hs_component_board"},
    {"n": 2, "key": "pin_coverage", "title": "Pin coverage", "runs": ["HS"], "gate": True,
     "stops_on": "a pin neither connected nor declared unused", "tool": "hs_component_board"},
    {"n": 3, "key": "schematic", "title": "Schematic", "runs": ["KiCad symbol libraries"], "gate": False,
     "stops_on": None, "tool": "hs_component_board"},
    {"n": 4, "key": "readback", "title": "Read-back parity", "runs": ["KiCad ERC and DRC (kicad-cli)"], "gate": True,
     "stops_on": "KiCad's netlist differs from the design", "tool": "hs_component_board"},
    {"n": 5, "key": "erc", "title": "ERC", "runs": ["KiCad ERC and DRC (kicad-cli)"], "gate": True,
     "stops_on": "any ERC error", "tool": "hs_review_kicad_schematic"},
    {"n": 6, "key": "placement", "title": "Placement + pours", "runs": ["HS placer", "pcbnew"], "gate": False,
     "stops_on": None, "tool": "hs_component_board"},
    {"n": 7, "key": "freerouting", "title": "Route · FreeRouting", "runs": ["FreeRouting"], "gate": False,
     "stops_on": "DRC errors after every attempt: hand on to the next router", "tool": "hs_component_board"},
    {"n": 8, "key": "krt", "title": "Route · KRT fallback", "runs": ["KiCadRoutingTools"], "gate": False,
     "stops_on": "DRC errors: hand on to Copper", "tool": "hs_component_board"},
    {"n": 9, "key": "copper", "title": "Route · Copper fallback", "runs": ["Copper (copper-kicad-mcp)"], "gate": False,
     "stops_on": None, "tool": "hs_route_copper"},
    {"n": 10, "key": "finish", "title": "Finish + labels", "runs": ["HS", "pcbnew"], "gate": False,
     "stops_on": None, "tool": "hs_component_board"},
    {"n": 11, "key": "drc", "title": "DRC + parity", "runs": ["KiCad ERC and DRC (kicad-cli)"], "gate": True,
     "stops_on": "any DRC error, unconnected item or schematic mismatch", "tool": "hs_component_board"},
    {"n": 12, "key": "track_current", "title": "Track current", "runs": ["HS (IPC-2221 chart fit)"], "gate": False,
     "stops_on": None, "tool": "hs_trace_current"},
    {"n": 13, "key": "decoupling", "title": "Decoupling", "runs": ["HS"], "gate": False,
     "stops_on": None, "tool": "hs_component_board"},
    {"n": 14, "key": "fab", "title": "Fab files", "runs": ["KiCad ERC and DRC (kicad-cli)", "jlcparts"], "gate": False,
     "stops_on": None, "tool": "hs_component_board"},
)


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _rel(path: Path) -> str:
    return str(path.relative_to(repo_root()))


def _run_values(v: dict[str, Any], quote: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """What the recorded run says at each step: a short line, its outcome as the record states it, and detail."""
    design, sch, drc, board = v.get("design", {}), v.get("schematic", {}), v.get("drc", {}), v.get("board", {})
    routing = v.get("routing", {})
    labels = v.get("silk_labels_moved") or {}
    err = sum(drc.get(g, {}).get("errors", 0) for g in ("violations", "unconnected_items", "schematic_parity"))
    warn = sum(drc.get(g, {}).get("warnings", 0) for g in ("violations", "unconnected_items", "schematic_parity"))
    widths = sorted(board.get("track_widths_mm") or [], reverse=True)
    pricing = (v.get("bom_pricing") or {}).get("1_boards") or {}
    out: dict[str, dict[str, Any]] = {
        "design": {"line": f"{design.get('parts')} parts · {design.get('nets')} nets · rev {design.get('revision')}",
                   "outcome": "recorded"},
        "pin_coverage": {"line": f"{sch.get('pins_checked')} pins checked",
                         "outcome": "clean" if sch.get("every_pin_connected_or_declared_unused") else "failed"},
        "schematic": {"line": f"{design.get('name')}.kicad_sch", "outcome": "recorded"},
        "readback": {"line": f"{sch.get('nets_compared')} nets compared",
                     "outcome": "clean" if sch.get("kicad_readback_matches_design") else "failed"},
        "erc": {"line": f"{sch.get('erc_errors')} errors · {sch.get('erc_warnings')} warnings",
                "outcome": "clean" if sch.get("erc_errors") == 0 else "failed"},
        "placement": {"line": f"{board.get('footprints')} footprints · {board.get('copper_layers')} layers · "
                              f"{'×'.join(str(round(s)) for s in board.get('size_mm') or [])} mm", "outcome": "recorded"},
        "freerouting": {"line": str(routing.get("engine")), "outcome": "recorded"},
        "krt": {"line": "not run on this build", "outcome": "not_run"},
        "copper": {"line": "not run on this build", "outcome": "not_run"},
        "finish": {"line": ("labels moved: " + ", ".join(labels)) if labels else "no labels moved", "outcome": "recorded"},
        "drc": {"line": f"{err} errors · {warn} warnings", "outcome": "clean" if err == 0 else "failed"},
        "track_current": {"line": " / ".join(f"{w} mm" for w in widths) + f" · {board.get('vias')} vias",
                          "outcome": "recorded"},
        "decoupling": {"line": "not recorded for this build", "outcome": "unknown"},
        "fab": {"line": f"parts US${pricing.get('per_board_usd')} a board"
                        + (f" · quote US${quote.get('total_usd')} for {quote.get('order', {}).get('boards')}" if quote else ""),
                "outcome": "recorded"},
    }
    return out


def spine() -> dict[str, Any]:
    run_dir = _paths()["run"]
    v = _load(run_dir / "verification.json")
    quote = _load(run_dir / "fab" / "quote_2026-11-26.json")
    values = _run_values(v, quote) if v else {}
    steps = [{**s, "run": values.get(s["key"], {"line": "not recorded", "outcome": "unknown"})} for s in SPINE]
    run = None
    if v:
        d = v.get("design", {})
        run = {"name": d.get("title"), "revision": d.get("revision"), "kicad": v.get("kicad_version"),
               "record": _rel(run_dir / "verification.json"), "not_checked": v.get("not_checked") or [],
               "renders": [k for k in RENDER_FILES if (_render(k) or Path()).is_file()],
               "claim_boundary": "Software checks on a design that has not been fabricated, assembled or powered."}
    return {"steps": steps, "gates": [s["n"] for s in SPINE if s["gate"]], "run": run}


def measures() -> dict[str, Any]:
    p = _paths()
    held = _load(p["held_out"])
    krt = _load(p["krt_vs_copper"])
    designer = _load(p["copper_vs_designer"])
    preds = _load(p["predictions"])
    out: dict[str, Any] = {}
    if held:
        t = held.get("tally", {})
        out["checkers"] = {
            "question": "Real schematic bugs caught, on projects HS's rules were not written from",
            "cases": held.get("cases_judged"),
            "rows": [
                {"name": "KiCad ERC", "caught": t.get("kicad_erc", {}).get("caught")},
                {"name": "kicad-happy", "caught": t.get("kicad_happy", {}).get("caught")},
                {"name": "HS review (rules fixed before this set)", "caught": t.get("hs_review_dev_rules", {}).get("caught")},
                {"name": "HS review (one rule added after)", "caught": t.get("hs_review_current", {}).get("caught")},
                {"name": "All three together", "caught": held.get("caught_by_any")},
            ],
            "says": held.get("what_this_says"), "record": _rel(p["held_out"]), "captured": held.get("captured"),
        }
    if krt:
        rows = []
        for b in krt.get("boards", []):
            rows.append({"board": b.get("board"), "krt": b.get("krt"), "copper": b.get("copper"), "designer": b.get("designer")})
        out["routers"] = {"question": krt.get("question"), "rows": rows, "says": krt.get("result"),
                          "limits": krt.get("limits"), "record": _rel(p["krt_vs_copper"]), "captured": krt.get("captured")}
    if designer:
        out["routers_vs_designer"] = {"question": designer.get("question"), "says": designer.get("result"),
                                      "record": _rel(p["copper_vs_designer"])}
    if preds:
        out["predictions"] = {"rule": preds.get("rule"), "record": _rel(p["predictions"]),
                              "rows": [{"id": x.get("id"), "design": x.get("design"), "quantity": x.get("quantity"),
                                        "status": x.get("status")} for x in preds.get("predictions", [])]}
    return out


def create_bench_router() -> APIRouter:
    router = APIRouter(prefix="/v1/bench", tags=["bench"])

    @router.get("/spine")
    def get_spine() -> dict[str, Any]:
        return spine()

    @router.get("/measures")
    def get_measures() -> dict[str, Any]:
        return measures()

    @router.get("/renders/{name}")
    def get_render(name: str) -> FileResponse:
        path = _render(name)
        if path is None or not path.is_file():
            raise HTTPException(status_code=404, detail=f"no render {name}")
        return FileResponse(path, media_type="image/png")

    return router
