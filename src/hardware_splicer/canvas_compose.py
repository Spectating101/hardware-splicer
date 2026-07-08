"""Canvas / editor graph → same netlist compile path (lightweight, no FreeRouting)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .auto_wire import compose_build_graph_from_canvas_nodes
from .build_compiler import BuildCompileResult, compile_catalog_build
from .material_modes import material_mode_summary, resolve_material_mode


@dataclass
class CanvasCompileResult:
    ok: bool
    build_id: str
    graph: Dict[str, Any]
    material_mode: str
    compile_result: Optional[BuildCompileResult] = None
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "build_id": self.build_id,
            "graph_mode": "canvas",
            "material_mode": self.material_mode,
            "graph": self.graph,
            "notes": self.notes,
            "error": self.error,
            "compile_result": self.compile_result.to_dict() if self.compile_result else None,
        }


def build_canvas_graph(
    *,
    nodes: Sequence[Mapping[str, Any]],
    wires: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
    salvage_mode: bool = False,
    material_mode: str | None = None,
    drc_fixup: Mapping[str, float] | None = None,
) -> Dict[str, Any]:
    """Merge editor nodes/wires or auto-wire unknown connections."""
    mode = str(material_mode or resolve_material_mode(constraints=constraints, salvage_mode=salvage_mode))
    if wires:
        graph = {
            "nodes": [dict(n) for n in nodes],
            "wires": [dict(w) for w in wires],
        }
    else:
        graph = compose_build_graph_from_canvas_nodes(list(nodes))
    graph.update(material_mode_summary(material_mode=mode, constraints=constraints))  # type: ignore[arg-type]
    graph["graph_mode"] = "canvas"
    if drc_fixup:
        graph["drc_fixup"] = {k: round(float(v), 4) for k, v in drc_fixup.items()}
    return graph


def compile_canvas_build(
    *,
    out_dir: str,
    nodes: Sequence[Mapping[str, Any]],
    wires: Sequence[Mapping[str, Any]] | None = None,
    constraints: Mapping[str, Any] | None = None,
    salvage_mode: bool = False,
    material_mode: str | None = None,
    build_id: str = "generic_low_voltage_build",
    export_gerber: bool = True,
    resolved_modules: Sequence[Mapping[str, Any]] | None = None,
    drc_fixup: Mapping[str, float] | None = None,
) -> CanvasCompileResult:
    """Editor/canvas partial graph → catalog compile with material_mode stamped on quality."""
    constraints_map = dict(constraints or {})
    if material_mode:
        constraints_map.setdefault("graph_mode", "canvas")
    mode = str(material_mode or resolve_material_mode(constraints=constraints_map, salvage_mode=salvage_mode))
    graph = build_canvas_graph(
        nodes=nodes,
        wires=wires,
        constraints=constraints_map,
        salvage_mode=salvage_mode,
        material_mode=mode,
        drc_fixup=drc_fixup,
    )
    notes: List[str] = ["Compiled from canvas/editor graph via unified netlist path."]
    if not graph.get("nodes"):
        return CanvasCompileResult(
            ok=False,
            build_id=build_id,
            graph=graph,
            material_mode=mode,
            error="canvas graph has no nodes",
            notes=notes,
        )

    splice_plan = {
        "target": {"recommended_build_id": build_id},
        "custom_graph": graph,
        "graph_mode": "canvas",
        "resolved_modules": list(resolved_modules or []),
        **material_mode_summary(material_mode=mode, constraints=constraints_map),  # type: ignore[arg-type]
    }
    compile_result = compile_catalog_build(
        build_id,
        out_dir,
        export_gerber=export_gerber,
        splice_plan=splice_plan,
        resolved_modules=list(resolved_modules or []),
    )
    quality = dict(compile_result.design_quality or {})
    quality.setdefault("material_mode", mode)
    return CanvasCompileResult(
        ok=bool(compile_result.ok),
        build_id=build_id,
        graph=graph,
        material_mode=mode,
        compile_result=compile_result,
        error=compile_result.error,
        notes=notes,
    )
