"""What HS can already do, read from its own code: every module, what it says it does, its tests, and how it is reached.

    python -m hardware_splicer.capability_map                 # regenerate docs/CAPABILITY_MAP.md, docs/capability_map/*.md
                                                              # and docs/capability_map.json
    python -m hardware_splicer.capability_map find fem stress # search modules by name and description (cheap for agents)
    python -m hardware_splicer.capability_map show part_lookup  # one module: reach, importers, imports, tests
    python -m hardware_splicer.capability_map --check         # exit 1 when a module was added or removed since generation

Generated, never hand-kept, so it cannot go stale the way an agent's memory does. Read it before designing any new
tool: on 2026-11-26 FEM screening, thermal/RF device review and arm kinematics were called "missing" while they sat in
modules nobody had opened. A module's own description is its author's claim; its tests and reachability are measured.

Reach is static and transitive over the full dotted import graph (relative imports, ``from pkg import name`` of a
submodule, the package's lazy ``_MODULES`` re-exports and exact module-name strings). A module is reached by an entry
point when that entry point imports it, directly or through other HS modules; importing a module is not the same as
offering each of its functions as a tool, so ``direct`` also records whether an entry layer (a tool, a REST router,
an MCP server, a console command) imports it itself. "Plumbing" marks API wrappers, compatibility shims and similar
support code, by name, so the engineering capabilities stand out.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PKG = Path(__file__).resolve().parent
ROOT = PKG.parents[1]
PREFIX = "hardware_splicer."
DOCS = ROOT / "docs"

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

# Entry points that serve agents or users. Console scripts are read from pyproject.toml and added to these.
SURFACES = {
    "toolbelt": ("engineering_toolbelt",),                       # the engine tools agents call (MCP and REST /v1/toolbelt)
    "mcp": ("mcp_server", "backend_mcp_server"),                 # hs-mcp, hs-backend-mcp
    "rest": ("product_api",),                                    # hs-serve
}
# Lines of work deliberately kept off the shipped surfaces (decided 2026-11-27). A module that no shipped entry point
# reaches and that matches none of these is listed as undecided: wire it, declare it here, or delete it.
RESEARCH_LINES = [
    ("keyboard splice board surgery", r"^(_pcbnew_helpers\.)?keyboard_splice"),
    ("SPI-flash virtual lab and vendor models",
     r"^(spi_|cleanroom_|vendor_model_|captured_model_materialization$|provider_review$|workshop_operator$)"),
    ("legacy salvage-package CLI (scripts/hardware_splicer.py)", r"^salvage_revision$"),
    ("donor intake from retained visual inspections (needs the inspection artifact store in a flow)", r"^visual_donor_intake$"),
    ("Codex/Astra investigation runtime (Codex lane dropped 2026-11-24)", r"^codex_"),
    ("repair investigator (captions, KiCad grounding, diagnosis)",
     r"^(restoration_|repair_investigator|adaptive_diagnosis$|operator_review_bridge$)"),
    ("evaluation and benchmark instruments",
     r"(_benchmark$|^robot_reference_e2e$|^robot_guidance_|^robot_arm_experiment$|^paired_evaluation$|^scoring_summary$|"
     r"^hypothesis_discrimination$|^golden_intakes$|^identity_perturbations$|^frontier_operator_experiment$|"
     r"^operator_investigation$|^operator_hypothesis_cycle$|^public_web_bench$|^geometry_snapshot$|^splice_manifest$|^mission_runner$)"),
    ("mechanics references and cross-project handoffs",
     r"^mechanical_(kirsch_reference|unilateral_pin_contact|workflow_integration|fixture_handoff|portfolio_handoff)$"),
    ("scheduled jobs and CI workers",
     r"^(landscape_watch|github_data_sources|github_signal_\w+|local_kicad_worker|multicad_toolchain|discrete_electronics_truth)$"),
    ("demonstrator builds run from scripts",
     r"^(drone_\w+|aerial_product_generator|system_example_microdrone|cadclaw_dry_product|teardown_\w+|whole_product_sample|"
     r"product_ecosystem_bridge|filter_\w+|function_\w+|part_scene|change_dossier|real_device_work_package)$"),
]
STATUS_ORDER = ("product", "research", "script", "runnable", "tests-only", "unreached")
STATUS_MEANING = {
    "product": "reached from a shipped entry point (toolbelt, MCP, REST or a console command)",
    "research": "not shipped on purpose: part of a declared research line (RESEARCH_LINES)",
    "script": "reached only from scripts/, projects/, eval/, experiments/, the Makefile or CI",
    "runnable": "has its own `python -m` main, and nothing shipped imports it",
    "tests-only": "only tests import it",
    "unreached": "nothing imports it, not even a test",
}
MOD_NAME = re.compile(r"hardware_splicer(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
FROM_ROOT = re.compile(r"from hardware_splicer import \(?([\w, \n]+)\)?")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _modules() -> dict[str, Path]:
    out = {}
    for p in sorted(PKG.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        parts = list(p.relative_to(PKG.parent).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = p
    return out


def _short(name: str) -> str:
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


class _Graph:
    def __init__(self, mods: dict[str, Path]):
        self.mods = mods
        self.names = set(mods)
        self.trees: dict[str, ast.Module] = {}
        for m, p in mods.items():
            try:
                self.trees[m] = ast.parse(_read(p))
            except SyntaxError:
                pass
        self.lazy = {m: self._lazy_table(t) for m, t in self.trees.items() if mods[m].name == "__init__.py"}
        # helper scripts (pcbnew, tool workers) are run by file path and import their siblings by bare name
        names_by_file: dict[str, list[str]] = defaultdict(list)
        for m, p in mods.items():
            if p.name != "__init__.py":
                names_by_file[p.name].append(m)
        self.by_file = {f: ms[0] for f, ms in names_by_file.items() if len(ms) == 1}
        self.edges = {m: self._imports(m) for m in mods}

    @staticmethod
    def _lazy_table(tree: ast.Module) -> dict[str, str]:
        for n in tree.body:
            if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict)
                    and any(getattr(t, "id", "") in ("_MODULES", "_EXPORTS", "_LAZY") for t in n.targets)):
                return {k.value: v.value for k, v in zip(n.value.keys, n.value.values)
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Constant)}
        return {}

    def best(self, name: str) -> str:
        """The longest prefix of a dotted name that is a module of this package."""
        while name and name not in self.names:
            name = name.rsplit(".", 1)[0] if "." in name else ""
        return name

    def member(self, package: str, attr: str) -> str:
        """What ``from package import attr`` loads: a submodule, a lazy re-export's module, or the package itself."""
        if f"{package}.{attr}" in self.names:
            return f"{package}.{attr}"
        target = self.lazy.get(package, {}).get(attr)
        if target:
            return self.best(f"{package}.{target}")
        return self.best(package)

    def _imports(self, m: str) -> set[str]:
        tree = self.trees.get(m)
        if tree is None:
            return set()
        is_pkg = self.mods[m].name == "__init__.py"
        out: set[str] = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                if n.level:
                    base = m.split(".") if is_pkg else m.split(".")[:-1]
                    base = base[: len(base) - (n.level - 1)]
                    target = ".".join(base + ([n.module] if n.module else []))
                elif n.module and n.module.split(".")[0] == "hardware_splicer":
                    target = n.module
                else:
                    sibling = ".".join(m.split(".")[:-1] + [n.module or ""])
                    if not is_pkg and sibling in self.names:
                        out.add(sibling)
                    continue
                found = self.best(target)
                if found:
                    out.update(self.member(found, a.name) if found == target else found for a in n.names)
            elif (isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_native_tool" and n.args
                  and isinstance(n.args[0], ast.Constant) and PREFIX + str(n.args[0].value) in self.names):
                out.add(PREFIX + str(n.args[0].value))  # the toolbelt runs it with `python -m` in the native interpreter
            elif isinstance(n, ast.Import):
                out.update(self.best(a.name) for a in n.names if a.name.startswith(PREFIX))
                if not is_pkg:
                    out.update(s for a in n.names if (s := ".".join(m.split(".")[:-1] + [a.name])) in self.names)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                if n.value in self.names:
                    out.add(n.value)  # importlib by name, mock.patch targets and similar
                elif n.value.endswith(".py") and n.value.rsplit("/", 1)[-1] in self.by_file:
                    out.add(self.by_file[n.value.rsplit("/", 1)[-1]])  # a helper script run by its path
        out.discard(m)
        out.discard("")
        return out

    def reach(self, starts: set[str]) -> set[str]:
        seen: set[str] = set()
        todo = [s for s in starts if s in self.names]
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            todo.extend(self.edges.get(x, ()))
            parts = x.split(".")
            todo.extend(".".join(parts[:i]) for i in range(2, len(parts)))  # importing a.b.c runs a.b
        return seen

    def refs_in_text(self, text: str) -> set[str]:
        """Modules a non-package file (test, script, Makefile) names."""
        found = {self.best(h) for h in MOD_NAME.findall(text)}
        found.update(self.by_file[f] for f in re.findall(r"hardware_splicer/(?:[\w]+/)*(\w+\.py)", text) if f in self.by_file)
        for group in FROM_ROOT.findall(text):
            found.update(self.member("hardware_splicer", nm) for nm in re.findall(r"\w+", group))
        found.discard("")
        found.discard("hardware_splicer")
        return found


