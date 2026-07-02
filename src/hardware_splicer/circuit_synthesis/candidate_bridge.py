"""Bridge synthesis candidates into the existing compose/build spine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from ..auto_wire import compose_build_graph_from_module_ids
from ..build_compiler import compile_from_netlist
from ..design_quality import build_design_quality_gate
from ..netlist.lower import build_graph_to_netlist
from .ir import SynthesisCandidate
from .operator_lowering import apply_operator_lowering
from .topology_library import evaluate_topology_authority


SCHEMA_VERSION = "hardware_splicer.circuit_synthesis_bridge.v1"


def compile_synthesis_candidate(
    candidate: SynthesisCandidate | Mapping[str, Any],
    *,
    out_dir: str | Path,
    export_gerber: bool = False,
    request_id: str | None = None,
) -> Dict[str, Any]:
    """Compile a ready-for-review synthesis candidate through the strict graph path.

    Blocked candidates never compile. This keeps topology planning separate from
    fabrication/readiness authority.
    """

    synthesis_candidate = (
        candidate if isinstance(candidate, SynthesisCandidate) else SynthesisCandidate.from_dict(candidate)
    )
    candidate_body = synthesis_candidate.to_dict()
    if synthesis_candidate.blocked:
        return _blocked_payload(
            candidate_body,
            out_dir=out_dir,
            request_id=request_id,
            error="candidate_blocked",
            message="Synthesis candidate has blocked constraints or missing evidence.",
        )

    build_path = dict(synthesis_candidate.recommended_build_path or {})
    module_ids = [str(mid) for mid in build_path.get("module_ids") or [] if str(mid).strip()]
    if len(module_ids) < 2:
        return _blocked_payload(
            candidate_body,
            out_dir=out_dir,
            request_id=request_id,
            error="insufficient_modules",
            message="Synthesis candidate does not provide enough known modules for strict graph compile.",
        )

    composed = compose_build_graph_from_module_ids(module_ids)
    graph = dict(composed.get("graph") or {})
    lowering = apply_operator_lowering(synthesis_candidate, graph)
    graph = lowering.graph
    if len(graph.get("nodes") or []) < 2 or not graph.get("wires"):
        return _blocked_payload(
            candidate_body,
            out_dir=out_dir,
            request_id=request_id,
            error="candidate_graph_unwired",
            message="Synthesis candidate modules did not produce a connected graph.",
        )

    constraints = {
        "graph_mode": "scratch",
        "synthesis_candidate_id": synthesis_candidate.candidate_id,
        "synthesis_result": synthesis_candidate.result,
        "synthesis_missing_evidence": list(synthesis_candidate.missing_evidence),
        "synthesis_constraints": [row.to_dict() for row in synthesis_candidate.constraints],
    }
    target = Path(out_dir)
    netlist = build_graph_to_netlist(graph, source=f"synthesis_candidate:{synthesis_candidate.candidate_id}")
    compile_result = compile_from_netlist(
        netlist,
        target,
        export_gerber=export_gerber,
        build_id=str(build_path.get("build_id") or "generic_low_voltage_build"),
    )
    quality = dict(compile_result.design_quality or {})
    quality.setdefault("synthesis_candidate_id", synthesis_candidate.candidate_id)
    quality.setdefault("synthesis_compile_mode", "strict_candidate_graph")
    gate = dict(build_design_quality_gate(quality))
    topology_authority = evaluate_topology_authority(
        synthesis_candidate,
        graph=graph,
        lowering_report=lowering.report,
        compile_ok=compile_result.ok,
        build_ready=bool(gate.get("build_ready")),
    )
    quality.setdefault("topology_authority", topology_authority)
    payload = {
        "ok": bool(compile_result.ok and gate.get("build_ready")),
        "mode": "strict_synthesis_netlist",
        "out_dir": str(target),
        "build_id": compile_result.build_id,
        "module_ids": module_ids,
        "graph": graph,
        "netlist": netlist.to_dict(),
        "constraints": constraints,
        "warnings": composed.get("warnings") or [],
        "notes": list(composed.get("notes") or []) + _lowering_notes(lowering.report),
        "topology_lowering": lowering.report,
        "topology_authority": topology_authority,
        "support_components": list(graph.get("support_components") or []),
        "topology_nets": list(graph.get("topology_nets") or []),
        "physical_support_lowering": dict(graph.get("physical_support_lowering") or {}),
        "compile_result": compile_result.to_dict(),
        "design_quality": quality,
        "design_quality_gate": gate,
        "artifacts": {
            "build_graph": compile_result.build_graph_file,
            "kicad_pcb": compile_result.kicad_pcb_file,
            "design_quality": compile_result.design_quality_file,
        },
    }
    from ..project_package import write_project_package_artifacts

    bridge_result = {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(payload.get("ok")),
        "request_id": request_id,
        "out_dir": str(target),
        "candidate": candidate_body,
        "module_ids": module_ids,
        "topology_lowering": lowering.report,
        "topology_authority": topology_authority,
        "support_components": list(graph.get("support_components") or []),
        "topology_nets": list(graph.get("topology_nets") or []),
        "physical_support_lowering": dict(graph.get("physical_support_lowering") or {}),
        "compose_result": payload,
        "design_quality_gate": gate,
        "claim_boundary": (
            "Compiled from bounded synthesis candidate. This is ready for review only; "
            "DRC/fabrication/bench gates still control readiness claims."
        ),
        "goal": str((synthesis_candidate.metadata or {}).get("goal") or ""),
        "project_name": synthesis_candidate.candidate_id,
        "build_id": compile_result.build_id,
    }
    package_write = write_project_package_artifacts(
        target,
        result=bridge_result,
        source="circuit_synthesis",
        candidate=candidate_body,
    )
    bridge_result["artifacts"] = {**bridge_result.get("artifacts", {}), **(package_write.get("artifacts") or {})}
    bridge_result["project_package"] = package_write.get("package")
    return bridge_result


def _lowering_notes(report: Mapping[str, Any]) -> list[str]:
    actions = list(report.get("actions") or [])
    if not actions:
        return []
    return [f"Applied topology operator lowering actions: {len(actions)}."]


def _blocked_payload(
    candidate: Mapping[str, Any],
    *,
    out_dir: str | Path,
    request_id: str | None,
    error: str,
    message: str,
) -> Dict[str, Any]:
    from ..project_package import write_project_package_artifacts

    blocked = {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "request_id": request_id,
        "out_dir": str(Path(out_dir)),
        "error": error,
        "message": message,
        "candidate": dict(candidate),
        "topology_authority": evaluate_topology_authority(candidate),
        "missing_evidence": list(candidate.get("missing_evidence") or []),
        "constraints": list(candidate.get("constraints") or []),
        "claim_boundary": "No compile was attempted because synthesis authority is not closed.",
        "project_name": str(candidate.get("candidate_id") or "blocked_candidate"),
    }
    package_write = write_project_package_artifacts(
        out_dir,
        result=blocked,
        source="circuit_synthesis_blocked",
        candidate=dict(candidate),
    )
    blocked["artifacts"] = package_write.get("artifacts") or {}
    blocked["project_package"] = package_write.get("package")
    return blocked
