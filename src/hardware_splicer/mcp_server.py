"""MCP server — expose Hardware-Splicer compile engine to any MCP client.

Run:
  PYTHONPATH=src python -m hardware_splicer.mcp_server

Requires: pip install mcp  (see requirements-mcp.txt)
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any, Sequence

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError as exc:  # pragma: no cover - optional dependency
    print(
        "Hardware-Splicer MCP requires the 'mcp' package.\n"
        "  pip install -r requirements-mcp.txt\n",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

from . import sdk

app = Server("hardware-splicer")


def _tool_result(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=sdk.dump_json(payload))]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hs_sdk_info",
            description=(
                "Capability card: what Hardware-Splicer engine does vs Flux, default env, "
                "honest limits (cosmetic copper, KiCad truth)."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_engine_doctor",
            description="Check local runtime: Python deps, KiCad/node, app roots.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_list_catalog_builds",
            description="List canned catalog build IDs compileable by the engine.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_resolve_parts",
            description=(
                "Map inventory part rows (name, type, optional module_id, voltage_v) "
                "to module-library IDs and power topology."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "e.g. [{\"name\": \"ESP32 devkit\", \"type\": \"microcontroller\"}]",
                    }
                },
                "required": ["parts"],
            },
        ),
        Tool(
            name="hs_suggest_modules",
            description="NL goal → open-catalog module suggestions (scratch mode starter set).",
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "e.g. wifi temperature logger"}
                },
                "required": ["goal"],
            },
        ),
        Tool(
            name="hs_plan_salvage",
            description=(
                "Plan salvage splice from goal + inventory without KiCad compile (~fast). "
                "Use before hs_salvage_bringup when exploring feasibility."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "parts": {"type": "array", "items": {"type": "object"}},
                    "constraints": {"type": "object"},
                    "project_name": {"type": "string"},
                },
                "required": ["goal", "parts"],
            },
        ),
        Tool(
            name="hs_compose",
            description=(
                "Compose and compile: NL phrase, module_ids, or canvas nodes → "
                "wired graph, netlist, KiCad PCB, BOM, firmware scaffold. "
                "KiCad DRC errors=0 is the pass bar; copper is cosmetic preview by default."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "phrase": {"type": "string"},
                    "module_ids": {"type": "array", "items": {"type": "string"}},
                    "canvas_nodes": {"type": "array", "items": {"type": "object"}},
                    "canvas_wires": {"type": "array", "items": {"type": "object"}},
                    "constraints": {"type": "object"},
                    "material_mode": {"type": "string", "enum": ["scratch", "salvage"]},
                    "salvage_mode": {"type": "boolean"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                    "fab_profile": {"type": "boolean", "default": False},
                    "arbitrary": {"type": "boolean", "default": False},
                    "allow_llm_first": {"type": "boolean", "default": True},
                    "drc_fixup": {
                        "type": "object",
                        "description": "Geometry hints from prior DRC loop (edge_pad_extra_mm, module_gap_extra_mm, via_clearance_mm).",
                    },
                },
            },
        ),
        Tool(
            name="hs_modules_catalog",
            description=(
                "List KiCad-footprinted modules for canvas compose (same catalog as Design Studio). "
                "Use before hs_compose with canvas_nodes."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_compose_drc_agent",
            description=(
                "Agent orchestration: hs_compose plus bounded manual DRC fixup rounds. "
                "Returns agent_loop.rounds with per-round KiCad DRC errors and drc_fixup. "
                "Set finalize_package=true for PROJECT_PACKAGE + bench_session."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "phrase": {"type": "string"},
                    "module_ids": {"type": "array", "items": {"type": "string"}},
                    "canvas_nodes": {"type": "array", "items": {"type": "object"}},
                    "canvas_wires": {"type": "array", "items": {"type": "object"}},
                    "constraints": {"type": "object"},
                    "material_mode": {"type": "string", "enum": ["scratch", "salvage"]},
                    "salvage_mode": {"type": "boolean"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                    "allow_llm_first": {"type": "boolean", "default": True},
                    "drc_fixup": {"type": "object"},
                    "max_manual_retries": {"type": "integer", "default": 2},
                    "finalize_package": {"type": "boolean", "default": False},
                    "project_name": {"type": "string"},
                },
            },
        ),
        Tool(
            name="hs_design_quality",
            description=(
                "Read KiCad DRC summary, drc_fix_loop, and error violations for a compose/splice build_dir."
            ),
            inputSchema={
                "type": "object",
                "properties": {"build_dir": {"type": "string"}},
                "required": ["build_dir"],
            },
        ),
        Tool(
            name="hs_salvage_bringup",
            description=(
                "Full salvage bring-up from PROJECT_INTAKE-shaped JSON: "
                "splice + compile + SALVAGE_BRINGUP_REPORT.json."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intake": {"type": "object"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                },
                "required": ["intake"],
            },
        ),
        Tool(
            name="hs_compose_arbitrary",
            description=(
                "NL goal → Qwen text netlist IR (when DASHSCOPE_API_KEY set) → KiCad compile. "
                "Use arbitrary=true for Qwen text netlist path. fab_profile exports gerbers headlessly (no FreeRouting)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "constraints": {"type": "object"},
                    "fab_profile": {"type": "boolean", "default": False},
                    "export_gerber": {"type": "boolean"},
                    "out_dir": {"type": "string"},
                    "allow_qwen": {"type": "boolean", "default": True},
                },
                "required": ["goal"],
            },
        ),
        Tool(
            name="hs_jarvis_build",
            description=(
                "Primary electrical JARVIS path: NL goal (+ optional salvage parts) → "
                "Qwen netlist when keyed → KiCad compile → simulation → TRUST_REPORT + JARVIS narrative."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "parts": {"type": "array", "items": {"type": "object"}},
                    "constraints": {"type": "object"},
                    "project_name": {"type": "string"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                    "allow_qwen": {"type": "boolean", "default": True},
                },
                "required": ["goal"],
            },
        ),
        Tool(
            name="hs_donor_board_vision",
            description=(
                "Donor board photo or embedded board_evidence.v1 → functional_salvage blocks on "
                "circuit.boards (Qwen board vision when live + image path). Use before or inside splice build."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intake": {"type": "object"},
                },
                "required": ["intake"],
            },
        ),
        Tool(
            name="hs_vision_capabilities",
            description="Inventory camera/vision/bench-capture modules already in the repo and how to reach them.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hs_vision_enrich_intake",
            description=(
                "Run intake vision on attachments (Qwen/Gemini when keyed). "
                "Set vision_assistance in intake or pass apply/live flags. "
                "Does not close splice bench gates by itself."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intake": {"type": "object"},
                    "apply": {"type": "boolean", "description": "Apply vision notes into intake evidence"},
                    "live": {"type": "boolean", "description": "Call live vision provider"},
                },
                "required": ["intake"],
            },
        ),
        Tool(
            name="hs_splice_bench_capture_template",
            description=(
                "Get BENCH_CAPTURE_TEMPLATE.json for open splice gates — fill measurements "
                "then submit with hs_splice_bench_submit_capture."
            ),
            inputSchema={
                "type": "object",
                "properties": {"build_dir": {"type": "string"}},
                "required": ["build_dir"],
            },
        ),
        Tool(
            name="hs_splice_bench_submit_capture",
            description=(
                "Submit bench_topology_capture.v1 packet to close matching splice bench gates. "
                "Use after hs_splice_build when instrument/camera rig produces structured capture JSON."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string"},
                    "capture": {"type": "object", "description": "bench_topology_capture.v1 packet"},
                },
                "required": ["build_dir", "capture"],
            },
        ),
        Tool(
            name="hs_splice_golden_loop",
            description=(
                "One-shot S3 golden loop: donor intake → splice compile → bench template → "
                "capture submit → gate closure. simulate_bench=true fills pass readings for CI; "
                "set false when submitting real instrument capture yourself."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intake": {"type": "object", "description": "PROJECT_INTAKE-shaped splice brief"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                    "simulate_bench": {
                        "type": "boolean",
                        "default": True,
                        "description": "Auto-fill template with simulated pass measurements",
                    },
                },
                "required": ["intake"],
            },
        ),
        Tool(
            name="hs_splice_build",
            description=(
                "Primary splice path: donor PROJECT_INTAKE JSON → splice plan → carrier KiCad compile. "
                "Opens SPLICE_BENCH_SESSION.json automatically. Use before bench submit."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intake": {"type": "object", "description": "PROJECT_INTAKE-shaped splice brief"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                },
                "required": ["intake"],
            },
        ),
        Tool(
            name="hs_splice_bench_status",
            description=(
                "S3 bench gate status for a splice build directory. "
                "Returns open/closed evidence gates and power_on_authorized flag."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string", "description": "Splice output directory"},
                },
                "required": ["build_dir"],
            },
        ),
        Tool(
            name="hs_splice_bench_submit",
            description=(
                "Submit bench measurements to close evidence gates. "
                "Each item: gate_id, status (closed|pass|fail|open), optional value/unit/notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string"},
                    "measurements": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": '[{"gate_id":"vmotor_rail","status":"closed","value":6.1,"unit":"V"}]',
                    },
                },
                "required": ["build_dir", "measurements"],
            },
        ),
        Tool(
            name="hs_inspect_fab",
            description=(
                "Inspect fabrication package on disk (PCB, BOM, Gerbers) without recompiling. "
                "Pass a catalog build dir or splice output dir."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string", "description": "Compile or splice output directory"},
                },
                "required": ["build_dir"],
            },
        ),
        Tool(
            name="hs_verify_engine",
            description=(
                "Compile catalog builds headlessly and check KiCad DRC errors=0. "
                "Slow (~20s full set). No FreeRouting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_ids": {"type": "array", "items": {"type": "string"}},
                    "max_warnings": {"type": "integer", "default": 500},
                    "out_dir": {"type": "string"},
                },
            },
        ),
        Tool(
            name="hs_clarify_hardware_intent",
            description=(
                "Blueprint-style front-half clarifier: vague hardware goals → "
                "clarifying questions + enriched intent fields. Use before plan/splice."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "object",
                        "description": "goal, supply_voltage_v, clarification_answers, …",
                    }
                },
                "required": ["intent"],
            },
        ),
        Tool(
            name="hs_plan_circuit_synthesis",
            description=(
                "Bounded circuit synthesis planner: intent → SynthesisCandidate "
                "(blocked | ready_for_review) with topology authority metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {"type": "object", "description": "CircuitIntent-shaped dict"},
                },
                "required": ["intent"],
            },
        ),
        Tool(
            name="hs_synthesize_circuit",
            description=(
                "Plan + optionally compile circuit synthesis candidate. "
                "Writes PROJECT_PACKAGE.json + PROJECT_PAGE.md when out_dir is set."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {"type": "object"},
                    "out_dir": {"type": "string"},
                    "export_gerber": {"type": "boolean", "default": False},
                    "compile_build": {
                        "type": "boolean",
                        "default": True,
                        "description": "false = plan-only package without KiCad compile",
                    },
                },
                "required": ["intent"],
            },
        ),
        Tool(
            name="hs_render_project_package",
            description=(
                "Refresh Blueprint-shaped PROJECT_PACKAGE artifacts from a build dir "
                "(splice or synthesis). Emits PROJECT_PAGE.md, WIRING_GUIDE.md, ASSEMBLY_GUIDE.md."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string"},
                    "result": {
                        "type": "object",
                        "description": "Optional in-memory build result to merge",
                    },
                    "source": {
                        "type": "string",
                        "default": "auto",
                        "description": "auto | splice_build | circuit_synthesis | …",
                    },
                },
                "required": ["build_dir"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any] | None) -> Sequence[TextContent]:
    args = arguments or {}

    if name == "hs_sdk_info":
        return _tool_result(sdk.sdk_info())
    if name == "hs_engine_doctor":
        return _tool_result(sdk.engine_doctor())
    if name == "hs_list_catalog_builds":
        return _tool_result(sdk.list_catalog_builds())
    if name == "hs_resolve_parts":
        return _tool_result(sdk.resolve_inventory_parts(args.get("parts") or []))
    if name == "hs_suggest_modules":
        return _tool_result(sdk.suggest_modules(str(args.get("goal") or "")))
    if name == "hs_plan_salvage":
        return _tool_result(
            sdk.plan_salvage(
                goal=str(args.get("goal") or ""),
                parts=args.get("parts") or [],
                constraints=args.get("constraints"),
                project_name=args.get("project_name"),
            )
        )
    if name == "hs_compose":
        return _tool_result(
            sdk.compose_design(
                phrase=args.get("phrase"),
                module_ids=args.get("module_ids"),
                canvas_nodes=args.get("canvas_nodes"),
                canvas_wires=args.get("canvas_wires"),
                constraints=args.get("constraints"),
                material_mode=args.get("material_mode"),
                salvage_mode=bool(args.get("salvage_mode")),
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
                fab_profile=bool(args.get("fab_profile")),
                arbitrary=bool(args.get("arbitrary")),
                allow_llm_first=bool(args.get("allow_llm_first", True)),
                drc_fixup=args.get("drc_fixup"),
            )
        )
    if name == "hs_modules_catalog":
        from .pcb.module_registry import list_canvas_modules

        modules = list_canvas_modules()
        return _tool_result({"ok": True, "count": len(modules), "modules": modules})
    if name == "hs_compose_drc_agent":
        return _tool_result(
            sdk.compose_design_agent_loop(
                phrase=args.get("phrase"),
                module_ids=args.get("module_ids"),
                canvas_nodes=args.get("canvas_nodes"),
                canvas_wires=args.get("canvas_wires"),
                constraints=args.get("constraints"),
                material_mode=args.get("material_mode"),
                salvage_mode=bool(args.get("salvage_mode")),
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
                allow_llm_first=bool(args.get("allow_llm_first", True)),
                drc_fixup=args.get("drc_fixup"),
                max_manual_retries=int(args.get("max_manual_retries", 2)),
                finalize_package=bool(args.get("finalize_package")),
                goal=args.get("phrase"),
                project_name=args.get("project_name"),
            )
        )
    if name == "hs_design_quality":
        from .build_files import read_design_quality_summary

        return _tool_result(read_design_quality_summary(str(args.get("build_dir") or "")))
    if name == "hs_compose_arbitrary":
        return _tool_result(
            sdk.compose_arbitrary(
                str(args.get("goal") or ""),
                constraints=args.get("constraints"),
                out_dir=args.get("out_dir"),
                fab_profile=bool(args.get("fab_profile")),
                export_gerber=args.get("export_gerber"),
                allow_qwen=bool(args.get("allow_qwen", True)),
            )
        )
    if name == "hs_salvage_bringup":
        return _tool_result(
            sdk.salvage_bringup(
                args.get("intake") or {},
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
            )
        )
    if name == "hs_jarvis_build":
        return _tool_result(
            sdk.jarvis_build(
                str(args.get("goal") or ""),
                parts=args.get("parts"),
                constraints=args.get("constraints"),
                project_name=args.get("project_name"),
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
                allow_qwen=bool(args.get("allow_qwen", True)),
            )
        )
    if name == "hs_donor_board_vision":
        return _tool_result(sdk.donor_board_vision_enrich(args.get("intake") or {}))
    if name == "hs_vision_capabilities":
        return _tool_result(sdk.vision_capabilities())
    if name == "hs_vision_enrich_intake":
        return _tool_result(
            sdk.vision_enrich_intake(
                args.get("intake") or {},
                apply=args.get("apply"),
                live=args.get("live"),
            )
        )
    if name == "hs_splice_bench_capture_template":
        return _tool_result(sdk.splice_bench_capture_template(str(args.get("build_dir") or "")))
    if name == "hs_splice_bench_submit_capture":
        return _tool_result(
            sdk.splice_bench_submit_capture(
                str(args.get("build_dir") or ""),
                args.get("capture") or {},
            )
        )
    if name == "hs_splice_golden_loop":
        return _tool_result(
            sdk.splice_golden_loop(
                args.get("intake") or {},
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
                simulate_bench=bool(args.get("simulate_bench", True)),
            )
        )
    if name == "hs_splice_build":
        return _tool_result(
            sdk.splice_build(
                args.get("intake") or {},
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
            )
        )
    if name == "hs_splice_bench_status":
        return _tool_result(sdk.splice_bench_status(str(args.get("build_dir") or "")))
    if name == "hs_splice_bench_submit":
        return _tool_result(
            sdk.splice_bench_submit(
                str(args.get("build_dir") or ""),
                args.get("measurements") or [],
            )
        )
    if name == "hs_inspect_fab":
        return _tool_result(sdk.inspect_fab_build_dir(str(args.get("build_dir") or "")))
    if name == "hs_verify_engine":
        return _tool_result(
            sdk.verify_engine(
                build_ids=args.get("build_ids"),
                max_warnings=int(args.get("max_warnings") or 500),
                out_dir=args.get("out_dir"),
            )
        )
    if name == "hs_clarify_hardware_intent":
        return _tool_result(sdk.clarify_hardware_intent(args.get("intent") or {}))
    if name == "hs_plan_circuit_synthesis":
        return _tool_result(sdk.plan_circuit_synthesis(args.get("intent") or {}))
    if name == "hs_synthesize_circuit":
        return _tool_result(
            sdk.synthesize_circuit(
                args.get("intent") or {},
                out_dir=args.get("out_dir"),
                export_gerber=bool(args.get("export_gerber")),
                compile_build=bool(args.get("compile_build", True)),
            )
        )
    if name == "hs_render_project_package":
        return _tool_result(
            sdk.render_project_package(
                str(args.get("build_dir") or ""),
                result=args.get("result"),
                source=str(args.get("source") or "auto"),
            )
        )

    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