def _console_scripts() -> dict[str, str]:
    toml = _read(ROOT / "pyproject.toml")
    return {cmd: target.split(":")[0] for cmd, target in re.findall(r'^([\w-]+)\s*=\s*"(hardware_splicer[^"]+)"', toml, re.M)}


def _has_main(tree: ast.Module) -> bool:
    return any(isinstance(n, ast.If) and "__main__" in ast.unparse(n.test) for n in tree.body)


def _doc(tree: ast.Module | None) -> str:
    return " ".join((ast.get_docstring(tree) or "").split()) if tree else ""


def _function_fingerprints(g: _Graph) -> dict[str, list[tuple[str, str, int]]]:
    """Top-level functions of five or more lines whose code, docstring aside, is identical in more than one module."""
    groups: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
    for m, tree in g.trees.items():
        for n in tree.body:
            if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            size = (n.end_lineno or n.lineno) - n.lineno + 1
            if size < 5:
                continue
            body = n.body[1:] if (n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
                                  and isinstance(n.body[0].value.value, str)) else n.body
            key = ast.dump(ast.Module(body=body or [ast.Pass()], type_ignores=[]), annotate_fields=False)
            key += ast.dump(n.args, annotate_fields=False)
            groups[hashlib.sha1(key.encode()).hexdigest()].append((_short(m), n.name, size))
    return {k: v for k, v in groups.items() if len({x[0] for x in v}) > 1}


