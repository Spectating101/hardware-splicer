"""Netlist-first compile path (general engine entry)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from ..pcb.geometry_compile import compile_graph_to_artifacts
from ..pcb.drc_fix_loop import compile_with_drc_fixup_loop
from ..compile_casefile import write_compile_casefile
from ..integrations.circuit_json_adapter import netlist_to_circuit_json
from ..integrations.schematic_export import write_schematic_for_netlist
from ..pcb.kicad_cli_erc import run_kicad_cli_erc, summarize_erc_for_quality
from .erc import run_erc, verify_net_coverage
from .ir import CircuitNetlist
from .lower import build_graph_to_netlist, netlist_to_build_graph
from .passives import suggest_passives
from .quality_flags import finalize_launch_quality


def netlist_from_build_graph(graph: Mapping[str, Any]) -> CircuitNetlist:
    return build_graph_to_netlist(graph, source="build_graph")


def compile_netlist_to_artifacts(
    netlist: CircuitNetlist,
    build_id: str,
    out_dir: str | Path,
    *,
    graph: Optional[Mapping[str, Any]] = None,
    notes: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """ERC → graph (from netlist or provided) → geometry/DRC/KiCad."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    notes = list(notes or [])
    warnings = list(warnings or [])

    netlist_path = out / "circuit_netlist.json"
    netlist_path.write_text(json.dumps(netlist.to_dict(), indent=2), encoding="utf-8")

    circuit_json_path = out / "circuit_json.json"
    circuit_json_path.write_text(
        json.dumps(netlist_to_circuit_json(netlist, source_build_id=build_id), indent=2),
        encoding="utf-8",
    )

    sch_path = out / "main_ctrl_build.kicad_sch"
    write_schematic_for_netlist(netlist, sch_path, title=build_id)
    sch_erc = run_kicad_cli_erc(sch_path, out_dir=out)

    erc = run_erc(netlist)
    erc_path = out / "ERC.json"
    erc_path.write_text(json.dumps(erc, indent=2), encoding="utf-8")

    if not erc.get("pass"):
        write_compile_casefile(
            out,
            build_id=build_id,
            error="erc_failed",
            netlist=netlist.to_dict(),
            erc=erc,
        )
        return {
            "ok": False,
            "error": "erc_failed",
            "paths": {"circuit_netlist": str(netlist_path), "erc": str(erc_path)},
            "erc": erc,
            "quality": {
                "build_ready": False,
                "erc_pass": False,
                "erc_errors": erc.get("errors"),
                "circuit_readiness": "erc_blocked",
            },
        }

    passive_suggestions = suggest_passives(netlist)
    if passive_suggestions:
        warnings.extend(s.get("message", "") for s in passive_suggestions if s.get("message"))

    resolved_graph = dict(graph) if graph else netlist_to_build_graph(netlist)
    if graph:
        coverage = verify_net_coverage(netlist, resolved_graph)
        if not coverage.get("pass"):
            warnings.append(f"net coverage gaps: {coverage.get('missing_nets')}")

    payload = compile_with_drc_fixup_loop(
        compile_graph_to_artifacts,
        build_id,
        out,
        resolved_graph,
        compile_kwargs={
            "notes": notes + ["Compiled via netlist IR path."],
            "warnings": warnings,
        },
    )
    quality = dict(payload.get("quality") or {})
    quality["erc_pass"] = True
    quality["erc_errors"] = 0
    quality["erc_warnings"] = erc.get("warnings", 0)
    quality["circuit_netlist_path"] = str(netlist_path)
    quality["erc_report_path"] = str(erc_path)
    quality["circuit_json_path"] = str(circuit_json_path)
    quality["kicad_sch_path"] = str(sch_path)
    quality.update(summarize_erc_for_quality(sch_erc))
    quality["compile_engine"] = "netlist_v2"
    quality["passive_suggestions"] = passive_suggestions
    quality = finalize_launch_quality(quality)
    quality_path = out / "DESIGN_QUALITY.json"
    quality_path.write_text(json.dumps(quality, indent=2), encoding="utf-8")
    payload["quality"] = quality
    payload["erc"] = erc
    payload["sch_erc"] = sch_erc
    payload["paths"] = {
        **(payload.get("paths") or {}),
        "circuit_netlist": str(netlist_path),
        "erc": str(erc_path),
        "circuit_json": str(circuit_json_path),
        "kicad_sch": str(sch_path),
        "kicad_erc": sch_erc.get("report_path"),
    }
    payload["ok"] = bool(payload.get("ok")) and erc.get("pass")
    return payload
