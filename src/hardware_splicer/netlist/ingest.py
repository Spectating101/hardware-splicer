"""Load netlist files — shared by CLI and API (netlist-compile parity)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from ..integrations.circuit_json_import import circuit_json_to_netlist
from .import_kicad import parse_kicad_netlist
from .ir import CircuitNetlist

NetlistFormat = Literal["auto", "ir_json", "kicad_netlist", "circuit_json"]


def detect_netlist_format(path: Path, *, explicit: NetlistFormat | None = None) -> NetlistFormat:
    if explicit and explicit != "auto":
        return explicit
    suffix = path.suffix.lower()
    if suffix == ".net":
        return "kicad_netlist"
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("(") and "(export" in text[:200].lower():
        return "kicad_netlist"
    payload = json.loads(text)
    if isinstance(payload, list):
        return "circuit_json"
    return "ir_json"


def load_netlist_file(
    path: str | Path,
    *,
    netlist_format: NetlistFormat = "auto",
    source_label: str | None = None,
) -> CircuitNetlist:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"netlist file not found: {source}")
    fmt = detect_netlist_format(source, explicit=netlist_format)
    text = source.read_text(encoding="utf-8")
    label = source_label or str(source)
    if fmt == "kicad_netlist":
        return parse_kicad_netlist(text)
    if fmt == "circuit_json":
        docs = json.loads(text)
        if not isinstance(docs, list):
            raise ValueError("circuit-json input must be a JSON array")
        return circuit_json_to_netlist(docs, source=label)
    payload = json.loads(text)
    return CircuitNetlist.from_dict(payload)


def load_netlist_payload(
    payload: dict[str, Any],
    *,
    netlist_format: NetlistFormat = "ir_json",
    source_label: str = "inline",
) -> CircuitNetlist:
    if netlist_format == "circuit_json":
        docs = payload.get("documents") or payload.get("circuit_json")
        if not isinstance(docs, list):
            raise ValueError("circuit_json payload requires a documents array")
        return circuit_json_to_netlist(docs, source=source_label)
    return CircuitNetlist.from_dict(payload)