def _similar_modules(g: _Graph, threshold: float = 0.5) -> list[dict[str, Any]]:
    """Pairs of modules that share at least half the distinctive code lines of the smaller one."""
    def lines(p: Path) -> set[str]:
        out = set()
        for line in _read(p).splitlines():
            line = line.strip()
            if len(line) > 12 and not line.startswith(("#", "import ", "from ", '"""', "return", ")", "]", "}")):
                out.add(line)
        return out
    sets = {m: lines(p) for m, p in g.mods.items()}
    big = sorted(m for m in sets if len(sets[m]) >= 20)
    index: dict[str, list[str]] = defaultdict(list)
    for m in big:
        for line in sets[m]:
            index[line].append(m)
    shared: dict[tuple[str, str], int] = defaultdict(int)
    for owners in index.values():
        if 1 < len(owners) <= 12:  # a line in many modules is boilerplate, not a sign of a copy
            for i, a in enumerate(owners):
                for b in owners[i + 1:]:
                    shared[(a, b)] += 1
    out = []
    for (a, b), n in shared.items():
        share = n / min(len(sets[a]), len(sets[b]))
        if n >= 15 and share >= threshold:
            out.append({"a": _short(a), "b": _short(b), "shared_lines": n, "share_of_smaller": round(share, 2)})
    return sorted(out, key=lambda r: (-r["share_of_smaller"], r["a"]))


