from __future__ import annotations

from hardware_splicer.bom_generator import build_bom_from_graph


def test_catalog_modules_have_mpn_hints() -> None:
    module_ids = [
        "bme280",
        "hc-sr04",
        "ssd1306-128x64",
        "ldo-ams1117-3v3",
        "ldo-ams1117-5v",
        "relay-1ch-5v",
    ]
    bom = build_bom_from_graph({"nodes": [{"id": f"n{i}", "moduleId": mid} for i, mid in enumerate(module_ids, start=1)]})
    lines = {row["module_id"]: row for row in bom["lines"]}
    for module_id in module_ids:
        assert lines[module_id]["mpn"], f"missing MPN for {module_id}"
