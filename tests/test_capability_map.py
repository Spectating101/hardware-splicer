"""Capability map: every module is listed, reach follows the full import graph, the generated files are current."""
from __future__ import annotations

from pathlib import Path

from hardware_splicer import capability_map as cm


def test_every_module_is_mapped_and_reach_is_transitive():
    m = cm.build()
    pkg = Path(cm.__file__).resolve().parent
    on_disk = set()
    for p in pkg.rglob("*.py"):
        if "__pycache__" in p.parts or p.parent == pkg and p.name == "__init__.py":
            continue
        parts = p.relative_to(pkg).with_suffix("").parts
        on_disk.add(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    assert {r["module"] for r in m["rows"]} == on_disk
    rows = {r["module"]: r for r in m["rows"]}
    assert rows["junk_catalogue"]["toolbelt"] and rows["junk_catalogue"]["tool"]   # imported inside a tool handler
    assert rows["routing_engine"]["toolbelt"] and not rows["routing_engine"]["tool"]  # only through component_board_pipeline
    assert rows["engineering_toolbelt_api"]["plumbing"] and not rows["mechanical_cad_fem"]["plumbing"]
    # resolved by full dotted name: a subpackage module is reached through its package's relative imports
    assert rows["circuit_synthesis.motor_driver_planner"]["status"] == "product"
    assert sum(m["status"][s]["modules"] for s in cm.STATUS_ORDER) == m["modules"]


def test_lazy_root_exports_count_as_imports_of_their_module():
    g = cm._Graph(cm._modules())
    lazy = g.lazy["hardware_splicer"]
    name, module = next(iter(lazy.items()))
    assert g.member("hardware_splicer", name) == g.best(f"hardware_splicer.{module}")


def test_find_ranks_name_matches_and_skips_unrelated_modules():
    hits = [r["module"] for r in cm.find(cm.build(), ["kicad", "diff"])]
    assert hits[0] == "kicad_diff"
    assert not cm.find(cm.build(), ["zzzz-no-such-capability"])


def test_generated_capability_map_is_current():
    """Adding or removing a module changes the map: regenerate with python -m hardware_splicer.capability_map."""
    assert cm.main(["--check"]) == 0


def test_every_engineering_module_is_shipped_or_in_a_declared_research_line():
    """Nothing piles up disconnected: wire a new module into the toolbelt, MCP, REST or a console command, or declare its
    line of work in capability_map.RESEARCH_LINES."""
    undecided = [r["module"] for r in cm._unshipped(cm.build()["rows"])]
    assert undecided == [], f"wire these or declare them in RESEARCH_LINES: {undecided}"
