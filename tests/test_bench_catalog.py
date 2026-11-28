"""Every HS toolbelt tool is filed in the workbench's explorer, so a new tool cannot silently go missing there."""
from __future__ import annotations

import re
from pathlib import Path

from hardware_splicer import engineering_toolbelt

CATALOG = Path(__file__).resolve().parents[1] / "apps" / "splice-ui" / "src" / "bench" / "catalog.js"


def test_every_toolbelt_tool_has_an_explorer_group():
    block = CATALOG.read_text(encoding="utf-8").split("export const TOOL_GROUPS", 1)[1].split("];", 1)[0]
    filed = set(re.findall(r'"(hs_[a-z0-9_]+)"', block))
    tools = set(engineering_toolbelt.TOOLS)
    assert tools - filed == set(), f"add to TOOL_GROUPS in {CATALOG.name}: {sorted(tools - filed)}"
    assert filed - tools == set(), f"no such toolbelt tool: {sorted(filed - tools)}"
