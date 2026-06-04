"""Minimal KiCad 6+ S-expression netlist parser.

This intentionally avoids importing `src.intelligence` because that package has
heavy side effects (vision/ML imports) that break lightweight engine usage.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from src.engines.kicad_sexp import SexpError, parse_sexp


def _sexp_token_to_text(value: Any) -> str:
    if isinstance(value, list):
        return "(" + "".join(_sexp_token_to_text(part) for part in value) + ")"
    return str(value)


class KiCadParser:
    """Parses KiCad netlists across modern and legacy formats."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nets: Dict[str, Any] = {}
        self.components: Dict[str, Any] = {}

    def parse(self) -> Dict[str, Any]:
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        if content.lstrip().startswith("# EESchema Netlist Version 1.1"):
            return self._parse_legacy_v1(content)

        try:
            return self._parse_modern_sexp(content)
        except SexpError:
            # Fall back to the older regex parser for malformed or uncommon
            # exports. The structured path is preferred for valid KiCad files.
            pass

        token = r'(?:\"([^\"]+)\"|([^\s\)]+))'

        # --- Parse Components ---
        comps_block_match = re.search(r"\(components(.*?)\)\s*\)\s*\(libparts", content, re.DOTALL)
        if not comps_block_match:
            comps_block_match = re.search(r"\(components(.*?)\)\s*\)\s*\(nets", content, re.DOTALL)

        if comps_block_match:
            comps_body = comps_block_match.group(1)
            comp_matches = re.findall(
                rf"\(comp\s+\(ref\s+{token}\)(.*?)\)\s*(?=\(comp|\s*$)",
                comps_body,
                re.DOTALL,
            )

            for ref_q, ref_u, body in comp_matches:
                ref = ref_q or ref_u
                val_match = re.search(r"^\s*\(value\s+(.+?)\)\s*$", body, re.MULTILINE)
                value = self._strip_token(val_match.group(1)) if val_match else "Unknown"

                fp_match = re.search(r"^\s*\(footprint\s+(.+?)\)\s*$", body, re.MULTILINE)
                footprint = self._strip_token(fp_match.group(1)) if fp_match else "Unknown"

                self.components[ref] = {"value": value, "footprint": footprint}

        # --- Parse Nets ---
        net_blocks = re.findall(
            rf"\(net\s+\(code\s+{token}\)\s+\(name\s+{token}\)(.*?)\)\s*(?=\(net|\)\s*$)",
            content,
            re.DOTALL,
        )

        for code_q, code_u, name_q, name_u, body in net_blocks:
            code = code_q or code_u
            name = name_q or name_u
            nodes = []
            node_matches = re.findall(rf"\(node\s+\(ref\s+{token}\)\s+\(pin\s+{token}\)", body)
            for ref_q, ref_u, pin_q, pin_u in node_matches:
                ref = ref_q or ref_u
                pin = pin_q or pin_u
                nodes.append({"ref": ref, "pin": pin})

            self.nets[name] = {"code": code, "nodes": nodes}

        return {"nets": self.nets, "components": self.components}

    def _parse_modern_sexp(self, content: str) -> Dict[str, Any]:
        ast = parse_sexp(content)

        def first_child(node: list, head: str) -> list | None:
            for child in node:
                if isinstance(child, list) and child and child[0] == head:
                    return child
            return None

        def child_value(node: list, head: str, default: str = "Unknown") -> str:
            child = first_child(node, head)
            if child and len(child) >= 2:
                return "".join(_sexp_token_to_text(part) for part in child[1:])
            return default

        components_node = first_child(ast, "components") if isinstance(ast, list) else None
        if components_node:
            for comp in components_node:
                if not isinstance(comp, list) or not comp or comp[0] != "comp":
                    continue
                ref = child_value(comp, "ref", "")
                if not ref:
                    continue
                self.components[ref] = {
                    "value": child_value(comp, "value"),
                    "footprint": child_value(comp, "footprint"),
                }

        nets_node = first_child(ast, "nets") if isinstance(ast, list) else None
        if nets_node:
            for net in nets_node:
                if not isinstance(net, list) or not net or net[0] != "net":
                    continue
                code = child_value(net, "code", "")
                name = child_value(net, "name", "")
                if not name:
                    continue
                nodes = []
                for child in net:
                    if not isinstance(child, list) or not child or child[0] != "node":
                        continue
                    ref = child_value(child, "ref", "")
                    pin = child_value(child, "pin", "")
                    if ref and pin:
                        nodes.append({"ref": ref, "pin": pin})
                self.nets[name] = {"code": code, "nodes": nodes}

        return {"nets": self.nets, "components": self.components}

    @staticmethod
    def _strip_token(token: str) -> str:
        token = (token or "").strip()
        if token.startswith('"') and token.endswith('"') and len(token) >= 2:
            return token[1:-1]
        return token

    def _parse_legacy_v1(self, content: str) -> Dict[str, Any]:
        code_counter = 1
        current_ref = None
        lines = content.splitlines()

        for raw_line in lines:
            line = raw_line.rstrip()
            comp_match = re.match(r"\s*\(\s*/[^\s]+\s+\$\S+\s+([^\s]+)\s+(.+?)\s+\{Lib=([^}]+)\}\s*$", line)
            if comp_match:
                current_ref = comp_match.group(1)
                value = comp_match.group(2).strip()
                lib = comp_match.group(3).strip()
                self.components[current_ref] = {"value": value, "footprint": lib}
                continue

            if current_ref is None:
                continue

            if re.match(r"\s*\)\s*$", line):
                current_ref = None
                continue

            pin_match = re.match(r"\s*\(\s*([^\s\)]+)\s+([^\)]+?)\s*\)\s*$", line)
            if pin_match:
                pin = pin_match.group(1).strip()
                net = pin_match.group(2).strip()
                if net not in self.nets:
                    self.nets[net] = {"code": str(code_counter), "nodes": []}
                    code_counter += 1
                self.nets[net]["nodes"].append({"ref": current_ref, "pin": pin})

        return {"nets": self.nets, "components": self.components}