def build() -> dict[str, Any]:
    g = _Graph(_modules())
    console = _console_scripts()
    entries = {k: {PREFIX + m for m in v} for k, v in SURFACES.items()}
    entries["console"] = {m for m in console.values() if m in g.names}
    reach = {k: g.reach(v) for k, v in entries.items()}
    # entry layer: what a tool, router, server or console command imports itself
    layer = set().union(*entries.values()) | {m for m in reach["rest"] if m.endswith("_api") or m.endswith("_router")}
    direct = set().union(*(g.edges[m] for m in layer)) | layer
    shipped = set().union(*reach.values())
    tool_direct = g.edges.get(PREFIX + "engineering_toolbelt", set())  # imported by a tool handler itself

    test_refs: dict[str, set[str]] = defaultdict(set)
    for t in sorted((ROOT / "tests").rglob("*.py")):
        for m in g.refs_in_text(_read(t)):
            test_refs[m].add(t.name)
    script_files = [p for d in ("scripts", "projects", "eval", "experiments", ".github", "apps") for p in (ROOT / d).rglob("*")
                    if p.is_file() and p.suffix in (".py", ".sh", ".yml", ".yaml", ".mjs", ".cjs", ".js", ".toml")
                    and "node_modules" not in p.parts and "dist" not in p.parts]
    script_files.append(ROOT / "Makefile")
    script_refs: dict[str, set[str]] = defaultdict(set)
    for p in script_files:
        if p.is_file():
            for m in g.refs_in_text(_read(p)):
                script_refs[m].add(str(p.relative_to(ROOT)))
    scripted = g.reach(set(script_refs))
    mains = {m for m, t in g.trees.items() if _has_main(t)}
    importers: dict[str, set[str]] = defaultdict(set)
    for a, bs in g.edges.items():
        for b in bs:
            importers[b].add(a)

    rows = []
    for m, p in g.mods.items():
        if p.name == "__init__.py" and m == "hardware_splicer":
            continue
        short = _short(m)
        doc = _doc(g.trees.get(m))
        area = next((a for a, rx in AREAS if re.search(rx, f"{short} {doc[:400]}".lower())), "other")
        tests = sorted(test_refs.get(m, ()))
        status = ("product" if m in shipped else "script" if m in scripted else "runnable" if m in mains
                  else "tests-only" if tests else "unreached")
        line = next((name for name, rx in RESEARCH_LINES if re.search(rx, short)), None)
        if status != "product" and line:
            status = "research"
        rows.append({
            "module": short, "area": area, "lines": _read(p).count("\n"), "plumbing": bool(PLUMBING.search(p.stem)),
            "status": status, "research_line": line if status == "research" else None, "direct": m in direct, "tool": m in tool_direct, "runnable": m in mains,
            "toolbelt": m in reach["toolbelt"], "mcp": m in reach["mcp"], "rest": m in reach["rest"],
            "console": m in reach["console"], "tests": len(tests), "test_files": tests,
            "importers": sorted(_short(x) for x in importers.get(m, ())),
            "imports": sorted(_short(x) for x in g.edges.get(m, ()) if x != "hardware_splicer"),
            "scripts": sorted(script_refs.get(m, ()))[:8], "about": doc[:400],
        })
    rows.sort(key=lambda r: r["module"])
    areas: dict[str, dict[str, int]] = defaultdict(lambda: {"modules": 0, "capability_modules": 0, "lines": 0, "tested": 0,
                                                            "product": 0, "in_toolbelt": 0})
    for r in rows:
        a = areas[r["area"]]
        a["modules"] += 1
        a["lines"] += r["lines"]
        a["tested"] += r["tests"] > 0
        a["capability_modules"] += not r["plumbing"]
        a["product"] += r["status"] == "product"
        a["in_toolbelt"] += r["tool"]
    dups = sorted(_function_fingerprints(g).values(), key=lambda v: (-(len(v) - 1) * v[0][2], v[0][0]))
    toolbelt_tools = []
    tb = g.trees.get(PREFIX + "engineering_toolbelt")
    if tb is not None:
        for n in ast.walk(tb):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "ToolSpec" and n.args and isinstance(n.args[0], ast.Constant):
                toolbelt_tools.append(n.args[0].value)
    status_counts = {s: {"modules": sum(r["status"] == s for r in rows), "lines": sum(r["lines"] for r in rows if r["status"] == s)}
                     for s in STATUS_ORDER}
    return {
        "schema": "hardware_splicer.capability_map.v2",
        "modules": len(rows), "lines": sum(r["lines"] for r in rows), "tested": sum(r["tests"] > 0 for r in rows),
        "in_toolbelt": sum(r["tool"] for r in rows), "status": status_counts,
        "surfaces": {k: {"entry": sorted(_short(e) for e in v), "reaches": len(reach[k] - {"hardware_splicer"})} for k, v in entries.items()},
        "console_scripts": console, "toolbelt_tools": toolbelt_tools,
        "areas": dict(sorted(areas.items(), key=lambda kv: -kv[1]["lines"])),
        "duplicate_functions": [[{"module": m, "function": f, "lines": n} for m, f, n in grp] for grp in dups],
        "duplicate_lines": sum((len(v) - 1) * v[0][2] for v in dups),
        "similar_modules": _similar_modules(g),
        "rows": rows,
    }


