"""Write compile failure casefiles for engine debugging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional


SCHEMA_VERSION = "hardware_splicer.compile_casefile.v1"


def write_compile_casefile(
    build_dir: Path,
    *,
    build_id: str,
    error: str,
    graph: Optional[Mapping[str, Any]] = None,
    netlist: Optional[Mapping[str, Any]] = None,
    erc: Optional[Mapping[str, Any]] = None,
    quality: Optional[Mapping[str, Any]] = None,
    splice_plan: Optional[Mapping[str, Any]] = None,
) -> str:
    build_dir.mkdir(parents=True, exist_ok=True)
    path = build_dir / "COMPILE_CASEFILE.json"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "build_id": build_id,
        "error": error,
        "graph": dict(graph) if graph else None,
        "netlist": dict(netlist) if netlist else None,
        "erc": dict(erc) if erc else None,
        "quality": dict(quality) if quality else None,
        "splice_plan": dict(splice_plan) if splice_plan else None,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)
