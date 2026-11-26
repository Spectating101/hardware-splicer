"""Capability map: every module is listed, reach follows imports through other modules, plumbing is marked."""
from __future__ import annotations

from pathlib import Path

from hardware_splicer import capability_map as cm


def test_every_module_is_mapped_and_reach_is_transitive():
    m = cm.build()
    pkg = Path(cm.__file__).resolve().parent
    on_disk = {".".join(p.relative_to(pkg).with_suffix("").parts) for p in pkg.rglob("*.py")
               if "__pycache__" not in p.parts and p.name != "__init__.py"}
    assert {r["module"] for r in m["rows"]} == on_disk
    rows = {r["module"]: r for r in m["rows"]}
    assert rows["junk_catalogue"]["toolbelt"]          # imported inside a tool handler
    assert rows["routing_engine"]["toolbelt"]          # reached only through component_board_pipeline
    assert rows["engineering_toolbelt_api"]["plumbing"] and not rows["mechanical_cad_fem"]["plumbing"]
