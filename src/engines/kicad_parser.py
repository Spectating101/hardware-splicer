"""Minimal KiCad 6+ S-expression netlist parser.

This intentionally avoids importing `src.intelligence` because that package has
heavy side effects (vision/ML imports) that break lightweight engine usage.
"""

from __future__ import annotations

import re
from typing import Any, Dict


class KiCadParser:
    """Parses KiCad 6+ S-Expression Netlists (.net)."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nets: Dict[str, Any] = {}
        self.components: Dict[str, Any] = {}

    def parse(self) -> Dict[str, Any]:
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # --- Parse Components ---
        comps_block_match = re.search(r"\(components(.*?)\)\s*\)\s*\(libparts", content, re.DOTALL)
        if not comps_block_match:
            comps_block_match = re.search(r"\(components(.*?)\)\s*\)\s*\(nets", content, re.DOTALL)

        if comps_block_match:
            comps_body = comps_block_match.group(1)
            comp_matches = re.findall(
                r"\(comp\s+\(ref\s+\"([^\"]+)\"\)(.*?)\)\s*(?=\(comp|\s*$)",
                comps_body,
                re.DOTALL,
            )

            for ref, body in comp_matches:
                val_match = re.search(r"\(value\s+\"([^\"]+)\"\)", body)
                value = val_match.group(1) if val_match else "Unknown"

                fp_match = re.search(r"\(footprint\s+\"([^\"]+)\"\)", body)
                footprint = fp_match.group(1) if fp_match else "Unknown"

                self.components[ref] = {"value": value, "footprint": footprint}

        # --- Parse Nets ---
        net_blocks = re.findall(
            r"\(net\s+\(code\s+\"([^\"]+)\"\)\s+\(name\s+\"([^\"]+)\"\)(.*?)\)\s*(?=\(net|\)\s*$)",
            content,
            re.DOTALL,
        )

        for code, name, body in net_blocks:
            nodes = []
            node_matches = re.findall(r"\(node\s+\(ref\s+\"([^\"]+)\"\)\s+\(pin\s+\"([^\"]+)\"\)", body)
            for ref, pin in node_matches:
                nodes.append({"ref": ref, "pin": pin})

            self.nets[name] = {"code": code, "nodes": nodes}

        return {"nets": self.nets, "components": self.components}
