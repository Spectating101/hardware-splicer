"""What HS can already do, read from its own code: every module, what it says it does, its tests, and how it is reached.

    python -m hardware_splicer.capability_map            # writes docs/CAPABILITY_MAP.md and docs/capability_map.json

Generated, never hand-kept, so it cannot go stale the way an agent's memory does. Read it before designing any new
tool: on 2026-11-26 FEM screening, thermal/RF device review and arm kinematics were called "missing" while they sat in
modules nobody had opened. A module's own description is its author's claim; its tests and reachability are measured.

Reach is static and transitive: a module counts as reachable from the toolbelt (the engine flow agents use), the MCP
server or the REST product API when that entry point imports it, directly or through other HS modules. "Plumbing" marks API wrappers, compatibility shims and similar
support code, by name, so the engineering capabilities stand out.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parent
ROOT = PKG.parents[1]

AREAS = [  # first match wins; matched against the module path and the first 400 characters of its description
    ("salvage, donors, repair", r"salvag|donor|repair|teardown|junk|keyboard_splice|spi_"),
    ("circuit boards and electronics", r"pcb|kicad|routing|schematic|netlist|gerber|footprint|circuit|electrical|erc\b|drc\b|wirestudio|board"),
    ("mechanical, CAD and FEM", r"mechanic|fem\b|_fem|cad|step_|mesh|stress|fastener|bracket|chassis|enclos|construction|print"),
    ("robots, arms and motion", r"robot|arm_|urdf|motion|kinemat|actuat|servo|gait|drive_sizing|rover"),
    ("drones, propulsion and power", r"drone|propuls|energy|battery|power|thermal"),
    ("firmware and devices", r"firmware|platformio|device_|bringup|esp32|pico|flash"),
    ("simulation", r"simulat|digital_|twin|physics"),
    ("parts, BOM and sourcing", r"bom|part|price|jlc|sourc|catalog|supplier|lcsc"),
    ("AI, agents and models", r"ai_|llm|agent|model_|orchestrat|vision|copilot|agy|text_client|jarvis|compose"),
    ("research and landscape", r"prior_art|landscape|github|research|benchmark|market|commerce"),
    ("projects, reviews and evidence", r"project|review|revision|evidence|mission|authority|ledger|release|package|session|history"),
]
PLUMBING = re.compile(r"(_api|_compat|_errors|_publication|_schema|_store|_router|_cli|_audit|_fixtures?)$|^cli|^__")


def _doc(path: Path) -> str:
    try:
        return " ".join((ast.get_docstring(ast.parse(path.read_text(encoding="utf-8", errors="replace"))) or "").split())
    except SyntaxError:
        return ""


def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            if n.level and not n.module:                      # from . import x, y
                out.update(a.name for a in n.names)
            elif n.level:                                     # from .x import y / from .x.y import z
                out.add(n.module.split(".")[0]); out.update(a.name for a in n.names)
            elif n.module and n.module.startswith("hardware_splicer"):
                rest = n.module.split("hardware_splicer", 1)[1].lstrip(".")
                out.add(rest.split(".")[0] if rest else ""); out.update(a.name for a in n.names)
        elif isinstance(n, ast.Import):
            out.update(a.name.split("hardware_splicer.", 1)[-1].split(".")[0] for a in n.names if a.name.startswith("hardware_splicer."))
    return {o for o in out if o}


def build() -> dict[str, Any]:
    modules = sorted(p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts and p.name != "__init__.py")
    graph = {p.stem: _imports(p) for p in modules}
    graph.update({p.stem: _imports(p) for p in PKG.rglob("__init__.py") if "__pycache__" not in p.parts and p.parent != PKG})

    def reach(start: str) -> set[str]:
        """Everything an entry point imports, directly or through other HS modules."""
        seen, todo = set(), list(graph.get(start, set()))
        while todo:
            m = todo.pop()
            if m in seen:
                continue
            seen.add(m)
            todo.extend(graph.get(m, set()))
        return seen

    entry = {name: reach(name) for name in ("engineering_toolbelt", "mcp_server", "product_api")}
    test_text = {}
    for t in sorted((ROOT / "tests").glob("test_*.py")):
        test_text[t.name] = t.read_text(encoding="utf-8", errors="replace")
    rows = []
    for p in modules:
        rel = p.relative_to(PKG)
        stem = p.stem
        dotted = ".".join(rel.with_suffix("").parts)
        doc = _doc(p)
        text = f"{dotted} {doc[:400]}".lower()
        area = next((a for a, rx in AREAS if re.search(rx, text)), "other")
        pat = re.compile(rf"\b{re.escape(stem)}\b")
        tests = [n for n, t in test_text.items() if pat.search(t)]
        lines = p.read_text(encoding="utf-8", errors="replace").count("\n")
        rows.append({"module": dotted, "area": area, "lines": lines, "plumbing": bool(PLUMBING.search(stem)),
                     "tests": len(tests), "toolbelt": stem in entry["engineering_toolbelt"], "mcp": stem in entry["mcp_server"],
                     "rest": stem in entry["product_api"], "about": doc[:300]})
    areas = defaultdict(lambda: {"modules": 0, "capability_modules": 0, "lines": 0, "tested": 0, "in_toolbelt": 0})
    for r in rows:
        a = areas[r["area"]]
        a["modules"] += 1; a["lines"] += r["lines"]; a["tested"] += r["tests"] > 0
        a["capability_modules"] += not r["plumbing"]; a["in_toolbelt"] += r["toolbelt"]
    return {"schema": "hardware_splicer.capability_map.v1", "modules": len(rows), "lines": sum(r["lines"] for r in rows),
            "tested": sum(r["tests"] > 0 for r in rows), "in_toolbelt": sum(r["toolbelt"] for r in rows),
            "areas": dict(sorted(areas.items(), key=lambda kv: -kv[1]["lines"])), "rows": rows}


def markdown(m: dict[str, Any]) -> str:
    out = ["# HS capability map (generated)", "",
           "Generated by `python -m hardware_splicer.capability_map` from the code itself. Do not edit by hand: regenerate.",
           "Read this before designing any new tool, and search it (or `hs_prior_art_search` with source `hs_own`) for the",
           "capability first. Descriptions are each module's own claim; tests and reach are measured statically.", "",
           f"**{m['modules']} modules, {m['lines']:,} lines; {m['tested']} referenced by at least one test; "
           f"{m['in_toolbelt']} imported by the engine toolbelt.**", "",
           "| Area | Modules | Engineering (not plumbing) | Lines | Tested | In toolbelt |", "|---|---|---|---|---|---|"]
    for a, s in m["areas"].items():
        out.append(f"| {a} | {s['modules']} | {s['capability_modules']} | {s['lines']:,} | {s['tested']} | {s['in_toolbelt']} |")
    out += ["", "Reach: **T** engine toolbelt (MCP and REST `/v1/toolbelt`), **M** MCP server, **R** REST product API.", ""]
    by_area = defaultdict(list)
    for r in m["rows"]:
        by_area[r["area"]].append(r)
    for a in m["areas"]:
        out += [f"## {a}", "", "| Module | Lines | Tests | Reach | What it says it does |", "|---|---|---|---|---|"]
        for r in sorted(by_area[a], key=lambda r: (r["plumbing"], -r["lines"])):
            reach = "".join(k for k, f in (("T", r["toolbelt"]), ("M", r["mcp"]), ("R", r["rest"])) if f) or "-"
            name = f"`{r['module']}`" + (" (plumbing)" if r["plumbing"] else "")
            about = (r["about"][:160] + ("..." if len(r["about"]) > 160 else "")).replace("|", "/") or "(no description)"
            out.append(f"| {name} | {r['lines']} | {r['tests']} | {reach} | {about} |")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    m = build()
    (ROOT / "docs" / "capability_map.json").write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "docs" / "CAPABILITY_MAP.md").write_text(markdown(m) + "\n", encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("modules", "lines", "tested", "in_toolbelt")}))
    for a, s in m["areas"].items():
        print(f"  {a}: {s['modules']} modules ({s['capability_modules']} engineering), {s['lines']:,} lines, {s['tested']} tested, {s['in_toolbelt']} in toolbelt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