# ------------------------------------------------------------------------------------------------------------- output


def _slug(area: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", area.lower()).strip("-")


def _reach_code(r: dict[str, Any]) -> str:
    return "".join(k for k, f in (("T", r["toolbelt"]), ("M", r["mcp"]), ("R", r["rest"]), ("C", r["console"])) if f) or "-"


def _about(r: dict[str, Any], n: int) -> str:
    return (r["about"][:n] + ("..." if len(r["about"]) > n else "")).replace("|", "/") or "(no description)"


def index_markdown(m: dict[str, Any]) -> str:
    """The short page every agent reads first: totals, entry surfaces, areas, what is disconnected or duplicated."""
    rows = m["rows"]
    out = ["# HS capability map (generated)", "",
           "Generated by `python -m hardware_splicer.capability_map` from the code. Do not edit by hand: regenerate.",
           "Search before reading: `python -m hardware_splicer.capability_map find <words>` lists matching modules with",
           "their reach and tests; `... show <module>` gives one module's importers, imports and tests. Full per-area",
           "tables are in `docs/capability_map/`; the job-level map (which module is canonical for which job) is",
           "`docs/CAPABILITY_CONSOLIDATION.md`.", "",
           f"**{m['modules']} modules, {m['lines']:,} lines; {m['tested']} referenced by a test; {m['in_toolbelt']} called by an engine tool.**", "",
           "| Status | Modules | Lines | Meaning |", "|---|---|---|---|"]
    for s in STATUS_ORDER:
        c = m["status"][s]
        out.append(f"| {s} | {c['modules']} | {c['lines']:,} | {STATUS_MEANING[s]} |")
    out += ["", "## Entry surfaces", "", "| Surface | Entry modules | Modules reached |", "|---|---|---|"]
    for k, s in m["surfaces"].items():
        out.append(f"| {k} | {', '.join('`' + e + '`' for e in s['entry'])} | {s['reaches']} |")
    out += ["", f"Toolbelt tools ({len(m['toolbelt_tools'])}): " + ", ".join(f"`{t}`" for t in m["toolbelt_tools"]) + ".",
            "Console commands: " + ", ".join(f"`{c}`" for c in m["console_scripts"]) + ".", "",
            "Reach codes in the area pages: **T** toolbelt, **M** MCP server, **R** REST product API, **C** console command.",
            "", "## Areas", "", "| Area | Modules | Engineering | Lines | Tested | Shipped | Called by a tool | Page |",
            "|---|---|---|---|---|---|---|---|"]
    for a, s in m["areas"].items():
        out.append(f"| {a} | {s['modules']} | {s['capability_modules']} | {s['lines']:,} | {s['tested']} | {s['product']} | "
                   f"{s['in_toolbelt']} | [{_slug(a)}](capability_map/{_slug(a)}.md) |")
    lines: dict[str, list[int]] = {}
    for r in rows:
        if r["status"] == "research":
            lines.setdefault(r["research_line"], [0, 0])
            lines[r["research_line"]][0] += 1
            lines[r["research_line"]][1] += r["lines"]
    out += ["", "## Research lines (not shipped on purpose)", "", "| Line | Modules | Lines |", "|---|---|---|"]
    out += [f"| {name} | {n} | {loc:,} |" for name, (n, loc) in sorted(lines.items(), key=lambda kv: -kv[1][1])]
    unshipped = _unshipped(rows)
    out += ["", f"## Undecided: engineering modules nothing shipped reaches and no research line claims ({len(unshipped)})", "",
            "The 20 largest; all of them, with what reaches each, are in",
            "[capability_map/not-shipped.md](capability_map/not-shipped.md). Decide per module: wire it into the toolbelt,",
            "declare it in RESEARCH_LINES, or delete it.", "",
            "| Module | Status | Lines | Tests | What it says it does |", "|---|---|---|---|---|"]
    out += [f"| `{r['module']}` | {r['status']} | {r['lines']} | {r['tests']} | {_about(r, 90)} |" for r in unshipped[:20]]
    out += ["", "## Modules that look like copies of each other", "",
            "Pairs sharing at least half the distinctive code lines of the smaller module.", "",
            "| Module | Module | Shared lines | Share of smaller |", "|---|---|---|---|"]
    out += [f"| `{p['a']}` | `{p['b']}` | {p['shared_lines']} | {p['share_of_smaller']} |" for p in m["similar_modules"]]
    out += ["", f"## Identical helper functions ({len(m['duplicate_functions'])} groups, {m['duplicate_lines']} redundant lines)", "",
            "Top-level functions of five or more lines whose code is identical in several modules. Largest first, top 25.", "",
            "| Function | Lines | Copies in |", "|---|---|---|"]
    for grp in m["duplicate_functions"][:25]:
        names = ", ".join(f"`{x['module']}`" + ("" if x["function"] == grp[0]["function"] else f" (`{x['function']}`)") for x in grp)
        out.append(f"| `{grp[0]['function']}` | {grp[0]['lines']} | {names} |")
    return "\n".join(out) + "\n"


def _unshipped(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Engineering modules nothing shipped reaches and no research line claims: each needs a decision."""
    return sorted((r for r in rows if r["status"] not in ("product", "research") and not r["plumbing"]),
                  key=lambda r: (-r["lines"], r["module"]))


def unshipped_markdown(m: dict[str, Any]) -> str:
    out = ["# HS capability map: undecided engineering modules (generated)", "",
           "Generated by `python -m hardware_splicer.capability_map`. Nothing shipped reaches these and no declared research",
           "line claims them: wire, declare or delete each. Status meanings: [CAPABILITY_MAP.md](../CAPABILITY_MAP.md).", "",
           "| Module | Status | Area | Lines | Tests | Reached from | What it says it does |", "|---|---|---|---|---|---|---|"]
    for r in _unshipped(m["rows"]):
        src = ", ".join(r["scripts"][:2]) or ", ".join(r["importers"][:2]) or "-"
        out.append(f"| `{r['module']}` | {r['status']} | {r['area']} | {r['lines']} | {r['tests']} | {src} | {_about(r, 120)} |")
    return "\n".join(out) + "\n"


def area_markdown(m: dict[str, Any], area: str) -> str:
    rows = sorted((r for r in m["rows"] if r["area"] == area), key=lambda r: (r["plumbing"], -r["lines"], r["module"]))
    out = [f"# HS capability map: {area} (generated)", "",
           "Generated by `python -m hardware_splicer.capability_map`. Reach: **T** toolbelt, **M** MCP, **R** REST, **C** console.",
           "Status and the other areas: [CAPABILITY_MAP.md](../CAPABILITY_MAP.md).", "",
           "| Module | Lines | Tests | Status | Reach | What it says it does |", "|---|---|---|---|---|---|"]
    for r in rows:
        name = f"`{r['module']}`" + (" (plumbing)" if r["plumbing"] else "")
        out.append(f"| {name} | {r['lines']} | {r['tests']} | {r['status']} | {_reach_code(r)} | {_about(r, 200)} |")
    return "\n".join(out) + "\n"


def outputs(m: dict[str, Any]) -> dict[Path, str]:
    head = json.dumps({k: v for k, v in m.items() if k != "rows"}, indent=1, ensure_ascii=False)
    body = ",\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in m["rows"])
    files = {DOCS / "capability_map.json": head[:-2] + ',\n "rows": [\n' + body + "\n ]\n}\n",
             DOCS / "CAPABILITY_MAP.md": index_markdown(m)}
    for a in m["areas"]:
        files[DOCS / "capability_map" / f"{_slug(a)}.md"] = area_markdown(m, a)
    files[DOCS / "capability_map" / "not-shipped.md"] = unshipped_markdown(m)
    return files


def find(m: dict[str, Any], words: list[str], limit: int = 15) -> list[dict[str, Any]]:
    """Modules whose name or description mention the words, best first: name hits weigh more, shipped and tested rank up."""
    words = [w.lower() for w in words if w.strip()]
    scored = []
    for r in m["rows"]:
        name, about = r["module"].lower(), r["about"].lower()
        score = sum(3 * (w in name) + (w in about) for w in words)
        if score and all(w in name or w in about for w in words[:1]):
            score += 0.5 * (r["status"] == "product") + 0.25 * (r["tests"] > 0) - 0.5 * r["plumbing"]
            scored.append((score, r))
    scored.sort(key=lambda sr: (-sr[0], -sr[1]["lines"]))
    return [r for _, r in scored[:limit]]


def _load_or_build() -> dict[str, Any]:
    return build()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "find":
        for r in find(_load_or_build(), argv[1:]):
            print(f"{r['module']:48s} {r['status']:10s} {_reach_code(r):4s} tests={r['tests']:<3d} {r['lines']:>5d}L  {_about(r, 110)}")
        return 0
    if argv and argv[0] == "show":
        m = _load_or_build()
        rows = {r["module"]: r for r in m["rows"]}
        r = rows.get(argv[1] if len(argv) > 1 else "")
        if r is None:
            print(f"no module {argv[1:]}; try: find {' '.join(argv[1:])}", file=sys.stderr)
            return 2
        print(json.dumps({k: r[k] for k in ("module", "area", "status", "direct", "lines", "tests", "test_files", "importers",
                                            "imports", "scripts", "about")} | {"reach": _reach_code(r)}, indent=1))
        return 0
    m = build()
    files = outputs(m)
    if argv and argv[0] == "--check":
        # Only the module list is checked: line counts and imports move with every edit, a new or deleted module is what
        # an agent reading the map must not miss.
        path = DOCS / "capability_map.json"
        listed = {r["module"] for r in json.loads(_read(path))["rows"]} if path.is_file() else set()
        current = {r["module"] for r in m["rows"]}
        for name in sorted(current - listed):
            print(f"not in the map: {name}")
        for name in sorted(listed - current):
            print(f"in the map but gone: {name}")
        if listed != current:
            print("regenerate with: PYTHONPATH=src python -m hardware_splicer.capability_map")
        return 0 if listed == current else 1
    (DOCS / "capability_map").mkdir(parents=True, exist_ok=True)
    for p in (DOCS / "capability_map").glob("*.md"):
        if p not in files:
            p.unlink()
    for p, text in files.items():
        p.write_text(text, encoding="utf-8")
    print(json.dumps({k: m[k] for k in ("modules", "lines", "tested", "in_toolbelt", "duplicate_lines")} | {"status": m["status"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
